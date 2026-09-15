"""Read user-requested specs from a conda prefix via conda-meta/history.

Upstream ``conda.models.environment.Environment.from_prefix()`` defaults to
``from_history=False``, which populates ``Environment.requested_packages``
with a ``MatchSpec`` for *every* installed ``PrefixRecord`` rather than
user intent. ``conda export`` likewise only passes ``from_history=True``
when the user supplies ``--from-history`` on the CLI.

Our exporters want actual user intent regardless of that CLI flag, so we
re-derive from ``conda-meta/history`` ourselves. Tracked upstream at
https://github.com/conda/conda/issues/15961.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from conda.history import History

if TYPE_CHECKING:
    from conda.common.path import PathType


def requested_specs_from_prefix(prefix: PathType | None) -> list[str]:
    """Return user-requested specs recorded in ``prefix``'s history.

    Returns an empty list when ``prefix`` is falsy, does not exist, or has
    no ``conda-meta/history`` file. Specs are returned as canonical
    ``MatchSpec`` string form (``str(MatchSpec)``), sorted by package name
    for stable output.
    """
    if not prefix:
        return []
    prefix_path = Path(prefix)
    if not (prefix_path / "conda-meta" / "history").is_file():
        return []
    specs_map = History(str(prefix_path)).get_requested_specs_map()
    return sorted(str(spec) for spec in specs_map.values())
