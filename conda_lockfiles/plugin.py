from __future__ import annotations

from typing import TYPE_CHECKING

from conda.plugins import hookimpl, types
from conda.plugins.types import (
    CondaEnvironmentExporter,
    CondaEnvironmentSpecifier,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


@hookimpl
def conda_environment_specifiers() -> Iterable[CondaEnvironmentSpecifier]:
    from .conda_lock import v1 as conda_lock_v1
    from .rattler_lock import v6 as rattler_lock_v6

    for module, loader, description in (
        (
            conda_lock_v1,
            conda_lock_v1.CondaLockV1Loader,
            "Multi-platform lockfile format with exact package versions",
        ),
        (
            rattler_lock_v6,
            rattler_lock_v6.RattlerLockV6Loader,
            "Rattler-based lockfile format from pixi",
        ),
    ):
        options = {}
        if "aliases" in CondaEnvironmentSpecifier.__dataclass_fields__:
            options.update(
                aliases=module.ALIASES, default_filenames=module.DEFAULT_FILENAMES
            )
        if hasattr(types, "EnvironmentFormat"):
            options.update(
                description=description,
                environment_format=types.EnvironmentFormat.lockfile,
            )
        yield CondaEnvironmentSpecifier(
            name=module.FORMAT, environment_spec=loader, **options
        )


@hookimpl
def conda_environment_exporters() -> Iterable[CondaEnvironmentExporter]:
    from .conda_lock import v1 as conda_lock_v1
    from .rattler_lock import v6 as rattler_lock_v6

    for module, description in (
        (conda_lock_v1, "Multi-platform lockfile format with exact package versions"),
        (rattler_lock_v6, "Rattler-based lockfile format from pixi"),
    ):
        options = {}
        if hasattr(types, "EnvironmentFormat"):
            options.update(
                description=description,
                environment_format=types.EnvironmentFormat.lockfile,
            )
        yield CondaEnvironmentExporter(
            name=module.FORMAT,
            aliases=module.ALIASES,
            default_filenames=module.DEFAULT_FILENAMES,
            multiplatform_export=module.multiplatform_export,
            **options,
        )
