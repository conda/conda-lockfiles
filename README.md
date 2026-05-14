# conda-lockfiles

Support for different lockfiles in the `conda` CLI tool.

<!-- docs-index-content-start -->
## What is this?

conda-lockfiles adds support for additional lockfile formats to conda. It supports different types of lockfiles
from the ecosystem like [conda-lock](https://github.com/conda/conda-lock) or [pixi](https://github.com/prefix-dev/pixi).

A lockfile is a machine-generated file that records the exact versions and sources of every package
in a given environment, including all dependencies, in its fully-resolved state. Unlike with
`environment.yml`, `requirements.txt`, or similar files, lockfiles do not require the environment to be
solved again, which might introduce differences from the original environment. Lockfiles can reproduce
exact environments across different machines and points in time again and again.

The basic usage is:

```bash
# Create environment from lockfile
conda create --name ENV-NAME --format FORMAT --file /path/to/lockfile

# Export current environment to lockfile
conda export --name ENV-NAME --format FORMAT --file /path/to/lockfile
```

If conda recognizes your lockfile's format, the `--format` flag is optional with `conda create`.

Currently supported lockfile formats are:

- `conda-lock.yml` / `conda-lock.yaml` — `conda-lock-v1` (alias: `conda-lock`)
- `pixi.lock` — `rattler-lock-v6` (aliases: `pixi`, `pixi-lock-v6`)

The version-pinned names (such as `-v1`, `-v6`) never change meaning. The short
aliases track the current-stable version. For information on when to use which name,
see [format aliases](https://conda-incubator.github.io/conda-lockfiles/format-aliases.html).

## Installation

`conda-lockfiles` is a `conda` plugin and must be installed in the `base` environment:

```bash
conda install --name base conda-forge::conda-lockfiles
```

## Usage

### Creating a lockfile for the current environment

```bash
conda export --format FORMAT --file FILE
```

To specify additional platforms:

```bash
conda export --format FORMAT --file FILE [--override-platforms] --platform PLATFORM ...
```

See [`conda export` docs](https://docs.conda.io/projects/conda/en/stable/commands/export.html) for more details.

### Creating a new environment from a lockfile

```bash
conda create --file FILE
```

If conda is unable to determine the file format:

```bash
conda create --file FILE --format FORMAT
```

See [`conda create` docs](https://docs.conda.io/projects/conda/en/stable/commands/create.html) for more details.

### Examples

**Export one `conda-lock` file with several platforms** (adjust platforms to what you need; exporting a platform different than the host may fail):

```bash
conda export \
  --name myenv \
  --format conda-lock-v1 \
  --file conda-lock.yml \
  --platform linux-64 \
  --platform osx-64
```

**Create an environment from that lockfile**:

```bash
conda create --name myenv --file conda-lock.yml
# if the format is not auto-detected:
conda create --name myenv --file dev-lock.yml --format conda-lock-v1
```

**Pixi / rattler lock v6**:

```bash
conda export --name myenv --format pixi --file pixi.lock
conda create --name myenv --file pixi.lock --format pixi
```

`pixi` resolves to `rattler-lock-v6` today. Use `--format
rattler-lock-v6` in committed lockfiles
and CI so a future alias flip doesn't change the written format.
<!-- docs-index-content-end -->

More information and example workflows are available on our online [documentation](https://conda-incubator.github.io/conda-lockfiles/).

## Contributing

Please refer to [`CONTRIBUTING.md`](/CONTRIBUTING.md).
