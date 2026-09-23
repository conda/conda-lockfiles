"""Use conda's current YAML API when available, or its pre-26.1 helpers."""

try:
    from conda.common.serialize.yaml import dumps, load, loads
except ModuleNotFoundError as exc:
    if exc.name != "conda.common.serialize.yaml":
        raise
    from conda.common.serialize import yaml_safe_dump as dumps
    from conda.common.serialize import yaml_safe_load as load
    from conda.common.serialize import yaml_safe_load as loads

__all__ = ["dumps", "load", "loads"]
