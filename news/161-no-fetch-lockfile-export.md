### Enhancements

* Add atomic lockfile transcoding without downloading package artifacts, and reject source data that cannot be represented without loss. (#161)

### Bug fixes

* Validate rattler package references against metadata with the same package-manager type. (#161)
* Accept the standard `manager: pip` value in conda-lock v1 files. (#161)
* Align the conda package runtime requirement with the EnvironmentFormat API used by the plugin. (#161)
