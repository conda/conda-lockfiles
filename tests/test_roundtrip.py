from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conda.base.context import context
from conda.common.compat import on_win
from conda.exceptions import CondaMultiError

from conda_lockfiles.conda_lock import v1 as conda_lock_v1
from conda_lockfiles.load_yaml import load_yaml
from conda_lockfiles.rattler_lock import v6 as rattler_lock_v6

from . import compare_conda_lock_v1, compare_rattler_lock_v6

CONDA_FORGE_CHANNEL_ARGS = ("--override-channels", "--channel=conda-forge")

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Callable

    from conda.testing.fixtures import (
        CondaCLIFixture,
        PathFactoryFixture,
        TmpEnvFixture,
    )
    from pytest import MonkeyPatch


@pytest.mark.parametrize(
    "format,filename,compare",
    [
        (
            rattler_lock_v6.FORMAT,
            rattler_lock_v6.PIXI_LOCK_FILE,
            compare_rattler_lock_v6,
        ),
        (
            conda_lock_v1.FORMAT,
            conda_lock_v1.CONDA_LOCK_FILE,
            compare_conda_lock_v1,
        ),
    ],
)
def test_export(
    path_factory: PathFactoryFixture,
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    format: str,
    filename: str,
    compare: Callable[[Path, Path], bool],
) -> None:
    lockfile = path_factory(filename)
    prefix2 = path_factory()
    lockfile2 = path_factory(filename)

    with tmp_env(*CONDA_FORGE_CHANNEL_ARGS, "zlib") as prefix:
        # export environment to a lockfile
        out, err, rc = conda_cli(
            "export",
            f"--prefix={prefix}",
            f"--format={format}",
            f"--file={lockfile}",
        )
        assert not out
        assert not err
        assert rc == 0

        # create a new environment from the lockfile
        out, err, rc = conda_cli(
            "env",
            "create",
            f"--prefix={prefix2}",
            f"--env-spec={format}",
            f"--file={lockfile}",
        )
        assert out
        assert not err
        assert rc == 0

        # export new environment to a lockfile, should be identical
        out, err, rc = conda_cli(
            "export",
            f"--prefix={prefix2}",
            f"--format={format}",
            f"--file={lockfile2}",
        )
        assert not out
        assert not err
        assert rc == 0
        assert compare(lockfile, lockfile2)


def test_conda_lock_v1_export_detects_yaml_extension(
    path_factory: PathFactoryFixture,
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
) -> None:
    """conda-lock-v1 must be inferred from conda-lock.yaml (CEP-37 / issue #121)."""
    lockfile = path_factory("conda-lock.yaml")
    with tmp_env(*CONDA_FORGE_CHANNEL_ARGS, "zlib") as prefix:
        out, err, rc = conda_cli(
            "export",
            f"--prefix={prefix}",
            f"--file={lockfile}",
        )
        assert not out
        assert not err
        assert rc == 0
    data = load_yaml(lockfile)
    assert data["version"] == 1
    assert "metadata" in data and "package" in data


@pytest.mark.parametrize(
    "format,filename,get_platforms",
    [
        (
            conda_lock_v1.FORMAT,
            conda_lock_v1.CONDA_LOCK_FILE,
            lambda lockfile: tuple(load_yaml(lockfile)["metadata"]["platforms"]),
        ),
        (
            rattler_lock_v6.FORMAT,
            rattler_lock_v6.PIXI_LOCK_FILE,
            lambda lockfile: tuple(
                load_yaml(lockfile)["environments"]["default"]["packages"]
            ),
        ),
    ],
)
def test_multiplatform_export(
    path_factory: PathFactoryFixture,
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    format: str,
    filename: str,
    get_platforms: Callable[[Path], tuple[str, ...]],
    monkeypatch: MonkeyPatch,
):
    platforms = tuple(sorted({context.subdir, "linux-64", "osx-arm64", "win-64"}))
    lockfile = path_factory(filename)
    with tmp_env(*CONDA_FORGE_CHANNEL_ARGS, "zlib") as prefix:
        # export environment to a lockfile
        out, err, rc = conda_cli(
            "export",
            f"--prefix={prefix}",
            f"--format={format}",
            f"--file={lockfile}",
            "--override-platforms",
            *(f"--platform={platform}" for platform in platforms),
        )
        assert "Collecting package metadata" in out, out
        assert not err
        assert rc == 0
        assert get_platforms(lockfile) == platforms

        for platform in platforms:
            # create a new environment from the lockfile
            try:
                out, err, rc = conda_cli(
                    "env",
                    "create",
                    f"--prefix={path_factory()}",
                    f"--env-spec={format}",
                    f"--file={lockfile}",
                    f"--platform={platform}",
                )
            except CondaMultiError:
                # on Windows unpacking packages for non-Windows platforms fails but we
                # ignore this since we only care about the solve/download
                # TODO: use --dry-run or --download-only instead
                if not (on_win and platform == context.subdir):
                    raise
            else:
                assert out
                assert not err
                assert rc == 0
