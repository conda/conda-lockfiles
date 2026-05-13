# Getting Started

The `conda-lockfiles` plugin is integrated directly into the following conda commands:

- `conda create`
- `conda export`

The `create` and `export` commands allow you to create environments from lockfiles or
save and share them, respectively.

## Using `conda create` to create environments from lockfiles

```shell
# Same committed file on another machine or in CI; conda uses the slice for the current subdir.  Autodetect format.
conda create --name my-env --file conda-lock.yml
conda create --name my-env --file dev.conda-lock.yml
conda create --name my-env --file pixi.lock

# If the format is not detected from the filename:
conda create --name my-env --file dev.yml --format conda-lock
# or, equivalently, using the canonical version-pinned name:
conda create --name my-env --file dev.yml --format conda-lock-v1
```

:::{tip}
`conda-lock` and `pixi` resolve to `conda-lock-v1` and `rattler-lock-v6`
today. Use the version-pinned names in committed lockfiles and CI. See
[format aliases](format-aliases.md).
:::

:::{warning}
Only version 6 format of the pixi lock file is supported. Earlier versions may cause errors.
:::

## Using `conda export` to create lockfiles

Export lockfile from existing environment.

```shell
# Single-platform export (current platform and activated environment, default)
conda export --file conda-lock.yml

# Single-platform export with explicit platform
conda export --file conda-lock.yml --platform linux-64

# Multi-platform export
conda export --file pixi.lock --platform linux-64 --platform osx-arm64

# Lockfile can be generated from an environment that isn't activated.
conda export --name my-env --file conda-lock.yml

# Export with custom filename (requires --format)
conda export --file dev-lock.yml --format conda-lock-v1
```

Special cases:

```shell
# Export with explicit format (overrides filename detection)
conda export --file conda-lock.yml --format yaml
# Warning: Filename 'conda-lock.yml' suggests format 'conda-lock-v1' but --format specifies 'yaml'. Using 'yaml' or the environment.yml format.

# Export to stdout (bypasses filename validation)
conda export > output.yml  # Uses default format
conda export --format conda-lock-v1 > anything.txt
```

## Using `conda export` to save lockfiles with a different platform

If you have created an environment with the following command on the `linux-64` platform:

```shell
conda create --name python-env --yes python
```

it's possible to export it to a lockfile using the `win-64` platform with the following command:

```shell
conda export --name python-env --format pixi --platform win-64 --file pixi.lock
# or with the version-pinned name:
conda export --name python-env --format rattler-lock-v6 --platform win-64 --file pixi.lock
```

:::{warning}
Currently, it is not possible to create an environment from a lockfile and then export it using a
different platform. For example, an environment created using a lockfile using the `linux-64` platform
cannot be subsequently exported to the `win-64` platform.
:::

## Example workflows

Simple export and create:
```shell
conda export --file conda-lock.yml           # Auto-detects conda-lock-v1
conda create --name prod --file conda-lock.yml   # Auto-detects conda-lock-v1
```

Create lock file to share across platforms:
```shell
conda export --file conda-lock.yml --platform linux-64 --platform osx-arm64 --platform --win-64
# Share conda-lock.yml with team
conda create --name sharedenv --file conda-lock.yml
```


Here is a simple script that uses conda requirements.txt (not a pip requirements.txt) files and changes the Python version to create multi-platform lock files for each Python version.

```shell
for py in 3.10 3.11 3.12 3.13 3.14; do
  ver="${py//./}"
  name="my_env-py${ver}"
  lock_file_name="py${ver}.conda-lock.yml"
  conda create --yes --name "${name}" --file requirements.txt "python=${py}"

  conda export --name "${name}" --file "${lock_file_name}" --format conda-lock-v1 --platform linux-64 --platform win-64 --platform osx-arm64

  conda env remove --name "${name}" --yes
done
```

## Tips on usage

- These lockfiles can be saved to your repositories and used in CI workflows
  for faster execution times
- They can also be used with `conda-lock` and `pixi`
- This project is still in beta; please file bugs and feature requests [here](https://github.com/conda-incubator/conda-lockfiles)

## A Note about `conda-lock`
The conda-lock command is a specific command that can be used to create conda-lock.yaml files. It will need to be installed separately. Currently, the only additional functionality it provides is being able to produce a lock file from an environment.yaml file. For more information, see [the conda-lock GitHub repo](https://github.com/conda/conda-lock).
