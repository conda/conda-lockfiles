from __future__ import annotations

from typing import TYPE_CHECKING

from conda.common.url import urlparse
from conda.models.channel import Channel

from . import CONDA_PYPI_CHANNEL_NAME, PYTHONHOSTED_URL_PREFIX

if TYPE_CHECKING:
    from collections.abc import Iterable


def base_urls(channel: str) -> tuple[str, ...]:
    """Expanded URLs that packages from this channel can start with."""
    return tuple(
        base.rstrip("/") for base in Channel(channel).base_urls if base
    )


def channel_for_package_url(package_url: str, channels: Iterable[str]) -> str | None:
    """Return the most specific lockfile channel for a wheel URL, or None.

    Ordinary conda archives keep the channel from their package records.
    Wheels hosted on files.pythonhosted.org use the listed conda-pypi
    channel when no channel URL matches.
    """
    if not (urlparse(package_url).path or "").endswith(".whl"):
        return None

    normalized_url = Channel(package_url).base_url or package_url
    matched_channel = None
    matched_length = -1
    conda_pypi_channel = None
    for channel in channels:
        if Channel(channel).canonical_name == CONDA_PYPI_CHANNEL_NAME:
            conda_pypi_channel = channel
        for base in base_urls(channel):
            if len(base) > matched_length and (
                normalized_url == base or normalized_url.startswith(base + "/")
            ):
                matched_channel = channel
                matched_length = len(base)
    if matched_channel is not None:
        return matched_channel
    if conda_pypi_channel and package_url.startswith(PYTHONHOSTED_URL_PREFIX):
        return conda_pypi_channel
    return None