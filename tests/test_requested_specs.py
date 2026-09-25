"""Round-trip tests for user-requested specs in exported lockfiles.

Covers issue #8: exports include specs from the prefix's
``conda-meta/history``, and loaders populate ``Environment.requested_packages``
from that data.
"""

from __future__ import annotations

import json

from conda_lockfiles.conda_lock.v1 import (
    CONDA_LOCK_FILE,
    REQUESTED_SPECS_KEY,
    CondaLockV1Loader,
)
from conda_lockfiles.history import requested_specs_from_prefix
from conda_lockfiles.load_yaml import load_yaml
from conda_lockfiles.rattler_lock.v6 import PIXI_LOCK_FILE, RattlerLockV6Loader

from . import SINGLE_PACKAGE_ENV


def test_requested_specs_from_prefix_reads_history() -> None:
    """``requested_specs_from_prefix`` returns history-recorded specs."""
    specs = requested_specs_from_prefix(SINGLE_PACKAGE_ENV)
    assert specs == ["python_abi"]


def test_requested_specs_from_prefix_missing_prefix(tmp_path) -> None:
    """Missing prefix or missing history file returns an empty list."""
    assert requested_specs_from_prefix(None) == []
    assert requested_specs_from_prefix(tmp_path / "does-not-exist") == []
    assert requested_specs_from_prefix(tmp_path) == []  # exists, no history


def test_conda_lock_v1_fixture_contains_requested_specs() -> None:
    """Our reference fixture carries the spec string in custom_metadata."""
    data = load_yaml(SINGLE_PACKAGE_ENV / CONDA_LOCK_FILE)
    payload = data["metadata"]["custom_metadata"][REQUESTED_SPECS_KEY]
    assert json.loads(payload) == ["python_abi"]


def test_conda_lock_v1_loader_populates_requested_packages() -> None:
    """Loader decodes custom_metadata and yields a MatchSpec on the Environment."""
    loader = CondaLockV1Loader(SINGLE_PACKAGE_ENV / CONDA_LOCK_FILE)
    env = loader.env_for("linux-64")
    assert [str(ms) for ms in env.requested_packages] == ["python_abi"]


def test_rattler_lock_v6_fixture_contains_requested_packages() -> None:
    """Our reference fixture carries the per-platform spec list."""
    data = load_yaml(SINGLE_PACKAGE_ENV / PIXI_LOCK_FILE)
    env_block = data["environments"]["default"]
    assert env_block["requested-packages"] == {"linux-64": ["python_abi"]}


def test_rattler_lock_v6_loader_populates_requested_packages() -> None:
    loader = RattlerLockV6Loader(SINGLE_PACKAGE_ENV / PIXI_LOCK_FILE)
    env = loader.env_for("linux-64")
    assert [str(ms) for ms in env.requested_packages] == ["python_abi"]


def test_conda_lock_v1_loader_tolerates_invalid_requested_specs(tmp_path) -> None:
    """An unparseable ``requested_specs`` payload is dropped, not raised."""
    # Minimal lockfile with a malformed requested_specs value.
    lockfile = tmp_path / CONDA_LOCK_FILE
    url = "https://conda.anaconda.org/conda-forge/noarch/python_abi-3.13-7_cp313.conda"
    sha = "0595134584589064f56e67d3de1d8fcbb673a972946bce25fb593fb092fdcd97"
    lockfile.write_text(
        "version: 1\n"
        "metadata:\n"
        "  content_hash: {}\n"
        "  channels:\n"
        "    - url: conda-forge\n"
        "      used_env_vars: []\n"
        "  platforms: [linux-64]\n"
        "  sources: ['']\n"
        "  custom_metadata:\n"
        "    requested_specs: 'not-json'\n"
        "package:\n"
        "  - name: python_abi\n"
        "    version: '3.13'\n"
        "    manager: conda\n"
        "    platform: linux-64\n"
        "    dependencies: {}\n"
        f"    url: {url}\n"
        "    hash:\n"
        "      md5: e84b44e6300f1703cb25d29120c5b1d8\n"
        f"      sha256: {sha}\n"
        "    category: main\n"
        "    optional: false\n"
    )
    loader = CondaLockV1Loader(lockfile)
    env = loader.env_for("linux-64")
    assert env.requested_packages == []
