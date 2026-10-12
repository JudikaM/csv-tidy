# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/) as described in [docs/RELEASE.md](docs/RELEASE.md).

## [Unreleased]

### Added

- `csv-tidy profile init INPUT --output PROFILE`: writes a starting profile from a file's
  header. Every column starts as text and nothing is inferred from values or names. Column
  types, required columns, keys, formats, and transformations are chosen with options
  (non-interactive, never prompts) or with `--interactive` guided questions. Existing files
  and the input are protected; cancelling exits with code 130 and writes nothing.
- `csv-tidy ui`: a local browser interface for choosing a file, separator and encoding,
  previewing the data, describing columns or loading a profile, checking, previewing the
  cleaning with before/after values, and saving the cleaned CSV, output profile, report, and
  rules. It runs the same pipeline as the commands on a loopback-only server protected by a
  session key, loads no external resources, and never writes to the chosen file.
- `csv-tidy batch check|clean INPUT...`: processes files and folders with one profile.
  Preview by default; `--apply --output-dir DIR` writes `NAME.clean.csv` per input, with
  optional `--output-schemas` and `--report-dir`. Output collisions and unsafe paths stop the
  batch before anything is read; one failing file never affects the others. Text and JSON
  summaries per file and in total. Exit code 2 if any file failed or was not fully read,
  otherwise 1 if any has data errors, otherwise 0.
- Reports state the validation coverage (`Checked:` / `Not checked:` in text, `coverage` in
  JSON) and add `verdict` and `next_steps`. A run without column rules is reported as
  `PASSED (structure only)` with a pointer to `profile init`.
- Python API: `CleanResult.export_blocked_reason`, `CheckResult.header`, `run_batch`,
  `select_inputs`, `BatchResult`.
- `scripts/benchmark.py` also measures report rendering and export; `docs/USER_TESTING.md`
  has task lists for developers and administrative staff (not yet run with users).

### Changed

- Text reports start with a `Verdict:` line, list unresolved problems first (`Still to fix`),
  and show source problems that were repaired or removed in separate `FIXED` / `REMOVED`
  lists instead of `ERROR [resolved]`. They end with specific next steps. JSON reports keep
  every existing field and value (including issue `severity` and `status`); the new fields
  are additions under report `schema_version` 1. Scripts that parse the *text* layout need
  adjusting; exit codes, the CLI options of `check` and `clean`, profiles, and the API are
  unchanged.
- The README quick start is a four-step check, preview, apply, re-check sequence whose
  commands match the documented installation (`.\.venv\Scripts\csv-tidy.exe`).

### Fixed

- A decoding error was located by counting only LF characters, so a file with CR line breaks
  reported line 1 for bad bytes on line 3. Lines are now counted as the parser counts them
  (LF, CRLF, CR), for every encoding.
- After a decoding error, `physical_lines` stayed 0 and records in front of the bad bytes
  could be missing from the counts. The scan now reports every complete line and record read
  before the failure, and stays incomplete (exit code 2).
- `max_field_chars` relied on the process-wide `csv.field_size_limit`: with two reads running
  at the same time, a read limited to 10 characters could accept a 50-character field. Each
  read now enforces its own limit, and the process-wide value is restored after the last
  read, also after exceptions.
- `export_clean` on a result with an incomplete scan said "0 output error(s) remain". It now
  states the real reason (incomplete scan with the fatal code and line, missing header, or
  the remaining errors) and what to do.

## [0.1.0] - 2026-10-11

Initial early-alpha release.

### Added

- `csv-tidy check` and `csv-tidy clean` (dry run by default, `--apply` to write), also
  available as `python -m csv_tidy`.
- Strict CSV reading (comma/semicolon, UTF-8 with or without BOM, explicit encodings, quoted
  multiline fields) with record indexes and physical line ranges.
- TOML profiles (`schema_version = 1`) with required columns, `text`/`decimal`/`date` types,
  number grammars `id`, `us`, `canonical`, numeric date formats, duplicate-row policy, and
  uniqueness keys.
- Explicit transformations: trim, normalize, deduplicate (keep first), applied in that order,
  followed by output validation.
- Safe export with input/alias protection, overwrite refusal, and per-file atomic writes.
- Generated output profiles (`--output-schema`) for validating and re-cleaning output.
- English text and JSON reports (report `schema_version` 1) and exit codes 0/1/2.
- Python API: `check_file`, `clean_file`, `export_clean`, `load_profile`, `profile_to_toml`.
- Synthetic examples, benchmark script, distribution smoke test, and CI for Linux and
  Windows on Python 3.11 and 3.15.

### Fixed

Defects found by audits of earlier development commits (e1e4a63, 4e5b12a, 8389d1d) and fixed
before this release:

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
- Binary and text-to-text codecs (`base64_codec`, `hex_codec`, `rot_13`) and the `undefined`
  codec were accepted as encodings and caused tracebacks; they are now configuration errors
  (exit code 2).
- `Profile`/`ColumnSpec` objects built directly through the API bypassed validation; they are
  now validated like TOML profiles.
- When saving `--report` failed, stdout still showed `exit_code` 0. Reports now list the report
  artifact (`written`/`failed`) and `summary.exit_code` matches the command's exit code.
- List-valued API settings (for example `Profile(trim=["a"])`) broke output-profile generation
  and `profile_to_toml`; profiles and settings are now validated and held as tuple copies.
- Outside Windows, a file system without hard links made no-clobber writes fall back to a
  non-atomic copy that could leave a partial file; such writes now fail safely instead.

### Documentation

- Clarified that parsing follows Python's `csv` module in strict mode: a quote inside an
  unquoted field is kept literally.
