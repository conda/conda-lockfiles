from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from conda.exceptions import CondaValueError
from conda.plugins.types import EnvironmentSpecBase

from .plugin import conda_environment_exporters

if TYPE_CHECKING:
    from collections.abc import Iterable

    from conda.models.environment import Environment


class LockfileSpecBase(EnvironmentSpecBase):
    """Base class for lockfile environment specifiers."""

    @property
    @abstractmethod
    def available_platforms(self) -> tuple[str, ...]:
        """Platforms declared in the lockfile."""

    def transcode(
        self,
        platforms: Iterable[str],
        *,
        format_name: str,
    ) -> str:
        """Render selected platforms without fetching package artifacts."""
        requested = tuple(platforms)
        if not requested:
            raise CondaValueError("At least one platform is required for transcoding.")
        available = self.available_platforms
        missing = sorted(set(requested) - set(available))
        if missing:
            raise CondaValueError(
                f"Platform(s) not in lockfile: {', '.join(missing)}. "
                f"Available platforms: {', '.join(available)}"
            )
        exporter = next(
            (
                exporter
                for exporter in conda_environment_exporters()
                if format_name in (exporter.name, *exporter.aliases)
            ),
            None,
        )
        if exporter is None or exporter.multiplatform_export is None:
            raise CondaValueError(
                f"Unsupported lockfile transcode format: {format_name}"
            )
        environments = self._environments_for_transcode(requested, exporter.name)
        return exporter.multiplatform_export(environments)

    @abstractmethod
    def _environments_for_transcode(
        self,
        platforms: tuple[str, ...],
        target_format: str,
    ) -> Iterable[Environment]:
        """Build exporter-compatible environments without fetching packages."""
