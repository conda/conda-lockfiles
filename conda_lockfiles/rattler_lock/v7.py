from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated  # noqa: TCH003

from conda.base.context import context
from conda.common.io import dashlist
from conda.common.serialize import yaml_safe_dump
from conda.exceptions import CondaValueError
from conda.models.channel import Channel
from conda.models.environment import Environment, EnvironmentConfig
from conda.plugins.types import EnvironmentSpecBase
from pydantic import BaseModel, Field, ValidationError, field_validator
from ruamel.yaml import YAMLError
from ruamel.yaml.parser import ParserError

from ..exceptions import CondaLockfilesParserError, CondaLockfilesValidationError
from ..load_yaml import load_yaml
from ..records_from_conda_urls import records_from_conda_urls
from ..validate_urls import validate_urls

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any, ClassVar, Final, Literal

    from conda.common.path import PathType
    from conda.models.records import PackageRecord


#: The name of the rattler lock v7 format.
FORMAT: Final = "rattler-lock-v7"

#: Aliases for the rattler lock v7 format. ``pixi-lock-v7`` is the
#: version-pinned alias. The unversioned ``pixi`` alias stays on v6
#: during the overlap release; it is *not* listed here.
#: See ``docs/format-aliases.md`` for the alias policy.
ALIASES: Final = ("pixi-lock-v7",)

#: The filename of the rattler lock v7 format.
PIXI_LOCK_FILE: Final = "pixi.lock"

#: Default filenames for the rattler lock v7 format.
DEFAULT_FILENAMES: Final = (PIXI_LOCK_FILE,)

#: Mapping of supported package types (as used in the lockfile) to package
#: managers (as used in the environment)
PACKAGE_TYPE_MAPPING: Final = {
    # "conda": "conda",  # processed as conda (explicit) packages
    "pypi": "pypi",
}


class RattlerLockV7Platform(BaseModel):
    """A platform declaration in the top-level ``platforms`` list."""

    name: str
    subdir: str | None = None
    virtual_packages: Annotated[
        list[str] | None,
        Field(alias="virtual-packages", default=None),
    ]

    model_config = {"populate_by_name": True}

    @property
    def resolved_subdir(self) -> str:
        """Return the effective subdir (falls back to *name*)."""
        return self.subdir or self.name


class RattlerLockV7Channel(BaseModel):
    """A channel specification in a rattler lock v7 file."""

    url: str


class RattlerLockV7PackageReference(BaseModel):
    """A reference to a package in an environment (just the URL or source id)."""

    conda: str | None = None
    conda_source: str | None = None
    pypi: str | None = None

    @field_validator("conda", "pypi", "conda_source")
    @classmethod
    def check_at_least_one(cls, value, info):
        """Ensure exactly one package type is specified."""
        present = sum(
            1
            for key in ("conda", "pypi", "conda_source")
            if info.data.get(key) is not None
        )
        if value is not None and present > 1:
            raise ValueError(
                "Exactly one of 'conda', 'pypi', or 'conda_source' must be specified"
            )
        return value

    _MISSING_MSG = "One of 'conda', 'pypi', or 'conda_source' must be specified"

    @property
    def package_type(self) -> Literal["conda", "pypi", "conda_source"]:
        if self.conda:
            return "conda"
        elif self.conda_source:
            return "conda_source"
        elif self.pypi:
            return "pypi"
        else:
            raise ValueError(self._MISSING_MSG)

    @property
    def url(self) -> str:
        if self.conda:
            return self.conda
        elif self.conda_source:
            return self.conda_source
        elif self.pypi:
            return self.pypi
        else:
            raise ValueError(self._MISSING_MSG)


class RattlerLockV7EnvironmentOptions(BaseModel):
    """Per-environment solver options (new in v7)."""

    channel_priority: Annotated[
        str | None,
        Field(alias="channel-priority", default=None),
    ]
    strategy: str | None = None

    model_config = {"populate_by_name": True}


class RattlerLockV7Package(RattlerLockV7PackageReference):
    """Full package definition with metadata in the packages list."""

    # Common metadata
    version: str | None = None
    build: str | None = None
    subdir: str | None = None
    noarch: str | None = None
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

    # v7 source package fields
    build_packages: list[RattlerLockV7PackageReference] | None = None
    host_packages: list[RattlerLockV7PackageReference] | None = None

    # v7 PyPI fields
    name: str | None = None
    index: str | None = None
    requires_python: str | None = None
    requires_dist: list[str] | None = None


class RattlerLockV7Environment(BaseModel):
    """An environment specification in a rattler lock v7 file."""

    channels: list[RattlerLockV7Channel]
    indexes: list[str] | None = None
    options: RattlerLockV7EnvironmentOptions | None = None
    packages: Annotated[
        dict[str, list[RattlerLockV7PackageReference]],
        Field(description="Mapping of platform names to package references"),
    ]


class RattlerLockV7(BaseModel):
    """The root structure of a rattler lock v7 file."""

    version: Annotated[
        int,
        Field(le=7, ge=7, description="Lock file format version, must be 7"),
    ] = 7
    platforms: Annotated[
        list[RattlerLockV7Platform],
        Field(description="Top-level platform declarations"),
    ]
    environments: Annotated[
        dict[str, RattlerLockV7Environment],
        Field(description="Mapping of environment names to environment specifications"),
    ]
    packages: Annotated[
        list[RattlerLockV7Package],
        Field(description="Complete list of packages with full metadata"),
    ]

    @field_validator("environments")
    @classmethod
    def check_default_env(cls, value):
        """Ensure default environment exists."""
        if "default" not in value:
            raise ValueError("Lock file must contain a 'default' environment")
        return value


def _record_to_package(record: PackageRecord) -> RattlerLockV7Package:
    """
    Convert a conda PackageRecord to a RattlerLockV7Package Pydantic model.

    :param record: Conda package record
    :return: RattlerLockV7Package with metadata
    """
    kwargs: dict[str, Any] = {"conda": record.url}

    fields = [
        "sha256",
        "md5",
        "depends",
        "constrains",
        "features",
        "track_features",
        "license",
        "license_family",
        "size",
        "python_site_packages_path",
    ]

    for field in fields:
        if data := record.get(field, None):
            kwargs[field] = data

    return RattlerLockV7Package(**kwargs)


def rattler_lock_v7_from_conda_envs(envs: Iterable[Environment]) -> RattlerLockV7:
    """
    Create a RattlerLockV7 lockfile from conda Environment objects.

    :param envs: Iterable of conda Environment objects
        (typically multiple platforms)
    :return: RattlerLockV7 Pydantic model instance
    """
    env_list = list(envs)

    for env in env_list:
        validate_urls(env, FORMAT)

    # Build top-level platforms list (new in v7)
    platform_names = sorted(env.platform for env in env_list)
    platforms = [RattlerLockV7Platform(name=p) for p in platform_names]

    # Build per-platform package references
    packages: list[RattlerLockV7Package] = []
    platform_refs: dict[str, list[RattlerLockV7PackageReference]] = {
        p: [] for p in platform_names
    }

    seen: set[str] = set()
    for pkg, platform in sorted(
        ((pkg, env.platform) for env in env_list for pkg in env.explicit_packages),
        key=lambda pkg_platform: (pkg_platform[0].name, pkg_platform[1]),
    ):
        platform_refs[platform].append(RattlerLockV7PackageReference(conda=pkg.url))

        if pkg.url in seen:
            continue
        packages.append(_record_to_package(pkg))
        seen.add(pkg.url)

    # Build channel list from first environment
    env = env_list[0]
    channels = [RattlerLockV7Channel(url=channel) for channel in env.config.channels]

    default_env = RattlerLockV7Environment(channels=channels, packages=platform_refs)

    return RattlerLockV7(
        version=7,
        platforms=platforms,
        environments={"default": default_env},
        packages=packages,
    )


def rattler_lock_v7_to_conda_env(
    lockfile: RattlerLockV7,
    name: str = "default",
    platform: str = context.subdir,
) -> Environment:
    """
    Render lockfile as a conda environment.

    :param lockfile: RattlerLockV7 lockfile model
    :param name: Environment name to extract
    :param platform: Platform to extract packages for
    :return: Conda Environment object
    """
    if not (environment := lockfile.environments.get(name, None)):
        raise ValueError(
            f"Environment '{name}' not found.\n"
            f"Available environments: {dashlist(sorted(lockfile.environments))}"
        )

    # Resolve platform name to subdir via top-level platforms list
    platform_map = {p.name: p.resolved_subdir for p in lockfile.platforms}

    channels = environment.channels
    config = EnvironmentConfig(
        channels=tuple(Channel(channel.url).canonical_name for channel in channels),
    )

    explicit_packages: dict[str, dict[str, Any]] = {}
    external_packages: dict[str, list[str]] = {}
    for ref in environment.packages.get(platform, ()):
        if ref.conda:
            explicit_packages[ref.url] = next(
                pkg for pkg in lockfile.packages if pkg.url == ref.url
            ).model_dump()
        elif ref.conda_source:
            # Source packages are not installable via conda; skip for now.
            # Future: could build from source using the embedded metadata.
            pass
        else:
            try:
                key = PACKAGE_TYPE_MAPPING[ref.package_type]
            except KeyError:
                raise ValueError(f"Unknown package type: {ref.package_type}")
            external_packages.setdefault(key, []).append(ref.url)

    return Environment(
        prefix=context.target_prefix,
        platform=platform_map.get(platform, platform),
        config=config,
        explicit_packages=records_from_conda_urls(
            explicit_packages, dry_run=context.dry_run
        ),
        external_packages=external_packages,
    )


def multiplatform_export(envs: Iterable[Environment]) -> str:
    """Export Environment to rattler lock v7 format."""
    lockfile = rattler_lock_v7_from_conda_envs(envs)
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
            f"Failed to export environment to rattler lock v7 format: {e}"
        ) from e


class RattlerLockV7Loader(EnvironmentSpecBase):
    detection_supported: ClassVar[bool] = True

    def __init__(self, path: PathType):
        self.path = Path(path).resolve()
        self._model: RattlerLockV7 | None = None

    def can_handle(self) -> bool:
        """
        Attempts to validate loaded data as a rattler lock v7 specification.

        :raises ValueError: Raised when validation fails
        """
        if not self.path.exists():
            raise ValueError(f"File not found: {self.path}")

        return self._validate_model()

    def _validate_model(self) -> bool:
        """
        Attempt to load model.

        :returns: indicates successful load
        :raises ValueError: raised when validation fails
        """
        try:
            self._model = RattlerLockV7.model_validate(self._data)
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
            return rattler_lock_v7_to_conda_env(self._model)
        except ValueError as e:
            raise CondaValueError(f"\n\nUnable to create environment: {e}") from e

    @property
    def available_platforms(self) -> tuple[str, ...]:
        """Platforms declared in this lockfile."""
        if self._model is None:
            self._validate_model()
        return tuple(p.name for p in self._model.platforms)

    def env_for(self, platform: str) -> Environment:
        """Return the Environment for a specific platform in the lockfile."""
        if platform not in self.available_platforms:
            raise ValueError(
                f"Platform {platform!r} not in lockfile. "
                f"Available platforms: {', '.join(self.available_platforms)}"
            )
        return rattler_lock_v7_to_conda_env(self._model, platform=platform)
