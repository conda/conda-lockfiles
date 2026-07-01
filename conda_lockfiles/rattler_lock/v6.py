from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated  # noqa: TCH003

from conda.base.context import context
from conda.common.io import dashlist
from conda.common.serialize import yaml_safe_dump
from conda.exceptions import CondaValueError
from conda.models.channel import Channel
from conda.models.environment import Environment, EnvironmentConfig
from conda.models.match_spec import MatchSpec
from conda.plugins.types import EnvironmentSpecBase
from pydantic import BaseModel, Field, ValidationError, field_validator
from ruamel.yaml import YAMLError
from ruamel.yaml.parser import ParserError

from ..exceptions import CondaLockfilesParserError, CondaLockfilesValidationError
from ..history import requested_specs_from_prefix
from ..load_yaml import load_yaml
from ..records_from_conda_urls import records_from_conda_urls
from ..validate_urls import validate_urls

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any, ClassVar, Final, Literal

    from conda.common.path import PathType
    from conda.models.records import PackageRecord


#: The name of the rattler lock v6 format.
FORMAT: Final = "rattler-lock-v6"

#: Aliases for the rattler lock v6 format. ``pixi`` is the unversioned
#: convenience alias and tracks the current stable ``rattler-lock-v*``
#: format; ``pixi-lock-v6`` is the version-pinned alias. The short alias
#: is listed first so that conda's help text renders it as the display
#: label. See ``docs/format-aliases.md`` for the alias policy.
ALIASES: Final = ("pixi", "pixi-lock-v6")

#: The filename of the rattler lock v6 format.
PIXI_LOCK_FILE: Final = "pixi.lock"

#: Default filenames for the rattler lock v6 format.
DEFAULT_FILENAMES: Final = (PIXI_LOCK_FILE,)

#: Mapping of supported package types (as used in the lockfile) to package
#: managers (as used in the environment)
PACKAGE_TYPE_MAPPING: Final = {
    # "conda": "conda",  # processed as conda (explicit) packages
    "pypi": "pypi",
}


class RattlerLockV6Channel(BaseModel):
    """A channel specification in a rattler lock file."""

    url: str


class RattlerLockV6PackageReference(BaseModel):
    """A reference to a package in an environment (just the URL)."""

    conda: str | None = None
    pypi: str | None = None

    @field_validator("conda", "pypi")
    @classmethod
    def check_at_least_one(cls, value, info):
        """Ensure at least one package manager is specified."""
        if not value and not info.data.get("conda") and not info.data.get("pypi"):
            raise ValueError("Either 'conda' or 'pypi' must be specified")

        if value and info.data.get("conda") and info.data.get("pypi"):
            raise ValueError("Either 'conda' or 'pypi' must be specified, not both")

        return value

    # NOTE: properties are excluded from the model_dump() output
    @property
    def package_type(self) -> Literal["conda", "pypi"]:
        if self.conda:
            return "conda"
        elif self.pypi:
            return "pypi"
        else:
            raise ValueError("Either 'conda' or 'pypi' must be specified")

    # NOTE: properties are excluded from the model_dump() output
    @property
    def url(self) -> str:
        if self.conda:
            return self.conda
        elif self.pypi:
            return self.pypi
        else:
            raise ValueError("Either 'conda' or 'pypi' must be specified")


class RattlerLockV6Package(RattlerLockV6PackageReference):
    """Full package definition with metadata in the packages list."""

    # Optional metadata fields
    sha256: str | None = None
    md5: str | None = None
    license: str | None = None
    license_family: str | None = None
    size: int | None = None
    timestamp: int | None = None
    depends: list[str] | None = None
    constrains: list[str] | None = None
    features: str | None = None
    track_features: list[str] | None = None
    python_site_packages_path: str | None = None


class RattlerLockV6Environment(BaseModel):
    """An environment specification in a rattler lock file."""

    model_config = {"populate_by_name": True}

    channels: list[RattlerLockV6Channel]
    packages: Annotated[
        dict[str, list[RattlerLockV6PackageReference]],
        Field(description="Mapping of platforms to package references (package URLs)"),
    ]
    # Non-standard extension: user-requested MatchSpec strings keyed by
    # platform. Serialized as ``requested-packages`` to match rattler's
    # kebab-case convention for multi-word keys. rattler silently ignores
    # unknown fields on read, but WILL drop them on any re-serialize
    # (``pixi add``, ``pixi update``, ...), so treat this as advisory.
    requested_packages: Annotated[
        dict[str, list[str]] | None,
        Field(
            default=None,
            alias="requested-packages",
            description=(
                "User-requested MatchSpec strings, keyed by platform. "
                "Non-standard extension; dropped on rattler re-serialize."
            ),
        ),
    ] = None


class RattlerLockV6(BaseModel):
    """The root structure of a rattler lock v6 file."""

    version: Annotated[
        int,
        Field(le=6, ge=6, description="Lock file format version, must be 6"),
    ] = 6
    environments: Annotated[
        dict[str, RattlerLockV6Environment],
        Field(description="Mapping of environment names to environment specifications"),
    ]
    packages: Annotated[
        list[RattlerLockV6Package],
        Field(description="Complete list of packages with full metadata"),
    ]

    @field_validator("environments")
    @classmethod
    def check_default_env(cls, value):
        """Ensure default environment exists."""
        if "default" not in value:
            raise ValueError("Lock file must contain a 'default' environment")
        return value


def _record_to_package(record: PackageRecord) -> RattlerLockV6Package:
    """
    Convert a conda PackageRecord to a RattlerLockV6Package Pydantic model.

    :param record: Conda package record
    :return: RattlerLockV6Package with metadata
    """
    # Build kwargs for RattlerLockV6Package constructor
    kwargs = {"conda": record.url}

    # Add optional metadata fields that rattler_lock includes in v6 lockfiles
    # https://github.com/conda/rattler/blob/rattler_lock-v0.23.5/crates/rattler_lock/src/parse/models/v6/conda_package_data.rs#L46
    fields = [
        # channel, subdir, name, build and version can be determined from the URL
        "sha256",
        "md5",
        "depends",
        "constrains",
        "features",
        "track_features",
        "license",
        "license_family",
        "size",
        # conda-libmamba-solver does not record the repodata timestamp,
        # do not include this field
        # See: https://github.com/conda/conda-libmamba-solver/issues/673
        # "timestamp",
        "python_site_packages_path",
    ]

    for field in fields:
        if data := record.get(field, None):
            kwargs[field] = data

    return RattlerLockV6Package(**kwargs)


def rattler_lock_v6_from_conda_envs(envs: Iterable[Environment]) -> RattlerLockV6:
    """
    Create a RattlerLockV6 lockfile from conda Environment objects.

    :param envs: Iterable of conda Environment objects
        (typically multiple platforms)
    :return: RattlerLockV6 Pydantic model instance
    """
    # Convert to list to allow multiple iterations
    env_list = list(envs)

    # Validate URLs for all environments
    for env in env_list:
        validate_urls(env, FORMAT)

    # Build per-platform package references
    packages: list[RattlerLockV6Package] = []
    platforms: dict[str, list[RattlerLockV6PackageReference]] = {
        platform: [] for platform in sorted(env.platform for env in env_list)
    }

    # TODO: Add support for external_packages (PyPI packages)
    # Currently only exports conda packages from env.explicit_packages

    # Process packages
    seen = set()  # Track package URLs to avoid duplicates
    for pkg, platform in sorted(
        # Canonical order is sorted by name then by platform
        ((pkg, env.platform) for env in env_list for pkg in env.explicit_packages),
        key=lambda pkg_platform: (pkg_platform[0].name, pkg_platform[1]),
    ):
        # Add package reference to this platform
        platforms[platform].append(RattlerLockV6PackageReference(conda=pkg.url))

        # Deduplicate: only add to packages list once
        if pkg.url in seen:
            continue
        packages.append(_record_to_package(pkg))
        seen.add(pkg.url)

    # Build channel list from first environment
    # (all environments should have same channels for multiplatform export)
    env = env_list[0]
    channels = [RattlerLockV6Channel(url=channel) for channel in env.config.channels]

    # Record user intent per-platform from each prefix's history. We
    # re-derive rather than trusting env.requested_packages because conda
    # fills that with the full install list by default
    # (conda/conda#15961).
    requested_packages: dict[str, list[str]] = {}
    for e in env_list:
        specs = requested_specs_from_prefix(e.prefix)
        if specs:
            requested_packages[e.platform] = specs

    # Build environment
    default_env = RattlerLockV6Environment(
        channels=channels,
        packages=platforms,
        requested_packages=requested_packages or None,
    )

    # Construct and return RattlerLockV6 instance
    return RattlerLockV6(
        version=6,
        environments={"default": default_env},
        packages=packages,
    )


def rattler_lock_v6_to_conda_env(
    lockfile: RattlerLockV6,
    name: str = "default",
    platform: str = context.subdir,
) -> Environment:
    """
    Render lockfile as a conda environment

    :param lockfile: RattlerLockV6 lockfile model
    :param name: Environment name to extract
    :param platform: Platform to extract packages for
    :return: Conda Environment object
    """
    # validate `name` and `platform` arguments
    if not (environment := lockfile.environments.get(name, None)):
        raise ValueError(
            f"Environment '{name}' not found.\n"
            f"Available environments: {dashlist(sorted(lockfile.environments))}"
        )

    channels = environment.channels
    config = EnvironmentConfig(
        channels=tuple(Channel(channel.url).canonical_name for channel in channels),
    )

    # Map rattler v6 packages to conda/external package records
    explicit_packages: dict[str, dict[str, Any]] = {}
    external_packages: dict[str, list[str]] = {}
    for ref in environment.packages.get(platform, ()):
        # Group by manager
        if ref.conda:
            explicit_packages[ref.url] = next(
                pkg for pkg in lockfile.packages if pkg.url == ref.url
            ).model_dump()
        else:
            # Map rattler v6 package type to conda package type
            try:
                key = PACKAGE_TYPE_MAPPING[ref.package_type]
            except KeyError:
                raise ValueError(f"Unknown package type: {ref.package_type}")
            external_packages.setdefault(key, []).append(ref.url)

    resolved_explicit = records_from_conda_urls(
        explicit_packages, dry_run=context.dry_run
    )

    # Decode per-platform user-requested specs. Drop specs whose name
    # isn't in the platform's explicit packages: Environment.__post_init__
    # enforces requested_packages ⊆ explicit_packages by name.
    requested_packages: list[MatchSpec] = []
    if environment.requested_packages:
        platform_specs = environment.requested_packages.get(platform, [])
        explicit_names = {pkg.name for pkg in resolved_explicit}
        for spec_str in platform_specs:
            if not isinstance(spec_str, str):
                continue
            try:
                ms = MatchSpec(spec_str)
            except Exception:
                continue
            if ms.name in explicit_names:
                requested_packages.append(ms)

    return Environment(
        prefix=context.target_prefix,
        platform=platform,
        config=config,
        explicit_packages=resolved_explicit,
        external_packages=external_packages,
        requested_packages=requested_packages,
    )


def multiplatform_export(envs: Iterable[Environment]) -> str:
    """Export Environment to rattler lock format."""
    lockfile = rattler_lock_v6_from_conda_envs(envs)
    try:
        return yaml_safe_dump(
            lockfile.model_dump(
                exclude_none=True,
                mode="python",
                by_alias=True,
            )
        )
    except YAMLError as e:
        raise CondaValueError(
            f"Failed to export environment to rattler lock format: {e}"
        ) from e


class RattlerLockV6Loader(EnvironmentSpecBase):
    detection_supported: ClassVar[bool] = True

    def __init__(self, path: PathType):
        self.path = Path(path).resolve()
        self._model: RattlerLockV6 | None = None

    def can_handle(self) -> bool:
        """
        Attempts to validate loaded data as a rattler lock v6 specification.

        :raises ValueError: Raised when validation fails
        """
        if not self.path.exists():
            raise ValueError(f"File not found: {self.path}")

        return self._validate_model()

    def _validate_model(self) -> bool:
        """
        Attempt to load model

        :returns: indicates successful load
        :raises ValueError: raised when validation fails
        """
        try:
            self._model = RattlerLockV6.model_validate(self._data)
            return True
        except ValidationError as e:
            raise CondaLockfilesValidationError(e, self.path) from e

    @property
    def _data(self) -> dict[str, Any]:
        try:
            return load_yaml(self.path)
        except ParserError as e:
            raise CondaLockfilesParserError(e, self.path)

    @property
    def env(self) -> Environment:
        try:
            if self._model is None:
                self._validate_model()
            return rattler_lock_v6_to_conda_env(self._model)
        except ValueError as e:
            raise CondaValueError(f"\n\nUnable to create environment: {e}") from e

    @property
    def available_platforms(self) -> tuple[str, ...]:
        """Platforms declared in this lockfile."""
        if self._model is None:
            self._validate_model()
        return tuple(sorted(self._model.environments["default"].packages.keys()))

    def env_for(self, platform: str) -> Environment:
        """Return the Environment for a specific platform in the lockfile."""
        if platform not in self.available_platforms:
            raise ValueError(
                f"Platform {platform!r} not in lockfile. "
                f"Available platforms: {', '.join(self.available_platforms)}"
            )
        return rattler_lock_v6_to_conda_env(self._model, platform=platform)
