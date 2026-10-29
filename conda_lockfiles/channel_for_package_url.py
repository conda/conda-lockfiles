from __future__ import annotations

from typing import TYPE_CHECKING

from conda.models.channel import Channel

from . import CONDA_PYPI_CHANNEL_NAME, PYTHONHOSTED_URL_PREFIX

if TYPE_CHECKING:
    from collections.abc import Iterable


def base_urls(channel: str) -> tuple[str, ...]:
    """Expanded URLs that packages from this channel can start with."""
    parsed = Channel(channel)
    urls = [url for url in parsed.base_urls if url]
    if not urls and parsed.base_url:
        urls = [parsed.base_url]
    if not urls:
        urls = [channel]
    return tuple(url.rstrip("/") for url in urls)


def channel_for_package_url(package_url: str, channels: Iterable[str]) -> str | None:
    """Return which lockfile channel this package came from.

    A package URL is matched against each channel's base URL.
    Example: Package ``file:///.../local-pypi/profiletools/foo.whl`` belongs
    to channel ``file:///.../local-pypi``.

    Wheels from ``https://files.pythonhosted.org/`` do not start with
    the ``conda-pypi`` channel URL. If the lockfile lists ``conda-pypi``,
    that channel is used instead.

    If nothing matches, return None.
    """
    conda_pypi_channel = None
    for channel in channels:
        if Channel(channel).canonical_name == CONDA_PYPI_CHANNEL_NAME:
            conda_pypi_channel = channel
        for base in base_urls(channel):
            if package_url == base or package_url.startswith(base + "/"):
                return channel
    if conda_pypi_channel and package_url.startswith(PYTHONHOSTED_URL_PREFIX):
        return conda_pypi_channel
    return None