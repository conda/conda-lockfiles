from __future__ import annotations

from contextlib import nullcontext
from typing import TYPE_CHECKING

import pytest
from conda.base.context import context, reset_context
from conda.exceptions import CondaValueError

from conda_lockfiles.exceptions import (
    CondaLockfilesParserError,
    EnvironmentExportNotSupported,
)
from conda_lockfiles.load_yaml import load_yaml
from conda_lockfiles.rattler_lock.v6 import PIXI_LOCK_FILE, RattlerLockV6Loader

from .. import (
    INVALID_LOCKFILES_DIR,
    PIXI_DIR,
    PIXI_V6_METADATA_DIR,
    SINGLE_PACKAGE_ENV,
    SINGLE_PACKAGE_NO_URL_ENV,
    compare_rattler_lock_v6,
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
def test_export_to_rattler_lock_v6(
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

    reference = prefix / PIXI_LOCK_FILE
    lockfile = tmp_path / PIXI_LOCK_FILE
    with pytest.raises(exception) if exception else nullcontext():
        out, err, rc = conda_cli(
            "export",
            f"--prefix={prefix}",
            f"--file={lockfile}",
            "--format=rattler-lock-v6",
        )
        assert not out
        assert not err
        assert rc == 0
        assert compare_rattler_lock_v6(lockfile, reference)

    # TODO: conda's context is not reset when EnvironmentExportNotSupported is raised?
    reset_context()


def test_can_handle(tmp_path: Path) -> None:
    loader = RattlerLockV6Loader(PIXI_DIR / PIXI_LOCK_FILE)
    assert loader.can_handle()
    assert loader.env

    # Invalid yaml file should raise a parse error
    with pytest.raises(CondaLockfilesParserError, match="Unable to parse the content"):
        RattlerLockV6Loader(PIXI_DIR / "pixi.toml").can_handle()

    # Non-existent file should raise ValueError
    with pytest.raises(ValueError, match="File not found"):
        RattlerLockV6Loader(tmp_path / PIXI_LOCK_FILE).can_handle()


def test_data() -> None:
    loader = RattlerLockV6Loader(PIXI_DIR / PIXI_LOCK_FILE)
    assert loader._data["version"] == 6
    assert len(loader._data["environments"]["default"]["packages"]["noarch"]) == 2


def test_noarch(
    mocker: MockerFixture,
    conda_cli: CondaCLIFixture,
    tmp_env: TmpEnvFixture,
    tmp_path: Path,
) -> None:
    """Test that noarch packages are listed once within lockfile."""
    platforms = ["linux-64", "osx-arm64"]  # more than one
    lockfile = tmp_path / PIXI_LOCK_FILE
    with tmp_env("--override-channels", "--channel=conda-forge", "boltons") as prefix:
        out, err, rc = conda_cli(
            "export",
            f"--prefix={prefix}",
            f"--file={lockfile}",
            "--format=rattler-lock-v6",
            "--override-platforms",
            *(f"--platform={platform}" for platform in platforms),
        )
        assert "Collecting package metadata" in out
        assert not err
        assert rc == 0

        data = load_yaml(lockfile)
        assert (
            sum(
                "conda-forge/noarch/boltons-" in package["conda"]
                for package in data["packages"]
            )
            == 1
        )


@pytest.mark.parametrize(
    "lockfile,should_raise",
    [
        pytest.param(
            PIXI_V6_METADATA_DIR / PIXI_LOCK_FILE,
            False,
            id="valid-lockfile",
        ),
        pytest.param(
            INVALID_LOCKFILES_DIR / "pixi-lock-v6-missing-environments.lock",
            True,
            id="missing-environments",
        ),
        pytest.param(
            INVALID_LOCKFILES_DIR / "pixi-lock-v6-missing-packages.lock",
            True,
            id="missing-packages",
        ),
        pytest.param(
            INVALID_LOCKFILES_DIR / "pixi-lock-v6-invalid-environments-type.lock",
            True,
            id="invalid-environments-type",
        ),
    ],
)
def test_can_handle_validation(lockfile: Path, should_raise: bool) -> None:
    """Test that can_handle properly validates lockfile structure."""
    loader = RattlerLockV6Loader(lockfile)

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
    invalid_lockfile = tmp_path / PIXI_LOCK_FILE
    invalid_lockfile.write_text("version: 6\npackages: []")

    loader = RattlerLockV6Loader(invalid_lockfile)

    # Should raise CondaValueError with descriptive message
    with pytest.raises(CondaValueError, match="missing required field 'environments'"):
        loader.can_handle()
