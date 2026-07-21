from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conda.base.context import context
from conda.exceptions import CondaValueError
from conda.plugins.types import EnvironmentFormat

if TYPE_CHECKING:
    from conda.plugins.manager import CondaPluginManager
    from pytest_mock import MockerFixture

from conda_lockfiles.conda_lock import v1 as conda_lock_v1
from conda_lockfiles.rattler_lock import v6 as rattler_lock_v6

from . import CONDA_LOCK_METADATA_DIR, PIXI_METADATA_DIR

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

PYTHONHOSTED_WHEEL_URL = (
    "https://files.pythonhosted.org/packages/ab/cd/langfuse-4.6.1-py3-none-any.whl"
)
PYTHONHOSTED_WHEEL_MD5 = "0123456789abcdef0123456789abcdef"
PYTHONHOSTED_WHEEL_SHA256 = (
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


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
    ],
)
def test_specifier_alias_resolves(
    plugin_manager: CondaPluginManager,
    alias: str,
    canonical_format: str,
) -> None:
    """Aliases resolve to the same plugin as the canonical format name."""
    specifiers = plugin_manager.get_environment_specifiers()
    assert alias in specifiers
    assert specifiers[alias].name == canonical_format


@pytest.mark.parametrize(
    "alias,canonical_format",
    [
        ("conda-lock", conda_lock_v1.FORMAT),
        ("pixi-lock-v6", rattler_lock_v6.FORMAT),
        ("pixi", rattler_lock_v6.FORMAT),
    ],
)
def test_exporter_alias_resolves(
    plugin_manager: CondaPluginManager,
    alias: str,
    canonical_format: str,
) -> None:
    """`conda export --format <alias>` resolves to the canonical exporter."""
    exporter = plugin_manager.get_environment_exporter_by_format(alias)
    assert exporter is not None
    assert exporter.name == canonical_format


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
    path = PIXI_METADATA_DIR / rattler_lock_v6.PIXI_LOCK_FILE
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
                PIXI_METADATA_DIR / rattler_lock_v6.PIXI_LOCK_FILE,
            ),
            id="rattler-lock-v6",
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


def test_env_for_export_does_not_fetch(loader, mocker: MockerFixture) -> None:
    execute = mocker.patch(
        "conda.core.package_cache_data.ProgressiveFetchExtract.execute",
        side_effect=AssertionError("package fetch attempted"),
    )

    env = loader.env_for(context.subdir, export=True)

    execute.assert_not_called()
    assert env.platform == context.subdir
    assert env.explicit_packages


@pytest.mark.parametrize("export", [False, True], ids=["install", "export"])
def test_env_for_unknown_platform_raises(loader, export: bool) -> None:
    with pytest.raises(ValueError, match="not in lockfile"):
        loader.env_for("not-a-real-platform", export=export)


def test_env_unchanged(loader) -> None:
    """Regression guard: env still returns a single Environment for context.subdir."""
    env = loader.env
    assert env.platform == context.subdir
    assert env.explicit_packages


def test_rattler_lock_v6_rejects_missing_package_metadata() -> None:
    url = "https://example.com/linux-64/example-1.0-0.conda"
    lockfile = rattler_lock_v6.RattlerLockV6(
        environments={
            "default": rattler_lock_v6.RattlerLockV6Environment(
                channels=[],
                packages={
                    "linux-64": [
                        rattler_lock_v6.RattlerLockV6PackageReference(conda=url)
                    ]
                },
            )
        },
        packages=[],
    )

    with pytest.raises(CondaValueError, match="missing from the packages list"):
        rattler_lock_v6.rattler_lock_v6_to_conda_env(
            lockfile,
            platform="linux-64",
            fetch=False,
        )


@pytest.mark.parametrize(
    "module,lockfile,load_env,expected_overrides",
    [
        pytest.param(
            conda_lock_v1,
            conda_lock_v1.CondaLockV1(
                metadata=conda_lock_v1.CondaLockV1Metadata(
                    channels=[
                        conda_lock_v1.CondaLockV1Channel(url="main"),
                        conda_lock_v1.CondaLockV1Channel(url="conda-pypi"),
                    ],
                    platforms=["osx-arm64"],
                ),
                package=[
                    conda_lock_v1.CondaLockV1Package(
                        name="langfuse",
                        version="4.6.1",
                        manager="conda",
                        platform="osx-arm64",
                        dependencies={"protobuf": ">=6"},
                        url=PYTHONHOSTED_WHEEL_URL,
                        hash=conda_lock_v1.CondaLockV1Hash(
                            md5=PYTHONHOSTED_WHEEL_MD5,
                            sha256=PYTHONHOSTED_WHEEL_SHA256,
                        ),
                    )
                ],
            ),
            conda_lock_v1.conda_lock_v1_to_conda_env,
            {
                "channel": "conda-pypi",
                "depends": ["protobuf >=6"],
                "md5": PYTHONHOSTED_WHEEL_MD5,
                "name": "langfuse",
                "sha256": PYTHONHOSTED_WHEEL_SHA256,
                "version": "4.6.1",
            },
            id="conda-lock-v1",
        ),
        pytest.param(
            rattler_lock_v6,
            rattler_lock_v6.RattlerLockV6(
                environments={
                    "default": rattler_lock_v6.RattlerLockV6Environment(
                        channels=[
                            rattler_lock_v6.RattlerLockV6Channel(url="main"),
                            rattler_lock_v6.RattlerLockV6Channel(url="conda-pypi"),
                        ],
                        packages={
                            "osx-arm64": [
                                rattler_lock_v6.RattlerLockV6PackageReference(
                                    conda=PYTHONHOSTED_WHEEL_URL,
                                )
                            ]
                        },
                    )
                },
                packages=[
                    rattler_lock_v6.RattlerLockV6Package(
                        conda=PYTHONHOSTED_WHEEL_URL,
                        md5=PYTHONHOSTED_WHEEL_MD5,
                        sha256=PYTHONHOSTED_WHEEL_SHA256,
                        depends=["python >=3.14"],
                        license="MIT",
                    )
                ],
            ),
            rattler_lock_v6.rattler_lock_v6_to_conda_env,
            {
                "channel": "conda-pypi",
                "depends": ["python >=3.14"],
                "license": "MIT",
                "md5": PYTHONHOSTED_WHEEL_MD5,
                "sha256": PYTHONHOSTED_WHEEL_SHA256,
            },
            id="rattler-lock-v6",
        ),
    ],
)
def test_conda_pypi_record_overrides(
    module,
    lockfile,
    load_env,
    expected_overrides,
    mocker: MockerFixture,
) -> None:
    """Loaders preserve wheel metadata in full and export-only records."""
    captured_calls = []

    def capture_records(metadata_by_url, **kwargs):
        captured_calls.append((metadata_by_url, kwargs))
        return ()

    mocker.patch.object(
        module,
        "records_from_conda_urls",
        side_effect=capture_records,
    )

    load_env(lockfile, platform="osx-arm64")
    load_env(lockfile, platform="osx-arm64", fetch=False)

    assert captured_calls[0][0][PYTHONHOSTED_WHEEL_URL] == expected_overrides
    assert captured_calls[0][1]["fetch"] is True
    assert captured_calls[1][0][PYTHONHOSTED_WHEEL_URL] == {
        **expected_overrides,
        "build": "py3_none_any_0",
        "subdir": "noarch",
    }
    assert captured_calls[1][1]["fetch"] is False
