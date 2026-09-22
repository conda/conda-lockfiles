### Enhancements

* Add atomic lockfile transcoding without downloading package artifacts, with validation of source package types and references. (#161)

### Bug fixes

* Validate rattler package references against metadata with the same package-manager type. (#161)
* Accept the standard `manager: pip` value in conda-lock v1 files. (#161)
* Align the conda package runtime requirement with the EnvironmentFormat API used by the plugin. (#161)
* Preserve embedded build numbers, including zero, in rattler-lock v6 transcoding. No-fetch records use zero when the source omits the field, while installation loaders retain their cached-metadata fallback. (#161)
