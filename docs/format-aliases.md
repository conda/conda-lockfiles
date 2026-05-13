# Format names and aliases

Each lockfile format has a version-pinned canonical name and, when a
short form reads better at the command line, an unversioned alias.

## Names today

| Canonical name    | Unversioned alias | Files                                |
| ----------------- | ----------------- | ------------------------------------ |
| `conda-lock-v1`   | `conda-lock`      | `conda-lock.yml`, `conda-lock.yaml`  |
| `rattler-lock-v6` | `pixi`            | `pixi.lock`                          |

`rattler-lock-v6` also accepts `pixi-lock-v6` for compatibility with
docs and tooling that use the `pixi-lock-v*` naming.

## What the two names mean

The canonical names (`conda-lock-v1`, `rattler-lock-v6`) identify one
specific file-format version and never change meaning. `conda-lock-v1`
will still be `conda-lock-v1` after `conda-lock-v2` ships. Use these in
committed lockfiles, CI pins, and anywhere a file is exchanged with
another tool.

The unversioned aliases (`conda-lock`, `pixi`) resolve to whichever
version is current-stable in the installed conda-lockfiles release. Use
these when you want the latest format and do not need the invocation to
outlive the next release.

Concretely: `conda export --format pixi` writes `rattler-lock-v6` today.
If a later release makes `rattler-lock-v7` current-stable, the same
command writes v7.

## Alias ordering convention

The `ALIASES` tuple in each format module puts the short unversioned
alias first. conda uses the first alias as the display label in
`--help` output, with the canonical name and any remaining aliases
shown in parentheses:

```
Lockfiles:
  - pixi (rattler-lock-v6, pixi-lock-v6)
  - conda-lock (conda-lock-v1)
```

All names in the tuple, and the canonical name itself, remain valid
everywhere conda accepts a `--format` value. The ordering only affects
the help label.

When adding a new alias, place the short form first.

## Default filenames across versions

Each format's `default_filenames` is the filename users are already
typing (`pixi.lock`, `conda-lock.yml`). A new version of the same
format claims the same filenames; conda-lockfiles does not invent
`pixi-v7.lock`.

That means two export plugins can register the same `default_filenames`
entry once a new version ships alongside the old one. `conda export
--file pixi.lock` (no `--format`) needs conda to pick one. Conda today
raises `PluginError` on that collision;
[conda/conda#15963](https://github.com/conda/conda/issues/15963) tracks
the tiebreaker work so conda picks the current-stable plugin. Until
that lands, users pass `--format rattler-lock-vN` alongside `--file
pixi.lock` to disambiguate.

On the read side, `conda create -f pixi.lock` dispatches on file
contents. Each specifier's `can_handle()` rejects files it cannot
parse, so both plugins can coexist without manual disambiguation.

`--file pixi.lock` without `--format` writes current-stable (whatever
`pixi` currently resolves to) once the tiebreaker in conda/conda#15963
lands. Pin `--format rattler-lock-v6` when the format version needs to
outlive the next alias flip.

## Re-exporting a lockfile at a new format version

Existing `pixi.lock` files on disk remain valid after an alias flip;
nothing rewrites them. To upgrade one, re-create the environment from
the existing file and re-export at the new format:

```shell
conda create --name lockfile-upgrade --file pixi.lock
conda export \
  --name lockfile-upgrade \
  --format rattler-lock-v7 \
  --file pixi.lock \
  --platform linux-64 \
  --platform osx-arm64 \
  --platform win-64
```

Pin the new canonical name in the re-export so the command is
unaffected by future alias flips. The same pattern works for
`conda-lock-v1` to a future `conda-lock-v2`.
