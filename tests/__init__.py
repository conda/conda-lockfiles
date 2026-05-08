from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from conda.common.serialize import yaml_safe_load

if TYPE_CHECKING:
    from typing import Any, TypedDict

    from conda_lockfiles.conda_lock.v1 import (
        CondaLockV1MetadataType,
        CondaLockV1PackageType,
    )

    class CondaLockV1Data(TypedDict):
        version: int
        metadata: CondaLockV1MetadataType
        package: list[CondaLockV1PackageType]


DATA_DIR = Path(__file__).parent / "data"

# mock channel
CHANNEL_DIR = DATA_DIR / "channel"
RECIPES_DIR = DATA_DIR / "recipes"

# lockfiles
PIXI_DIR = DATA_DIR / "pixi"
PIXI_V6_METADATA_DIR = DATA_DIR / "pixi-v6-metadata"
PIXI_V7_METADATA_DIR = DATA_DIR / "pixi-v7-metadata"
CONDA_LOCK_METADATA_DIR = DATA_DIR / "conda-lock-metadata"
INVALID_LOCKFILES_DIR = DATA_DIR / "invalid-lockfiles"

# Enviroments
ENVIRONMENTS_DIR = DATA_DIR / "environments"
SINGLE_PACKAGE_ENV = ENVIRONMENTS_DIR / "single_package"
SINGLE_PACKAGE_NO_URL_ENV = ENVIRONMENTS_DIR / "single_package_no_url"


RE_CREATED_BY = re.compile(r"created_by: conda-lockfiles .+")
RE_CREATED_AT = re.compile(r"created_at: .+")


def normalize_conda_lock_v1(text: str) -> CondaLockV1Data:
    data = yaml_safe_load(text)
    data["metadata"]["custom_metadata"]["created_by"] = "conda-lockfiles VERSION"
    data["metadata"]["time_metadata"]["created_at"] = "TIMESTAMP"
    return data


def compare_conda_lock_v1(lockfile: Path, reference: Path) -> Any:
    lockfile_data = normalize_conda_lock_v1(lockfile.read_text())
    reference_data = normalize_conda_lock_v1(reference.read_text())
    return lockfile_data == reference_data


def compare_rattler_lock_v6(lockfile: Path, reference: Path) -> Any:
    lockfile_data = yaml_safe_load(lockfile.read_text())
    reference_data = yaml_safe_load(reference.read_text())
    return lockfile_data == reference_data


def compare_rattler_lock_v7(lockfile: Path, reference: Path) -> Any:
    lockfile_data = yaml_safe_load(lockfile.read_text())
    reference_data = yaml_safe_load(reference.read_text())
    return lockfile_data == reference_data
