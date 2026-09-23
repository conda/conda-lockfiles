from __future__ import annotations

import warnings
from contextlib import nullcontext
from typing import TYPE_CHECKING

import pytest
from conda.base.context import context, reset_context
from conda.exceptions import CondaValueError
from conda.models.environment import Environment

from conda_lockfiles.conda_lock.v1 import (
    CONDA_LOCK_FILE,
    PIP_EXPORT_WARNING,
    CondaLockV1Loader,
    multiplatform_export,
)
from conda_lockfiles.exceptions import EnvironmentExportNotSupported
from conda_lockfiles.load_yaml import load_yaml

from .. import (
    CONDA_LOCK_METADATA_DIR,
    INVALID_LOCKFILES_DIR,
    SINGLE_PACKAGE_ENV,
    SINGLE_PACKAGE_NO_URL_ENV,
    compare_conda_lock_v1,
)

if TYPE_CHECKING:
    from pathlib import Path

    from conda.testing.fixtures import CondaCLIFixture, TmpEnvFixture
    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    "prefix,exception",
    [
        pytest.param(SINGLE_PACKAGE_ENV, None, id="single-package"),
        pytest.param(
            SINGLE_PACKAGE_NO_URL_ENV,
            EnvironmentExportNotSupported,
            id="single-package-no-url",
        ),
    ],
)
def test_export_to_conda_lock_v1(
    mocker: MockerFixture,
    tmp_path: Path,
    conda_cli: CondaCLIFixture,
    prefix: Path,
    exception: Exception | None,
) -> None:
    # mock context.channels to only contain conda-forge
    mocker.patch(
        "conda.base.context.Context.channels",
        new_callable=mocker.PropertyMock,
        return_value=(channels := ("conda-forge",)),
    )
    assert context.channels == channels

    reference = prefix / CONDA_LOCK_FILE
    lockfile = tmp_path / CONDA_LOCK_FILE
    with pytest.raises(exception) if exception else nullcontext():
        out, err, rc = conda_cli("export", f"--prefix={prefix}", f"--file={lockfile}")
        assert not out
        assert not err
        assert rc == 0
        assert compare_conda_lock_v1(lockfile, reference)

    # TODO: conda's context is not reset when EnvironmentExportNotSupported is raised?
    reset_context()


def test_export_lockfile_with_pip_deps():
    """Test exporting conda lockfile with pip deps will produce an error message"""
    env_with_pip = Environment(
        platform=context.subdir,
        prefix="idontexist",
        external_packages={"pip": ["pypi/pypi::packaging==25.0=pypi_0"]},
    )
    with warnings.catch_warnings(record=True) as warning_list:
        export = multiplatform_export([env_with_pip])
        warning_messages = [str(w.message) for w in warning_list]
        assert PIP_EXPORT_WARNING in warning_messages
        assert export is not None


def test_can_handle(tmp_path: Path) -> None:
    loader = CondaLockV1Loader(CONDA_LOCK_METADATA_DIR / CONDA_LOCK_FILE)
    assert loader.can_handle()
    assert loader.env

    # Invalid file type should raise ValueError
    with pytest.raises(ValueError, match="validation errors:"):
        CondaLockV1Loader(CONDA_LOCK_METADATA_DIR / "environment.yaml").can_handle()

    # Non-existent file should raise ValueError
    with pytest.raises(ValueError, match="Cannot load file"):
        CondaLockV1Loader(tmp_path / CONDA_LOCK_FILE).can_handle()


def test_data() -> None:
    loader = CondaLockV1Loader(CONDA_LOCK_METADATA_DIR / CONDA_LOCK_FILE)
    assert loader._data["version"] == 1
    assert len(loader._data["package"]) == 14


def test_noarch(
    mocker: MockerFixture,
    conda_cli: CondaCLIFixture,
    tmp_env: TmpEnvFixture,
    tmp_path: Path,
) -> None:
    """Test that noarch packages are listed once within lockfile."""
    platforms = ["linux-64", "osx-arm64"]  # more than one
    lockfile = tmp_path / CONDA_LOCK_FILE
    with tmp_env("--override-channels", "--channel=conda-forge", "boltons") as prefix:
        out, err, rc = conda_cli(
            "export",
            f"--prefix={prefix}",
            f"--file={lockfile}",
            "--override-platforms",
            *(f"--platform={platform}" for platform in platforms),
        )
        assert "Collecting package metadata" in out
        assert not err
        assert rc == 0

        data = load_yaml(lockfile)
        assert (
            sorted(
                package["platform"]
                for package in data["package"]
                if package["name"] == "boltons"
            )
            == platforms
        )


@pytest.mark.parametrize(
    "lockfile,should_raise",
    [
        pytest.param(
            CONDA_LOCK_METADATA_DIR / CONDA_LOCK_FILE,
            False,
            id="valid-lockfile",
        ),
        pytest.param(
            INVALID_LOCKFILES_DIR / "conda-lock-v1-missing-metadata.yml",
            True,
            id="missing-metadata",
        ),
        pytest.param(
            INVALID_LOCKFILES_DIR / "conda-lock-v1-missing-package.yml",
            True,
            id="missing-package",
        ),
        pytest.param(
            INVALID_LOCKFILES_DIR / "conda-lock-v1-invalid-metadata-type.yml",
            True,
            id="invalid-metadata-type",
        ),
    ],
)
def test_can_handle_validation(lockfile: Path, should_raise: bool) -> None:
    """Test that can_handle properly validates lockfile structure."""
    loader = CondaLockV1Loader(lockfile)

    with pytest.raises(ValueError) if should_raise else nullcontext():
        result = loader.can_handle()
        if not should_raise:
            # If the validation should be successful, ensure that
            # can_handle returns True and the environment can be loaded.
            assert result
            loader.env


def test_can_handle_raises_validation_errors(tmp_path: Path) -> None:
    """Test that validation errors raise CondaValueError with descriptive messages."""
    # Create an invalid lockfile
    invalid_lockfile = tmp_path / CONDA_LOCK_FILE
    invalid_lockfile.write_text("version: 1\npackage: []")

    loader = CondaLockV1Loader(invalid_lockfile)

    # Should raise CondaValueError with descriptive message (Pydantic format)
    with pytest.raises(CondaValueError, match="missing required field 'metadata'"):
        loader.can_handle()
