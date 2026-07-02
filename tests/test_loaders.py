from __future__ import annotations

import warnings
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from conda.base.context import context
from conda.plugins.types import EnvironmentFormat

if TYPE_CHECKING:
    from conda.plugins.manager import CondaPluginManager

from conda_lockfiles.conda_lock import v1 as conda_lock_v1
from conda_lockfiles.rattler_lock import v6 as rattler_lock_v6
from conda_lockfiles.rattler_lock import v7 as rattler_lock_v7

from . import CONDA_LOCK_METADATA_DIR, PIXI_V6_METADATA_DIR, PIXI_V7_METADATA_DIR

CONDA_LOCK_METADATA_BUILDS = {
    "linux-64": "hee588c1_0",
    "osx-64": "hdb6dae5_0",
    "osx-arm64": "h3f77e49_0",
    "win-64": "h67fdade_0",
}

CONDA_LOCK_METADATA_SHA256 = {
    "linux-64": "b3dcd409c96121c011387bdf7f4b5758d876feeb9d8e3cfc32285b286931d0a7",
    "osx-64": "e88ea982455060b96fdab3d360b947389248bf2139e3b17576e4c72e139526fc",
    "osx-arm64": "80bbe9c53d4bf2e842eccdd089653d0659972deba7057cda3ebaebaf43198f79",
    "win-64": "92546e3ea213ee7b11385b22ea4e7c69bbde1c25586288765b37bc5e96b20dd9",
}

CONDA_LOCK_METADATA_MD5 = {
    "linux-64": "71888e92098d0f8c41b09a671ad289bc",
    "osx-64": "caf16742f7e16475603cd9981ef36195",
    "osx-arm64": "cda0ec640bc4698d0813a8fb459aee58",
    "win-64": "92b11b0b2120d563caa1629928122cee",
}

PIXI_ALIAS_WARNING = (
    "'pixi' currently resolves to rattler-lock-v6 and will resolve to rattler-lock-v7"
)


@contextmanager
def expect_alias_warning(alias: str):
    if alias == "pixi":
        with pytest.warns(PendingDeprecationWarning, match=PIXI_ALIAS_WARNING):
            yield
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("error", PendingDeprecationWarning)
            yield


@pytest.mark.parametrize(
    "format_name,expected_description",
    [
        (
            conda_lock_v1.FORMAT,
            "Multi-platform lockfile format with exact package versions",
        ),
        (
            rattler_lock_v6.FORMAT,
            "Rattler-based lockfile format from pixi",
        ),
        (
            rattler_lock_v7.FORMAT,
            "Rattler-based lockfile format from pixi (v7)",
        ),
    ],
)
def test_specifier_plugin_metadata(
    plugin_manager: CondaPluginManager,
    format_name: str,
    expected_description: str,
) -> None:
    specifiers = plugin_manager.get_environment_specifiers()
    specifier = specifiers.get(format_name)
    assert specifier is not None
    assert specifier.description == expected_description
    assert specifier.environment_format == EnvironmentFormat.lockfile


@pytest.mark.parametrize(
    "format_name,expected_description",
    [
        (
            conda_lock_v1.FORMAT,
            "Multi-platform lockfile format with exact package versions",
        ),
        (
            rattler_lock_v6.FORMAT,
            "Rattler-based lockfile format from pixi",
        ),
        (
            rattler_lock_v7.FORMAT,
            "Rattler-based lockfile format from pixi (v7)",
        ),
    ],
)
def test_exporter_plugin_metadata(
    plugin_manager: CondaPluginManager,
    format_name: str,
    expected_description: str,
) -> None:
    exporter = plugin_manager.get_environment_exporter_by_format(format_name)
    assert exporter is not None
    assert exporter.description == expected_description
    assert exporter.environment_format == EnvironmentFormat.lockfile


@pytest.mark.parametrize(
    "alias,canonical_format",
    [
        ("conda-lock", conda_lock_v1.FORMAT),
        ("pixi-lock-v6", rattler_lock_v6.FORMAT),
        ("pixi", rattler_lock_v6.FORMAT),
        ("pixi-lock-v7", rattler_lock_v7.FORMAT),
    ],
)
def test_specifier_alias_resolves(
    plugin_manager: CondaPluginManager,
    alias: str,
    canonical_format: str,
) -> None:
    """Aliases resolve to the same plugin as the canonical format name."""
    specifiers = plugin_manager.get_environment_specifiers()
    with expect_alias_warning(alias):
        specifier = specifiers[alias]
    assert specifier.name == canonical_format


@pytest.mark.parametrize(
    "alias,canonical_format",
    [
        ("conda-lock", conda_lock_v1.FORMAT),
        ("pixi-lock-v6", rattler_lock_v6.FORMAT),
        ("pixi", rattler_lock_v6.FORMAT),
        ("pixi-lock-v7", rattler_lock_v7.FORMAT),
    ],
)
def test_exporter_alias_resolves(
    plugin_manager: CondaPluginManager,
    alias: str,
    canonical_format: str,
) -> None:
    """`conda export --format <alias>` resolves to the canonical exporter."""
    with expect_alias_warning(alias):
        exporter = plugin_manager.get_environment_exporter_by_format(alias)
    assert exporter is not None
    assert exporter.name == canonical_format


@pytest.mark.parametrize(
    "format_name",
    [
        rattler_lock_v6.FORMAT,
        "pixi-lock-v6",
    ],
)
def test_pinned_rattler_lock_v6_names_do_not_warn(
    plugin_manager: CondaPluginManager,
    format_name: str,
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", PendingDeprecationWarning)
        assert plugin_manager.get_exporter_format_mapping()[format_name].name == (
            rattler_lock_v6.FORMAT
        )


def test_create_environment_from_conda_lock_v1(
    plugin_manager: CondaPluginManager,
) -> None:
    path = CONDA_LOCK_METADATA_DIR / conda_lock_v1.CONDA_LOCK_FILE
    loader = plugin_manager.get_environment_specifier(
        path,
        conda_lock_v1.FORMAT,
    )
    assert loader.name == conda_lock_v1.FORMAT
    assert loader.environment_spec == conda_lock_v1.CondaLockV1Loader

    spec = loader.environment_spec(path)
    assert spec.can_handle()
    assert spec.env
    assert spec.env.prefix == context.target_prefix
    assert spec.env.platform == context.subdir
    assert not spec.env.requested_packages
    assert not spec.env.external_packages

    explicit_packages = spec.env.explicit_packages
    # each platform may have a different number of packages
    assert explicit_packages

    pkg = next(pkg for pkg in explicit_packages if pkg.name == "libsqlite")
    assert pkg.name == "libsqlite"
    assert pkg.version == "3.50.0"
    assert pkg.build == CONDA_LOCK_METADATA_BUILDS[context.subdir]
    assert pkg.sha256 == CONDA_LOCK_METADATA_SHA256[context.subdir]
    assert pkg.md5 == CONDA_LOCK_METADATA_MD5[context.subdir]
    assert pkg.depends == ("ONLY_IN_LOCKFILE 0",)


def test_create_environment_from_rattler_lock_v6(
    plugin_manager: CondaPluginManager,
) -> None:
    path = PIXI_V6_METADATA_DIR / rattler_lock_v6.PIXI_LOCK_FILE
    loader = plugin_manager.get_environment_specifier(
        path,
        rattler_lock_v6.FORMAT,
    )
    assert loader.name == rattler_lock_v6.FORMAT
    assert loader.environment_spec == rattler_lock_v6.RattlerLockV6Loader

    spec = loader.environment_spec(path)
    assert spec.can_handle()
    assert spec.env
    assert spec.env.prefix == context.target_prefix
    assert spec.env.platform == context.subdir
    assert not spec.env.requested_packages
    assert not spec.env.external_packages

    explicit_packages = spec.env.explicit_packages
    assert len(explicit_packages) == 1

    pkg = explicit_packages[0]
    assert pkg.name == "tzdata"
    assert pkg.version == "2025b"
    assert pkg.build == "h78e105d_0"
    assert pkg.build_number == 0
    assert (
        pkg.sha256 == "5aaa366385d716557e365f0a4e9c3fca43ba196872abbbe3d56bb610d131e192"
    )
    assert pkg.md5 == "4222072737ccff51314b5ece9c7d6f5a"
    assert pkg.license == "ONLY_IN_LOCKFILE"
    assert pkg.size == 122968
    assert pkg.timestamp == 1742727099.393


def test_create_environment_from_rattler_lock_v7(
    plugin_manager: CondaPluginManager,
) -> None:
    path = PIXI_V7_METADATA_DIR / rattler_lock_v7.PIXI_LOCK_FILE
    loader = plugin_manager.get_environment_specifier(
        path,
        rattler_lock_v7.FORMAT,
    )
    assert loader.name == rattler_lock_v7.FORMAT
    assert loader.environment_spec == rattler_lock_v7.RattlerLockV7Loader

    spec = loader.environment_spec(path)
    assert spec.can_handle()
    assert spec.env
    assert spec.env.prefix == context.target_prefix
    assert not spec.env.requested_packages
    assert not spec.env.external_packages

    explicit_packages = spec.env.explicit_packages
    assert len(explicit_packages) == 1

    pkg = explicit_packages[0]
    assert pkg.name == "tzdata"
    assert pkg.version == "2025b"
    assert pkg.build == "h78e105d_0"
    assert (
        pkg.sha256 == "5aaa366385d716557e365f0a4e9c3fca43ba196872abbbe3d56bb610d131e192"
    )
    assert pkg.md5 == "4222072737ccff51314b5ece9c7d6f5a"
    assert pkg.license == "ONLY_IN_LOCKFILE"
    assert pkg.size == 122968


EXPECTED_PLATFORMS = ("linux-64", "osx-64", "osx-arm64", "win-64")


@pytest.fixture(
    params=[
        pytest.param(
            (
                conda_lock_v1.CondaLockV1Loader,
                CONDA_LOCK_METADATA_DIR / conda_lock_v1.CONDA_LOCK_FILE,
            ),
            id="conda-lock-v1",
        ),
        pytest.param(
            (
                rattler_lock_v6.RattlerLockV6Loader,
                PIXI_V6_METADATA_DIR / rattler_lock_v6.PIXI_LOCK_FILE,
            ),
            id="rattler-lock-v6",
        ),
        pytest.param(
            (
                rattler_lock_v7.RattlerLockV7Loader,
                PIXI_V7_METADATA_DIR / rattler_lock_v7.PIXI_LOCK_FILE,
            ),
            id="rattler-lock-v7",
        ),
    ],
)
def loader(request):
    cls, path = request.param
    spec = cls(path)
    spec.can_handle()
    return spec


def test_available_platforms(loader) -> None:
    assert loader.available_platforms == EXPECTED_PLATFORMS


@pytest.mark.parametrize("platform", EXPECTED_PLATFORMS)
def test_env_for(loader, platform) -> None:
    env = loader.env_for(platform)
    assert env.platform == platform
    assert env.explicit_packages


def test_env_for_unknown_platform_raises(loader) -> None:
    with pytest.raises(ValueError, match="not in lockfile"):
        loader.env_for("not-a-real-platform")


def test_env_unchanged(loader) -> None:
    """Regression guard: env still returns a single Environment for context.subdir."""
    env = loader.env
    assert env.platform == context.subdir
    assert env.explicit_packages
