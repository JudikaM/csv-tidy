# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/) as described in [docs/RELEASE.md](docs/RELEASE.md).

## [Unreleased]

## [0.4.1] - 2026-10-14

A new look for the local interface, and a port fix on Windows. The CLI, profiles, reports,
exit codes, and the Python API are unchanged.

### Changed

- Interface: a new look with a dark "Cosmos" theme (the default) and a light theme, switched
  in the header and remembered by the browser. Each step is a card with a numbered badge; the
  status strip shows the current step in a step navigation; files can be dropped onto the
  file area; mode and separator choices are cards; Quit asks for confirmation in a dialog; a
  short notice confirms saved files. Everything stays local (no web fonts or external styles;
  Inter and JetBrains Mono are used only when installed), and text contrast is at least 4.5:1
  in both themes.

### Fixed

- On Windows, a second `csv-tidy ui --port N` could bind the port of a running one (Python
  enables address reuse, which Windows treats as port sharing), so the new page was refused.
  The port is now claimed exclusively and the second start fails with an explanation.

## [0.4.0] - 2026-10-14

Start, update, and use the local interface without a command line.

**Upgrade notes.** Nothing changes for the CLI options, profiles, or exit codes. JSON reports
gain the `remedy` field on every issue. After updating, run `csv-tidy shortcut install` once
per user to get the icons.

### Added

- `csv-tidy-ui`: starts the local interface without a console window (a pip `gui-scripts`
  entry point). It stops by itself 10 minutes after its page was closed; the page checks in
  every minute. `csv-tidy ui --idle-minutes N` offers the same from a command line.
- `csv-tidy shortcut install|remove`: a **CSV Tidy** icon on the Desktop and in the Start
  Menu and an **Update CSV Tidy** entry (Windows); desktop entries on Linux. Shortcuts of
  other programs with the same names are never changed or removed.
- `csv-tidy update [--check] [--version X.Y.Z] [--pause]`: installs the latest (or the given)
  GitHub release with pip, verified against the SHA-256 that GitHub publishes for the wheel.
  The only command that connects to the internet, and only when run.
- Issues have a `remedy` code (JSON reports: `remedy` on every issue).
- Interface: suggestions name the page's own controls instead of command-line options; date
  formats are chosen from a list with examples, with **Other…** for any supported format; a
  stopped server is reported with a pointer to the icon.

### Changed

- The interface's date fields are lists instead of free text; profiles with other formats
  load into **Other…** unchanged.

## [0.3.0] - 2026-10-14

The local interface now covers what was only possible on the command line: several files
with one set of rules, the field-size limit, and the report and preview limits.

**Upgrade notes.** Nothing changes for the CLI, profiles, JSON reports, or exit codes. Added
API is optional (`BatchInput.label`). The interface keeps its one-file flow as the default.

### Added

- Interface: **several files with the same rules**. Choose many files, set or load the rules
  once, check or preview all of them through `run_batch` (the same function as
  `csv-tidy batch`), see one row per file with its status and reason, open **Details** for a
  file, save a cleaned CSV per ready file, or **Save all results as ZIP** (cleaned CSV and
  output profile per ready file, a report per file, and the batch summary). Blocked or
  unreadable files are never exported and are named with their reason.
- Interface: **More settings** has the longest allowed value (`max_field_chars`) and the
  number of problems listed, changed values listed, and rows shown in previews. Saved
  reports use the same limits; totals stay complete.
- `BatchInput.label`: names a file in batch outcomes and reports instead of its path.
- `scripts/benchmark.py` measures a five-file batch through `run_batch` and through the
  interface (batch preview plus ZIP). `scripts/smoke_dist.py` runs the interface's batch and
  ZIP from the installed wheel.

### Changed

- `csv-tidy ui --max-file-mb` also limits the total size of several files chosen together.

## [0.2.0] - 2026-10-14

Second early-alpha release: a profile creator, a local browser interface, batch processing,
clearer reports, and four reliability fixes. The code was published in commit `0cdae3a`; this
release sets the version and aligns the documentation.

**Upgrade notes.** Profiles (`schema_version = 1`), JSON reports (report `schema_version` 1),
exit codes, the options of `check` and `clean`, and the Python API of 0.1.0 keep working
unchanged. JSON reports gain fields; the layout of *text* reports changed, so scripts should
read JSON. The process-wide `csv.field_size_limit` is no longer left modified by a read.

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
- `scripts/smoke_dist.py` also checks that the wheel and the source distribution contain the
  interface's page, style sheet, and script, and exercises `profile init`, `batch`, and the
  interface server from the installed wheel. A release-consistency test ties the package
  version to the changelog and the documented sample output.

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
