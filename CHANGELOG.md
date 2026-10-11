# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/) as described in [docs/RELEASE.md](docs/RELEASE.md).

## [Unreleased]

### Added

- First implementation, planned as release 0.1.0:
  - `csv-tidy check` and `csv-tidy clean` (dry run by default, `--apply` to write), also
    available as `python -m csv_tidy`.
  - Strict CSV reading (comma/semicolon, UTF-8 with or without BOM, explicit encodings, quoted
    multiline fields) with record indexes and physical line ranges.
  - TOML profiles (`schema_version = 1`) with required columns, `text`/`decimal`/`date`
    types, number grammars `id`, `us`, `canonical`, numeric date formats, duplicate-row policy,
    and uniqueness keys.
  - Explicit transformations: trim, normalize, deduplicate (keep first), applied in that order,
    followed by output validation.
  - Safe export with input/alias protection, overwrite refusal, and per-file atomic writes.
  - Generated output profiles (`--output-schema`) for validating and re-cleaning output.
  - English text and JSON reports (report `schema_version` 1) and exit codes 0/1/2.
  - Python API: `check_file`, `clean_file`, `export_clean`, `load_profile`.
  - Synthetic examples, benchmark script, distribution smoke test, and CI for Linux and
    Windows on Python 3.11 and 3.15.
