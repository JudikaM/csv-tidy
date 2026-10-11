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

### Fixed

Defects found by an audit of the first published commit (e1e4a63), before any release:

- A value selected for normalization that could not be parsed in its source format was
  reported as resolved, and exported, when it happened to look valid in the output format
  (for example `1.25` with `id` source and `canonical` output). It now stays an error.
- `export_clean` protected input paths relative to the current working directory at export
  time; results now keep absolute input paths captured when the files were read.
- Normalization could make a value longer than `max_field_chars`, producing an export that its
  own output profile could not read. Such values are now reported as `field_too_large` output
  errors and block the export.
- Writing without `--overwrite` could replace a file created by another process during the
  write; the final step now refuses an existing destination atomically.
- Binary and text-to-text codecs (`base64_codec`, `hex_codec`, `rot_13`) were accepted as
  encodings and caused tracebacks; they are now configuration errors (exit code 2).
- `Profile`/`ColumnSpec` objects built directly through the API bypassed validation; they are
  now validated like TOML profiles.
- When saving `--report` failed, stdout still showed `exit_code` 0. Reports now list the report
  artifact (`written`/`failed`) and `summary.exit_code` matches the command's exit code.

### Documentation

- Clarified that parsing follows Python's `csv` module in strict mode: a quote inside an
  unquoted field is kept literally.
