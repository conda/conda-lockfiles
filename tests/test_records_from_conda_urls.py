from __future__ import annotations

import pytest
from conda.base.context import reset_context
from conda.exceptions import CondaValueError, DryRunExit

from conda_lockfiles.records_from_conda_urls import records_from_conda_urls


def test_records_from_urls_and_metadata() -> None:
    md5 = "4222072737ccff51314b5ece9c7d6f5a"
    sha256 = "5aaa366385d716557e365f0a4e9c3fca43ba196872abbbe3d56bb610d131e192"
    license = "ONLY_IN_TEST"

    metadata_by_url = {
        "https://conda.anaconda.org/conda-forge/noarch/tzdata-2025b-h78e105d_0.conda": {
            "md5": md5,
            "sha256": sha256,
            "license": license,
        },
    }
    records = records_from_conda_urls(metadata_by_url)
    assert isinstance(records, tuple)
    assert len(records) == 1
    record = records[0]
    assert record.name == "tzdata"
    # set by passed metadata
    assert record.md5 == md5
    assert record.sha256 == sha256
    assert record.license == license
    # only known after downloading
    assert record.size == 122_968


def test_records_from_conda_urls_without_fetch(mocker) -> None:
    sha256 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    url = (
        "https://conda.anaconda.org/conda-forge/linux-64/"
        f"python-3.13.7-h4f43103_100_cp313.conda#sha256={sha256}"
    )
    metadata = {
        "depends": ["bzip2 >=1.0.8,<2.0a0"],
        "license": "Python-2.0",
        "md5": "0123456789abcdef0123456789abcdef",
        "sha256": sha256,
        "size": 42,
    }
    execute = mocker.patch(
        "conda.core.package_cache_data.ProgressiveFetchExtract.execute",
        side_effect=AssertionError("package fetch attempted"),
    )
    query_all = mocker.patch(
        "conda.core.package_cache_data.PackageCacheData.query_all",
        side_effect=AssertionError("package cache read attempted"),
    )

    records = records_from_conda_urls({url: metadata}, dry_run=True, fetch=False)

    execute.assert_not_called()
    query_all.assert_not_called()
    assert len(records) == 1
    assert records[0].dump() == {
        "name": "python",
        "version": "3.13.7",
        "build": "h4f43103_100_cp313",
        "build_number": 0,
        "channel": "https://conda.anaconda.org/conda-forge",
        "subdir": "linux-64",
        "fn": "python-3.13.7-h4f43103_100_cp313.conda",
        "md5": metadata["md5"],
        "url": url,
        "sha256": metadata["sha256"],
        "depends": ("bzip2 >=1.0.8,<2.0a0",),
        "constrains": (),
        "license": "Python-2.0",
        "size": 42,
    }


def test_records_from_wheel_url_without_fetch_preserves_distribution_name() -> None:
    url = (
        "https://files.pythonhosted.org/packages/ab/cd/"
        "typing_extensions-4.12.2-py3-none-any.whl"
    )

    (record,) = records_from_conda_urls(
        {
            url: {
                "build": "py3_none_any_0",
                "channel": "conda-pypi",
                "md5": "0123456789abcdef0123456789abcdef",
                "sha256": "a" * 64,
                "subdir": "noarch",
            }
        },
        fetch=False,
    )

    assert record.name == "typing_extensions"
    assert record.version == "4.12.2"
    assert record.build == "py3_none_any_0"
    assert record.build_number == 0
    assert record.channel.canonical_name == "conda-pypi"
    assert record.subdir == "noarch"
    assert record.fn == "typing_extensions-4.12.2-py3-none-any.whl"
    assert record.url == url
    assert record.md5 == "0123456789abcdef0123456789abcdef"
    assert record.sha256 == "a" * 64


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/noarch/bad.conda",
        "https://files.pythonhosted.org/packages/ab/cd/bad.whl",
    ],
    ids=["conda-archive", "wheel"],
)
def test_records_from_conda_urls_without_fetch_rejects_invalid_url(url: str) -> None:
    with pytest.raises(
        CondaValueError,
        match="Unable to reconstruct a package record from a lockfile URL",
    ):
        records_from_conda_urls({url: {}}, fetch=False)


def test_records_from_conda_urls_dry_run(monkeypatch, capsys):
    """
    Ensure that the metadata_by_url is shown correctly when dry_run is True.

    Regression fix for: https://github.com/conda-incubator/conda-lockfiles/issues/109
    """

    #: Used in ``test_records_from_conda_urls_dry_run`` test as expected output
    expected_dry_run_output = (
        "\nDry run would have fetched the following package records:\n\n"
        "  - example/noarch::package==0.1.0=h396c80c_0[md5=edd329d7d3a4ab45dcf905899a"
        "7a6115,sha256=7c2df5721c742c2a47b2c8f960e718c930031663ac1174da67c1ed5999f7938c]\n"
        "  - example/noarch::dependency==0.2.1=h536810c_0[md5=a9d86bc62f39b94c466171"
        "6624eb21b0,sha256=799cab4b6cde62f91f750149995d149bc9db525ec12595e8a1d91b9317"
        "f038b3]\n"
    )

    monkeypatch.setenv("CONDA_CHANNEL_ALIAS", "https://example.com")

    reset_context(())

    metadata_by_url = {
        "https://example.com/example/noarch/package-0.1.0-h396c80c_0.conda": {
            "conda": (
                "https://example.com/example/noarch/package-0.1.0-h396c80c_0.conda"
            ),
            "sha256": (
                "7c2df5721c742c2a47b2c8f960e718c930031663ac1174da67c1ed5999f7938c"
            ),
            "md5": "edd329d7d3a4ab45dcf905899a7a6115",
        },
        "https://example.com/example/noarch/dependency-0.2.1-h536810c_0.conda": {
            "conda": (
                "https://example.com/example/noarch/dependency-0.2.1-h536810c_0.conda"
            ),
            "sha256": (
                "799cab4b6cde62f91f750149995d149bc9db525ec12595e8a1d91b9317f038b3"
            ),
            "md5": "a9d86bc62f39b94c4661716624eb21b0",
        },
    }

    with pytest.raises(DryRunExit):
        records_from_conda_urls(metadata_by_url, dry_run=True)

    out, err = capsys.readouterr()

    # breakpoint()

    assert out == expected_dry_run_output
