from __future__ import annotations

from contextlib import nullcontext
from typing import TYPE_CHECKING

import pytest
from conda.base.context import context, reset_context
from conda.exceptions import CondaValueError

from conda_lockfiles.exceptions import EnvironmentExportNotSupported
from conda_lockfiles.load_yaml import load_yaml
from conda_lockfiles.rattler_lock.v7 import (
    PIXI_LOCK_FILE,
    RattlerLockV7Loader,
    rattler_lock_v7_to_conda_env,
)

from .. import (
    INVALID_LOCKFILES_DIR,
    PIXI_V7_METADATA_DIR,
    SINGLE_PACKAGE_ENV,
    SINGLE_PACKAGE_NO_URL_ENV,
    compare_rattler_lock_v7,
)

if TYPE_CHECKING:
    from pathlib import Path

    from conda.testing.fixtures import CondaCLIFixture, TmpEnvFixture
    from pytest_mock import MockerFixture


V7_REFERENCE_FILE = "pixi-v7.lock"


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
def test_export_to_rattler_lock_v7(
    mocker: MockerFixture,
    tmp_path: Path,
    conda_cli: CondaCLIFixture,
    prefix: Path,
    exception: Exception | None,
) -> None:
    mocker.patch(
        "conda.base.context.Context.channels",
        new_callable=mocker.PropertyMock,
        return_value=(channels := ("conda-forge",)),
    )
    assert context.channels == channels

    reference = prefix / V7_REFERENCE_FILE
    lockfile = tmp_path / PIXI_LOCK_FILE
    with pytest.raises(exception) if exception else nullcontext():
        out, err, rc = conda_cli(
            "export",
            f"--prefix={prefix}",
            f"--file={lockfile}",
            "--format=rattler-lock-v7",
        )
        assert not out
        assert not err
        assert rc == 0
        assert compare_rattler_lock_v7(lockfile, reference)

    reset_context()


def test_can_handle() -> None:
    loader = RattlerLockV7Loader(PIXI_V7_METADATA_DIR / PIXI_LOCK_FILE)
    assert loader.can_handle()
    assert loader.env


def test_can_handle_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="File not found"):
        RattlerLockV7Loader(tmp_path / PIXI_LOCK_FILE).can_handle()


def test_data() -> None:
    loader = RattlerLockV7Loader(PIXI_V7_METADATA_DIR / PIXI_LOCK_FILE)
    assert loader._data["version"] == 7
    assert len(loader._data["environments"]["default"]["packages"]["linux-64"]) == 1


def test_available_platforms() -> None:
    loader = RattlerLockV7Loader(PIXI_V7_METADATA_DIR / PIXI_LOCK_FILE)
    loader.can_handle()
    assert set(loader.available_platforms) == {
        "linux-64",
        "osx-64",
        "osx-arm64",
        "win-64",
    }


def test_env_for_invalid_platform() -> None:
    loader = RattlerLockV7Loader(PIXI_V7_METADATA_DIR / PIXI_LOCK_FILE)
    loader.can_handle()
    with pytest.raises(ValueError, match="not in lockfile"):
        loader.env_for("linux-aarch64")


def test_env_rejects_missing_context_platform(tmp_path: Path) -> None:
    lockfile = tmp_path / PIXI_LOCK_FILE
    platform = "osx-64" if context.subdir != "osx-64" else "linux-64"
    lockfile.write_text(
        f"""\
version: 7
platforms:
  - name: {platform}
environments:
  default:
    channels: []
    packages:
      {platform}: []
packages: []
"""
    )

    loader = RattlerLockV7Loader(lockfile)
    assert loader.can_handle()
    with pytest.raises(CondaValueError, match=f"Platform {context.subdir!r}"):
        loader.env


def test_env_for_rejects_platform_missing_from_environment(tmp_path: Path) -> None:
    lockfile = tmp_path / PIXI_LOCK_FILE
    lockfile.write_text(
        """\
version: 7
platforms:
  - name: linux-64
  - name: osx-64
environments:
  default:
    channels: []
    packages:
      linux-64: []
packages: []
"""
    )

    loader = RattlerLockV7Loader(lockfile)
    assert loader.can_handle()
    with pytest.raises(ValueError, match="not found in environment"):
        loader.env_for("osx-64")


def test_env_for_rejects_conda_source_packages(tmp_path: Path) -> None:
    lockfile = tmp_path / PIXI_LOCK_FILE
    lockfile.write_text(
        """\
version: 7
platforms:
  - name: linux-64
environments:
  default:
    channels: []
    packages:
      linux-64:
        - conda_source: "my-package[12345678] @ ./my-package"
packages:
  - conda_source: "my-package[12345678] @ ./my-package"
    version: 0.1.0
    build: py_0
    subdir: noarch
"""
    )

    loader = RattlerLockV7Loader(lockfile)
    assert loader.can_handle()
    with pytest.raises(ValueError, match="conda_source packages are not supported"):
        loader.env_for("linux-64")


def test_env_for_rejects_missing_package_metadata(tmp_path: Path) -> None:
    url = "https://conda.anaconda.org/conda-forge/noarch/tzdata-2025b-h78e105d_0.conda"
    lockfile = tmp_path / PIXI_LOCK_FILE
    lockfile.write_text(
        f"""\
version: 7
platforms:
  - name: linux-64
environments:
  default:
    channels: []
    packages:
      linux-64:
        - conda: {url}
packages: []
"""
    )

    loader = RattlerLockV7Loader(lockfile)
    assert loader.can_handle()
    with pytest.raises(ValueError, match="was not found in packages list"):
        loader.env_for("linux-64")


def test_can_handle_rejects_invalid_package_references(tmp_path: Path) -> None:
    lockfile = tmp_path / PIXI_LOCK_FILE
    lockfile.write_text(
        """\
version: 7
platforms:
  - name: linux-64
environments:
  default:
    channels: []
    packages:
      linux-64:
        - conda: https://example.test/pkg.conda
          pypi: https://example.test/pkg.whl
packages:
  - conda: https://example.test/pkg.conda
    pypi: https://example.test/pkg.whl
"""
    )

    loader = RattlerLockV7Loader(lockfile)
    with pytest.raises(CondaValueError, match="Exactly one"):
        loader.can_handle()


def test_can_handle_rejects_missing_package_reference_type(tmp_path: Path) -> None:
    lockfile = tmp_path / PIXI_LOCK_FILE
    lockfile.write_text(
        """\
version: 7
platforms:
  - name: linux-64
environments:
  default:
    channels: []
    packages:
      linux-64:
        - name: pkg
packages:
  - name: pkg
"""
    )

    loader = RattlerLockV7Loader(lockfile)
    with pytest.raises(CondaValueError, match="Exactly one"):
        loader.can_handle()


def test_can_handle_accepts_non_default_environments(tmp_path: Path) -> None:
    lockfile = tmp_path / PIXI_LOCK_FILE
    lockfile.write_text(
        """\
version: 7
platforms:
  - name: linux-64
environments:
  docs:
    channels: []
    packages: {}
packages: []
"""
    )

    loader = RattlerLockV7Loader(lockfile)
    assert loader.can_handle()
    env = rattler_lock_v7_to_conda_env(loader._model, name="docs", platform="linux-64")
    assert env.platform == "linux-64"
    assert not env.explicit_packages

    with pytest.raises(CondaValueError, match="Environment 'default' not found"):
        loader.env


def test_env_for_preserves_pypi_references(tmp_path: Path) -> None:
    lockfile = tmp_path / PIXI_LOCK_FILE
    lockfile.write_text(
        """\
version: 7
platforms:
  - name: linux-64
environments:
  default:
    channels: []
    indexes:
      - https://my-custom-index.example.com/simple
    packages:
      linux-64:
        - pypi: ./local-pkg
        - pypi: https://example.test/pkg-1.0-py3-none-any.whl
packages:
  - pypi: ./local-pkg
    name: local-pkg
  - pypi: https://example.test/pkg-1.0-py3-none-any.whl
    name: pkg
    version: "1.0"
    sha256: f93fc78fe8bf15afe2b8d6b6499f1c73953571c004b3135db0c83b9a5fd4e5e1
    index: https://my-custom-index.example.com/simple
"""
    )

    loader = RattlerLockV7Loader(lockfile)
    assert loader.can_handle()
    env = loader.env_for("linux-64")
    assert env.external_packages == {
        "pypi": ["./local-pkg", "https://example.test/pkg-1.0-py3-none-any.whl"]
    }


def test_noarch(
    mocker: MockerFixture,
    conda_cli: CondaCLIFixture,
    tmp_env: TmpEnvFixture,
    tmp_path: Path,
) -> None:
    """Test that noarch packages are listed once within lockfile."""
    platforms = ["linux-64", "osx-arm64"]
    lockfile = tmp_path / PIXI_LOCK_FILE
    with tmp_env("--override-channels", "--channel=conda-forge", "boltons") as prefix:
        out, err, rc = conda_cli(
            "export",
            f"--prefix={prefix}",
            f"--file={lockfile}",
            "--format=rattler-lock-v7",
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
            PIXI_V7_METADATA_DIR / PIXI_LOCK_FILE,
            False,
            id="valid-lockfile",
        ),
        pytest.param(
            INVALID_LOCKFILES_DIR / "pixi-lock-v7-missing-environments.lock",
            True,
            id="missing-environments",
        ),
        pytest.param(
            INVALID_LOCKFILES_DIR / "pixi-lock-v7-missing-packages.lock",
            True,
            id="missing-packages",
        ),
        pytest.param(
            INVALID_LOCKFILES_DIR / "pixi-lock-v7-missing-platforms.lock",
            True,
            id="missing-platforms",
        ),
        pytest.param(
            INVALID_LOCKFILES_DIR / "pixi-lock-v7-invalid-environments-type.lock",
            True,
            id="invalid-environments-type",
        ),
    ],
)
def test_can_handle_validation(lockfile: Path, should_raise: bool) -> None:
    """Test that can_handle properly validates lockfile structure."""
    loader = RattlerLockV7Loader(lockfile)

    with pytest.raises(ValueError) if should_raise else nullcontext():
        result = loader.can_handle()
        if not should_raise:
            assert result
            loader.env


def test_can_handle_raises_validation_errors(tmp_path: Path) -> None:
    """Test that validation errors raise CondaValueError with descriptive messages."""
    invalid_lockfile = tmp_path / PIXI_LOCK_FILE
    invalid_lockfile.write_text("version: 7\nplatforms: []\npackages: []")

    loader = RattlerLockV7Loader(invalid_lockfile)

    with pytest.raises(CondaValueError, match="missing required field 'environments'"):
        loader.can_handle()


def test_v7_rejects_v6_lockfile() -> None:
    """Ensure v7 loader rejects a v6 lockfile."""
    from tests import PIXI_V6_METADATA_DIR

    loader = RattlerLockV7Loader(PIXI_V6_METADATA_DIR / PIXI_LOCK_FILE)
    with pytest.raises(CondaValueError):
        loader.can_handle()


def test_platforms_section_in_export(
    mocker: MockerFixture,
    tmp_path: Path,
    conda_cli: CondaCLIFixture,
) -> None:
    """Verify that exported v7 lockfiles contain the top-level platforms list."""
    mocker.patch(
        "conda.base.context.Context.channels",
        new_callable=mocker.PropertyMock,
        return_value=("conda-forge",),
    )
    lockfile = tmp_path / PIXI_LOCK_FILE
    out, err, rc = conda_cli(
        "export",
        f"--prefix={SINGLE_PACKAGE_ENV}",
        f"--file={lockfile}",
        "--format=rattler-lock-v7",
    )
    assert rc == 0
    data = load_yaml(lockfile)
    assert data["version"] == 7
    assert "platforms" in data
    assert any(p["name"] == "linux-64" for p in data["platforms"])

    reset_context()
