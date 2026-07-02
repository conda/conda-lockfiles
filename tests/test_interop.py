"""Cross-tool interop tests.

Validate that lockfiles exported by conda-lockfiles can be consumed by the
tools they originated from: pixi for rattler-lock-v6, conda-lock for
conda-lock-v1. Addresses the "and other tools" part of issue #9.

Tests are marked ``interop`` and skipped automatically when the external
tool is not on PATH so local pytest runs stay green without extra setup.
CI installs both tools and runs the full set.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from conda_lockfiles.conda_lock import v1 as conda_lock_v1
from conda_lockfiles.rattler_lock import v6 as rattler_lock_v6
from conda_lockfiles.rattler_lock import v7 as rattler_lock_v7

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Callable

    from conda.testing.fixtures import (
        CondaCLIFixture,
        TmpEnvFixture,
    )


pytestmark = pytest.mark.interop


# A single, small, broadly-available package keeps these tests fast and
# avoids flakiness from the solver picking different builds across
# platforms. zlib is what the existing round-trip tests already use.
INTEROP_PACKAGE = "zlib"


@pytest.fixture
def require_tool() -> Callable[[str], str]:
    """Return a helper that resolves a tool on PATH or skips the test."""

    def _require(tool: str) -> str:
        path = shutil.which(tool)
        if path is None:
            pytest.skip(f"{tool} not on PATH")
        return path

    return _require


# Each case: (lockfile format, export filename, consumer tool binary).
# Filenames matter: conda-lock's unified-format parser requires the
# ``.conda-lock.yml`` double extension; pixi wants the file literally
# named ``pixi.lock``.
@pytest.mark.parametrize(
    "lock_format,filename,tool_name",
    [
        pytest.param(
            rattler_lock_v6.FORMAT,
            rattler_lock_v6.PIXI_LOCK_FILE,
            "pixi",
            id="pixi-consumes-rattler-lock-v6",
        ),
        pytest.param(
            rattler_lock_v7.FORMAT,
            rattler_lock_v7.PIXI_LOCK_FILE,
            "pixi",
            id="pixi-consumes-rattler-lock-v7",
        ),
        pytest.param(
            conda_lock_v1.FORMAT,
            "interop.conda-lock.yml",
            "conda-lock",
            id="conda-lock-consumes-conda-lock-v1",
        ),
    ],
)
def test_external_tool_consumes_our_export(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    tmp_path: Path,
    require_tool: Callable[[str], str],
    lock_format: str,
    filename: str,
    tool_name: str,
) -> None:
    """Our export must be installable by the tool that owns the format."""
    tool = require_tool(tool_name)

    workdir = tmp_path / tool_name
    workdir.mkdir()
    lockfile = workdir / filename

    # Export a small env via our plugin.
    with tmp_env(INTEROP_PACKAGE) as prefix:
        out, err, rc = conda_cli(
            "export",
            f"--prefix={prefix}",
            f"--format={lock_format}",
            f"--file={lockfile}",
        )
        assert rc == 0, (out, err)

    # Hand the lockfile to the consumer tool. Invocation differs per tool
    # because the tools expose very different install interfaces: pixi
    # installs a workspace (manifest + lockfile) in --frozen mode, while
    # conda-lock installs a lockfile directly into a prefix.
    if tool_name == "pixi":
        (workdir / "pixi.toml").write_text(
            "[workspace]\n"
            'name = "interop"\n'
            'channels = ["conda-forge"]\n'
            'platforms = ["linux-64", "osx-64", "osx-arm64", "win-64"]\n'
            "\n"
            "[dependencies]\n"
            f'{INTEROP_PACKAGE} = "*"\n'
        )
        argv = [
            tool,
            "install",
            "--frozen",
            "--manifest-path",
            str(workdir / "pixi.toml"),
        ]
        consumed_prefix = workdir / ".pixi" / "envs" / "default"
    elif tool_name == "conda-lock":
        consumed_prefix = workdir / "consumed"
        argv = [tool, "install", "--prefix", str(consumed_prefix), str(lockfile)]
    else:
        raise AssertionError(f"unhandled tool {tool_name!r}")

    result = subprocess.run(argv, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{tool_name} install failed\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    conda_meta = consumed_prefix / "conda-meta"
    assert conda_meta.is_dir(), f"{tool_name} did not create {conda_meta}"
    assert any(
        entry.name.startswith(f"{INTEROP_PACKAGE}-") and entry.suffix == ".json"
        for entry in conda_meta.iterdir()
    ), f"{INTEROP_PACKAGE} not recorded in {conda_meta}"
