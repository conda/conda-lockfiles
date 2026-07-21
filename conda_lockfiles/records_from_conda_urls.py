from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import unquote, urlsplit

from conda.base.context import context
from conda.common.io import dashlist
from conda.core.package_cache_data import PackageCacheData, ProgressiveFetchExtract
from conda.exceptions import (
    CondaExitZero,
    CondaValueError,
    DryRunExit,
)
from conda.models.match_spec import MatchSpec
from conda.models.records import PackageRecord
from packaging.utils import parse_wheel_filename

if TYPE_CHECKING:
    from typing import Any

    CondaPackageURL = str
    CondaPackageMetadata = dict[str, Any]


def records_from_conda_urls(
    metadata_by_url: dict[CondaPackageURL, CondaPackageMetadata],
    dry_run: bool = False,
    download_only: bool = context.download_only,
    *,
    fetch: bool = True,
) -> tuple[PackageRecord, ...]:
    """
    Return PackageRecords for a set of conda package URLs.

    Any metadata specified for the url in `metadata_by_url` will be reflected
    in the resulting PackageRecords. When ``fetch`` is true, fields not specified
    are filled from the package cache.

    When ``fetch`` is false, package artifacts and cache entries are not read.
    The metadata-only records use zero for the required ``build_number`` field
    and are only suitable for transcoding because the supported lockfile
    exporters do not serialize that field.

    """
    try:
        fetch_specs = [
            MatchSpec(
                url,
                **{key: metadata[key] for key in ("md5", "sha256") if key in metadata},
            )
            for url, metadata in metadata_by_url.items()
        ]
    except (TypeError, ValueError) as e:
        if not fetch:
            raise CondaValueError(
                "Unable to reconstruct a package record from a lockfile URL."
            ) from e
        raise

    if dry_run and fetch:
        print("\nDry run would have fetched the following package records:")
        print(dashlist(fetch_specs))

        raise DryRunExit()

    if not fetch:
        records: list[PackageRecord] = []
        for fetch_spec, (url, metadata) in zip(
            fetch_specs, metadata_by_url.items(), strict=True
        ):
            try:
                fields = {
                    field: fetch_spec.get_exact_value(field)
                    for field in (
                        "channel",
                        "subdir",
                        "name",
                        "version",
                        "build",
                        "fn",
                    )
                }
                filename = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
                if filename.endswith(".whl"):
                    _, version, _, _ = parse_wheel_filename(filename)
                    fields.update(
                        fn=filename,
                        name=filename.partition("-")[0],
                        version=str(version),
                    )
                records.append(
                    PackageRecord(
                        **{
                            **fields,
                            "build_number": 0,
                            **metadata,
                            "url": url,
                        }
                    )
                )
            except (TypeError, ValueError) as e:
                raise CondaValueError(
                    "Unable to reconstruct a package record from a lockfile URL."
                ) from e
        return tuple(records)

    pfe = ProgressiveFetchExtract(fetch_specs)
    pfe.execute()

    if download_only:
        raise CondaExitZero(
            "Package caches prepared. Installed cancelled with --download-only option."
        )

    records: list[PackageRecord] = []
    for fetch_spec in fetch_specs:
        cache_record = next(PackageCacheData.query_all(fetch_spec), None)
        if cache_record is None:
            raise AssertionError(f"Missing package cache record for: {fetch_spec}")
        url = fetch_spec.get("url")
        overrides = metadata_by_url.get(url, {})
        records.append(
            PackageRecord.from_objects(
                cache_record,
                **overrides,
            )
        )
    return tuple(records)
