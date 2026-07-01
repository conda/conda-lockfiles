from __future__ import annotations

import warnings
from dataclasses import dataclass

from conda.plugins.types import (
    CondaEnvironmentExporter,
    CondaEnvironmentSpecifier,
    CondaPlugin,
    PluginError,
)

_WARNED_ONCE: set[tuple[str, str, type[Warning]]] = set()


class WarningAlias(str):
    """String alias that warns when conda resolves it through a mapping lookup."""

    def __new__(
        cls,
        value: str,
        *,
        message: str,
        category: type[Warning],
        once: bool = False,
    ) -> WarningAlias:
        alias = super().__new__(cls, value)
        alias._message = message
        alias._category = category
        alias._once = once
        return alias

    def __eq__(self, other: object) -> bool:
        matches = super().__eq__(other)
        if matches and not isinstance(other, WarningAlias):
            self._warn()
        return matches

    def __hash__(self) -> int:
        return super().__hash__()

    def _warn(self) -> None:
        key = (str(self), self._message, self._category)
        if self._once and key in _WARNED_ONCE:
            return

        warnings.warn(self._message, self._category, stacklevel=4)
        if self._once:
            _WARNED_ONCE.add(key)


def pending_alias_binding_warning(
    alias: str,
    *,
    current: str,
    future: str,
    flip_release: str,
) -> WarningAlias:
    return WarningAlias(
        alias,
        message=(
            f"{alias!r} currently resolves to {current} and will resolve to "
            f"{future} in {flip_release}. Pin --format {current} to keep "
            "writing v6 after the flip."
        ),
        category=PendingDeprecationWarning,
    )


def flipped_alias_binding_warning(
    alias: str,
    *,
    current: str,
    previous: str,
) -> WarningAlias:
    return WarningAlias(
        alias,
        message=(
            f"{alias!r} now resolves to {current} (was {previous} in the "
            f"previous release). Pin --format {previous} if you need the old "
            "format."
        ),
        category=DeprecationWarning,
        once=True,
    )


def _normalize_aliases(aliases: tuple[str, ...]) -> tuple[str, ...]:
    try:
        return tuple(
            dict.fromkeys(
                alias if isinstance(alias, WarningAlias) else alias.lower().strip()
                for alias in aliases
            )
        )
    except AttributeError as exc:
        raise PluginError("Invalid plugin aliases") from exc


@dataclass
class CondaLockfilesEnvironmentExporter(CondaEnvironmentExporter):
    """Conda exporter plugin that preserves warning-capable alias strings."""

    def __post_init__(self):
        CondaPlugin.__post_init__(self)
        self.aliases = _normalize_aliases(self.aliases)

        if bool(self.export) == bool(self.multiplatform_export):
            raise PluginError(
                "Exactly one of export or multiplatform_export must be set "
                f"for {self!r}"
            )

        if self.description is None:
            self.description = self.name


@dataclass
class CondaLockfilesEnvironmentSpecifier(CondaEnvironmentSpecifier):
    """Conda specifier plugin that preserves warning-capable alias strings."""

    def __post_init__(self):
        CondaPlugin.__post_init__(self)
        self.aliases = _normalize_aliases(self.aliases)

        if self.description is None:
            self.description = self.name
