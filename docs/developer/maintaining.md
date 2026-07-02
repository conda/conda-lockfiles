# Maintaining this project

This page collects workflows that only maintainers need. End-user
reference on format names and aliases lives in
[Format names and aliases](../format-aliases).

## Bump policy

When a new version of a format reaches stable, the alias is rolled
over two releases so the flip is never silent:

1. **Overlap release.** The new canonical name (`rattler-lock-v7`)
   ships alongside the old one (`rattler-lock-v6`). The unversioned
   alias (`pixi`) still resolves to the old canonical name. Alias
   resolution emits a `PendingDeprecationWarning` with wording that
   names the binding change, not a format deprecation:

   ```
   PendingDeprecationWarning: 'pixi' currently resolves to
   rattler-lock-v6 and will resolve to rattler-lock-v7 in
   conda-lockfiles <version>. Pin --format rattler-lock-v6 to keep
   writing v6 after the flip.
   ```

   Python's default filter silences `PendingDeprecationWarning` for
   end users and shows it in tests and `python -W` runs, which is the
   right volume for "this alias is about to flip, it may matter to
   you".

2. **Flip release.** The unversioned alias now resolves to the new
   canonical name. First alias resolution per process emits a one-shot
   `DeprecationWarning`:

   ```
   DeprecationWarning: 'pixi' now resolves to rattler-lock-v7 (was
   rattler-lock-v6 in the previous release). Pin --format
   rattler-lock-v6 if you need the old format.
   ```

   `DeprecationWarning` (not `PendingDeprecationWarning`) because the
   change has landed and Python's default filter shows it once per
   location per process, so anyone who did not read the release notes
   sees the flip exactly once. The old canonical name keeps working;
   no warning on it.

3. **Removal release.** The old canonical name (`rattler-lock-v6`)
   enters the standard `conda.deprecations.deprecated` cycle with a
   concrete `remove_in` target. The one-shot `DeprecationWarning` from
   step 2 is dropped; the binding is stable again.

Canonical names only participate in step 3. The unversioned alias
(`pixi`, `conda-lock`) itself is never removed.

The warning support for steps 1 and 2 lives in
`conda_lockfiles.aliases`. Use `pending_alias_binding_warning()` during
an overlap release and `flipped_alias_binding_warning()` during the
flip release.

### Maintainer checklist

When shipping a new format version (overlap release):

- Register it under its canonical name in `conda_lockfiles/plugin.py`.
- Set `default_filenames` to match the previous canonical version
  (`pixi.lock` stays `pixi.lock`).
- Leave the unversioned alias pointing at the previous canonical name.
- When alias resolution picks the unversioned alias, raise
  `PendingDeprecationWarning` with wording that names the binding
  change (not a format deprecation) and names the flip release.
- Announce the upcoming flip in the release notes.
- Add tests covering both canonical names and confirming the alias
  still resolves to the previous format.
- Update the "Names today" table in
  [Format names and aliases](../format-aliases).

When flipping the alias (flip release):

- Point the unversioned alias at the new canonical name.
- On first alias resolution per process, raise a one-shot
  `DeprecationWarning` naming the flip that just happened and pointing
  at the pin command.
- Call out the flip in the release notes.
- Update the "Names today" table.

When retiring the old version (removal release):

- Mark the old canonical name with `conda.deprecations.deprecated` and
  a removal target.
- Drop the one-shot `DeprecationWarning` from step 2.
- Update the "Names today" table.
