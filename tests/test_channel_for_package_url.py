from __future__ import annotations

from conda_lockfiles.channel_for_package_url import channel_for_package_url

LOCAL = "file:///tmp/local-pypi"


def test_channel_for_package_url() -> None:
    channels = ("conda-forge", LOCAL)
    assert (
        channel_for_package_url(
            f"{LOCAL}/noarch/profiletools-0.2.0-py3-none-any.whl",
            channels,
        )
        == LOCAL
    )
    assert (
        channel_for_package_url(
            f"{LOCAL}/profiletools/profiletools-0.2.0-py3-none-any.whl",
            channels,
        )
        == LOCAL
    )
