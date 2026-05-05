[//]: # (current developments)

## 0.2.0 (unreleased)

### Enhancements

* Add unversioned `pixi` and `conda-lock` aliases for `rattler-lock-v6` and `conda-lock-v1`, with the alias bump policy and maintainer checklist documented. (#45 via #130)
* Add `available_platforms` and `env_for` to lockfile loaders so callers can pick a per-platform environment without re-parsing. (#128)
* Expose format descriptions and lockfile metadata through the plugin hooks. (#124)
* Accept `.yaml` in addition to `.yml` for `conda-lock-v1`. (#122)
* Register specifier-side aliases for the `conda_lock` and `rattler` env spec plugins. (#105)
* Parse lockfiles through Pydantic models; errors now point at the specific field that failed. (#103)
* Warn when `conda export` runs on an environment with pip dependencies, since the formats don't round-trip those. (#92)

### Bug fixes

* Clean up `--dry-run` output and stop printing stacktraces on expected failure paths. (#112)

### Deprecations

* Drop filename-based checks from env spec plugins; routing goes through `can_handle()` on file contents. (#107)

### Docs

* Split the docs into an end-user reference and a Developer section. `docs/format-aliases.md` covers the user-facing alias contract; `docs/developer/maintaining.md` holds the bump policy and maintainer checklist; `docs/developer/contributing.md` pulls in the root `CONTRIBUTING.md`. (#130 and follow-up)
* Refresh `README.md` and the getting-started guide for the current CLI. (#125, #137)
* Expand installation and usage instructions. (#72)

### Other

* Add cross-tool interop tests that export to `rattler-lock-v6` / `conda-lock-v1` and feed the output back into `pixi install --frozen` and `conda-lock install`, behind a new `interop` pytest marker that skips when the external tool is not on `PATH`. `conda-lock` added to the `test` pixi feature so CI picks it up. (#9 via #131)
* Fix the `conda-libmamba-solver` canary hash in CI and re-lock the committed env. (#113, #120)
* Infrastructure and template sync from `conda-bot`. (#81, #90, #94, #134)
* Dependency and workflow bumps from `dependabot`. (#75, #85, #96, #104, #115)
* `pre-commit` hook updates from `pre-commit-ci`. (#73, #76, #80, #86, #89, #91, #97, #102, #106, #108, #110, #111, #114, #123, #126, #129)

### Contributors

* @conda-bot
* @danyeaw made their first contribution in https://github.com/conda-incubator/conda-lockfiles/pull/122
* @jezdez
* @kenodegard
* @kkinnaman made their first contribution in https://github.com/conda-incubator/conda-lockfiles/pull/137
* @ryanskeith made their first contribution in https://github.com/conda-incubator/conda-lockfiles/pull/125
* @soapy1 made their first contribution in https://github.com/conda-incubator/conda-lockfiles/pull/92
* @travishathaway
* @dependabot[bot]
* @pre-commit-ci[bot]

## 0.1.1 (2025-10-22)

Early tagged release. See the git history for details; structured
changelog entries start with 0.2.0.

## 0.1.0 (2025-10-14)

First tagged release. See the git history for details; structured
changelog entries start with 0.2.0.
