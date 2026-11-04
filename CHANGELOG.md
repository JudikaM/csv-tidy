# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/) as described in [docs/RELEASE.md](docs/RELEASE.md).

## [Unreleased]

## [1.1.1] - 2026-11-04

Small fixes to the look of the local interface.

**Upgrade notes (from 1.1.0).** Profiles, CLI, reports, and the Python API are unchanged.

### Changed

- Interface: clicking a control in the file card with the mouse no longer draws blue lines
  around it. The card keeps its border while a control in it has focus, and the file area and
  the lists (such as **Encoding** and the lists of step 3) show their focus ring only when
  they are reached with the keyboard. The ring around the chosen separator and file mode is
  unchanged.
- Interface: lists (such as **Encoding** and the lists of step 3) show the same chevron as
  **How to use**, a little further from the edge than the browser's arrow, and it turns while
  the list is open (at once when the system asks for reduced motion). The date list of a
  column rule is slightly wider, so "Like the file (YYYY-MM-DD)" fits.
- Interface: thin scroll bars (a 6-pixel rounded thumb without a track) for the page, the side
  bar, the side panel (when the open **How to use** guide makes it taller than the window),
  and tables, in both themes.

## [1.1.0] - 2026-11-04

A short guide in the local interface.

**Upgrade notes (from 1.0.1).** Profiles, CLI, reports, and the Python API are unchanged.

### Added

- Interface: **How to use** at the bottom of the side panel, a short guide that is closed
  until it is opened: the six steps in one line each, every step name leading to its step,
  and a tip that profiles saved on the page also work with the `csv-tidy` command. It is a
  native disclosure that works with the keyboard and screen readers, and whether it is open
  is remembered in the browser (`csv-tidy-howto`, where the browser allows storage). In wide
  windows the side panel now scrolls on its own when it is taller than the window.

### Removed

- Interface: the unused background layer (the `backdrop` element and its style rule) and its
  style tokens `--nebula-1`, `--nebula-2`, `--nebula-3`, and `--stars`. They were transparent
  in both themes, so the page looks the same.

## [1.0.1] - 2026-11-04

A small clean-up of the local interface.

**Upgrade notes (from 1.0.0).** Profiles, CLI, reports, and the Python API are unchanged.

### Changed

- Interface: the side bar, the narrow-screen top bar, and the browser tab use a small logo
  mark without text (`logo-mark.png`, 64 x 64 pixels), which stays readable at 24 to 32
  pixels. The full logo (`logo.png`) is still served and packaged.

### Removed

- Interface: three unused style tokens, `--header`, `--status-bg`, and `--z-sticky`, from the
  page's style sheet. Nothing used them, so the page looks the same.

## [1.0.0] - 2026-11-04

The first stable release. [docs/STABILITY.md](docs/STABILITY.md) lists everything that 1.x
keeps compatible: profiles, command-line options, exit codes, issue codes, JSON reports, and
the Python API. To get there, a few names were made consistent (with the old command-line
and Python names still accepted), and the local interface was reorganized like a desktop
application with a side bar, a file card, and a side panel.

**Upgrade notes (from 0.5.0).**

- **Profiles:** unchanged. Every 0.x profile works as before; profile `schema_version` stays 1.
- **Command line:** commands written for 0.5 keep working. `--schema`, `--output-schema`, and
  `--output-schemas` now print a warning on stderr; switch to `--profile`, `--output-profile`,
  and `--output-profiles` before 2.0.0, which removes the old names. Exit codes are unchanged.
- **JSON reports:** `schema_version` is now 2. Programs that read reports must accept it and
  the renamed values in the table below; clean reports also have a top-level `artifacts`
  list (the same as `export.artifacts`, which stays). Text reports name artifacts as before.
- **Python API:** `export_clean(output_schema=...)` and `run_batch(output_schemas=...)` keep
  working with a `DeprecationWarning`; use `output_profile=` and `output_profiles=`.
  `ArtifactOutcome.kind` and `BatchResult.mode` use the new values below.
- **Local interface:** every feature works as before; it is laid out differently (see
  Changed). Its look, layout, and internal HTTP API are not covered by the stability promise.

| Where | 0.5.0 | 1.0.0 |
|-------|-------|-------|
| Option (`check`, `clean`, `batch`) | `--schema PROFILE` | `--profile PROFILE` (old name deprecated) |
| Option (`clean`) | `--output-schema PATH` | `--output-profile PATH` (old name deprecated) |
| Option (`batch clean`) | `--output-schemas` | `--output-profiles` (old name deprecated) |
| Report `schema_version` | `1` | `2` |
| Report `mode` (`clean`, `batch`), `BatchResult.mode` | `"dry-run"` | `"dry_run"` (`"apply"` unchanged) |
| Artifact `kind` (reports, `ArtifactOutcome.kind`) | `"output CSV"`, `"output profile"` | `"output_csv"`, `"output_profile"` (`"report"` unchanged) |
| Issue code for a cleaned value longer than `max_field_chars` (stage `output`) | `field_too_large` | `output_field_too_large` (`field_too_large` stays the fatal reading error) |
| Clean report | `export.artifacts` | `artifacts` and `export.artifacts` (the same list) |
| `export_clean` keyword | `output_schema=` | `output_profile=` (old name deprecated) |
| `run_batch` keyword | `output_schemas=` | `output_profiles=` (old name deprecated) |

### Added

- [docs/STABILITY.md](docs/STABILITY.md): what Semantic Versioning covers from 1.0.0
  (profiles, command-line options, exit codes, issue codes, JSON reports, the Python API) and
  what it does not (the look of the local interface, message wording, benchmark numbers), a
  full inventory of that surface, the decisions that led to this release, and the
  deprecation rules. A test keeps the inventory in step with the code.
- Command line: `--profile` (`check`, `clean`, `batch check`, `batch clean`),
  `--output-profile` (`clean`), and `--output-profiles` (`batch clean`). Help text, next-step
  sentences, and the documentation use them.
- Python API: `CleanResult.ok`, `source_errors`, `source_warnings`, and `output_warnings`,
  matching `CheckResult.ok`, `errors`, and `warnings`.
- Python API: `FatalError`, `SourceSettings`, `OutputSettings`, `BatchInput`, and
  `FileOutcome` are exported from `csv_tidy`, so every type that a public function returns or
  contains can be imported from the package.
- Clean reports have a top-level `artifacts` list, like check and batch reports.
- Issue code `output_field_too_large` (error, stage `output`, remedy `max_field_chars`) for a
  cleaned value that is longer than `max_field_chars`.
- Interface: the side bar has **New check** (start again with nothing loaded; it asks first
  when files, rules, or results would be lost, and removes the temporary copies), **Find**
  (shows only the table rows of the current step that contain a word: a column name, a value,
  or a problem; Escape empties and closes it), and **In this session**: every loaded file with
  its row count and whether it is not checked yet, has problems, or is fine, shown as an icon
  and in words. Clicking a file opens its latest result; with several files, the file's
  details, and the results of the other files are kept. A note says that nothing is kept
  after Quit.
- Interface: the side panel shows the current **Profile** (Load, Save), how many **Columns**
  have rules (Edit), the **Unique keys** (Add), the **Output** separator, encoding, line
  ending, and formula protection (Edit), and the **Theme** (Switch). Each action leads to the
  control in step 3.
- Documentation: "Migrating from 0.x" in the README, the interface's limits under "Supported
  conventions and limits" (one session, results in memory, nothing kept after Quit, the size
  limit), a section on working on the interface in CONTRIBUTING.md, the page structure in
  ARCHITECTURE.md, the 1.x support policy in SECURITY.md, and user-testing tasks for the new
  layout with a results table and a screen-reader (NVDA) checklist in docs/USER_TESTING.md.
  The sessions with people and the screen-reader session are planned after 1.0; they have
  not taken place.

### Changed

- Reports: `schema_version` 2. `mode` is `dry_run` instead of `dry-run`, and artifact kinds
  are `output_csv` and `output_profile` instead of `output CSV` and `output profile`; the
  same values in `BatchResult.mode` and `ArtifactOutcome.kind`. Messages and text reports
  still say "output CSV" and "output profile".
- A cleaned value longer than `max_field_chars` is reported as `output_field_too_large`
  instead of `field_too_large`; it still blocks the export.
- Interface: the page is laid out like a desktop application. A side bar on the left holds
  previous/next step buttons, the sections above, links to the files, profile, report, and
  settings parts of the page, and, at the bottom, the logo, version, "Offline & local", the
  theme switch, and Quit (which still asks first). It can be folded to a row of icons, and
  the choice is remembered in this browser. The steps stay in the middle column under one
  page title; a side panel on the right holds the rows above and the notes that were in the
  footer. Below 1100 pixels the side panel moves under the steps; below 720 pixels the side
  bar opens over the page from a bar at the top and keeps the keyboard inside until it is
  closed (Escape or the side-bar button). Every feature works as before.
- Interface: the file, separator, encoding, and one-file/several-files choice are in one input
  card at the top of the middle column, with a **+** button, the size limit, and one primary
  button that checks, then previews the cleaning, then shows the ways to save. A breadcrumb
  (`Files / NAME`) lists the loaded files and opens their latest result; the title shows the
  file name. Steps 1-6 now show one at a time under the card: the step you pick, or the one
  with the newest result (2 after reading a file, 4 after a check, 5 after a cleaning
  preview). The status line sits quietly above the step content.
- Interface: in the dark theme the side bar is #1F1F1F on a #191919 page, divided by a
  #303030 line.
- Interface: the side panel is a card at the right edge of the window; the main column stays
  centered in the space between the side bar and the panel.
- Interface: the dark theme (still the default) uses the colors of VS Code's built-in "Dark
  Modern" theme and is now named "Dark Modern"; a theme chosen earlier is still remembered.
- Interface: every icon is now an inline [Lucide](https://lucide.dev) icon (the set shadcn/ui
  uses), including the Tab separator and the theme switch, which shows a sun or moon in the
  text color as in shadcn/ui's mode toggle; still no external files or requests.
- Interface: the light theme uses the colors of VS Code's built-in "Light+" theme and is now
  named "Light+". Text contrast stays at least 4.5:1 in both themes.
- Interface: the CSV Tidy logo is shown in the side bar and used as the page icon
  (`logo.png`, served by the local server like the other page files).
- Interface: the marked step in the step navigation is gray in both themes instead of indigo.
- Interface accessibility: the bar at the top of narrow windows is a `header` landmark, the
  breadcrumb's file button has a name before the script runs, and every control, landmark,
  focus ring, keyboard path, reduced-motion setting, and color pair was checked automatically
  in both themes at three window widths (see TEST_CASES.md). This was an automated check,
  not a session with a screen reader.
- The saved-profile header of the interface and `profile init`'s next steps name `--profile`.

### Deprecated

- `--schema`, `--output-schema`, and `--output-schemas`: use `--profile`, `--output-profile`,
  and `--output-profiles`. The old names still work, are not shown by `--help`, and print a
  warning on stderr; giving an old and a new name together is a usage error. Removed in 2.0.0.
- `export_clean(output_schema=...)` and `run_batch(output_schemas=...)`: use
  `output_profile=` and `output_profiles=`. The old names raise `DeprecationWarning`; giving
  both names raises `TypeError`. Removed in 2.0.0.

### Fixed

- Interface: pressing the check or preview button right after typing in a field that reads the
  file again (such as "Rows shown in previews") no longer loses the press; it now runs once the
  file was read.
- Documentation: the README options table no longer lists `--max-examples` for `check`
  (only `clean` and `batch clean` have it); CONFIGURATION.md no longer names version 0.4 as
  its scope, and documents `coverage.structure` and the `verdict.state` values of the `clean`
  and `batch` reports; the package docstring names `__all__` as the public API.
- Interface: clicking a step in the step navigation (for example "2. Look") now marks that
  step; before, the mark stayed on the step the work had reached. The mark still moves on by
  itself when choosing a file, checking, or cleaning reaches a new step.
- Documentation: STABILITY.md no longer lists `batch report` as an artifact kind; no report
  ever contained it (the summary written by `batch --report` has the kind `report`).

## [0.5.0] - 2026-10-29

Dates without separators, tab-separated files, per-column formats in `profile init`,
protection against formulas in exported files, a fix for the local interface, and tooling that
checks what the project claims: types, every supported Python version on Linux, Windows, and
macOS, test coverage, dependency vulnerabilities, and code scanning.

**Upgrade notes.** Profiles, CLI options, exit codes, and the Python API of 0.4 keep working
unchanged; everything new is opt-in. JSON reports gain `transformations.neutralize_formulas`
(an empty list when unused). A profile written by 0.5 is still read by 0.4 unless it uses a
tab delimiter, a date format without separators, or `neutralize_formulas`.

### Added

- Date formats without separators, such as `YYYYMMDD` (`20261231`) and `DDMMYYYY`, for source
  and output dates in profiles, options, and the local interface (which lists `YYYYMMDD`).
  They may use only the fixed-width tokens `YYYY`, `MM`, and `DD`; `YYYYMD` and mixed formats
  such as `YYYY-MMDD` are rejected with an explanation.
- Tab-separated files: `delimiter = "\t"` in profiles, `--delimiter tab` and
  `--output-delimiter tab` (a tab character or `\t` also works), a Tab choice in the local
  interface, and tab in the guided `profile init`. The single-column hint also recognizes
  tabs, and next-step commands spell the option as `--delimiter tab`.
- `profile init` options for per-column formats: `--column-number-format COLUMN=FORMAT` and
  `--column-date-format COLUMN=FORMAT`, for files whose columns use different number or date
  formats. They are checked before anything is written.
- Opt-in neutralization of spreadsheet formulas (CSV injection): values of selected text
  columns that start with `=`, `+`, `-`, `@`, a tab, or a carriage return get a leading `'`,
  as OWASP recommends. Select it with `neutralize_formulas` in `[transform]`,
  `--neutralize-formulas COLUMN` (`--no-neutralize-formulas` clears it), or **Repair:
  protect formulas** in the local interface; it works in batch processing and the Python
  API (`Overrides.neutralize_formulas`). It runs after normalize and before deduplicate.
  Number and date columns cannot be selected. JSON reports gain
  `transformations.neutralize_formulas`; `order` and text reports name the step only when
  it is selected, and generated profiles write the key only when it is used.
- README: status badges, quick links, and screenshots of the local interface in its dark and
  light themes (`docs/images/`).
- A code of conduct (Contributor Covenant 2.1), linked from the README and CONTRIBUTING.md and
  included in the source distribution.
- The new-issue page links questions to Discussions and security reports to private
  vulnerability reporting; blank issues stay available for contact requests.

### Changed

- Security reports now go through GitHub private vulnerability reporting instead of a
  detail-free contact-request issue (SECURITY.md).
- Release process: `main` is protected, so a release commit reaches it through a pull request
  with passing CI, and the tag points to the resulting `main` commit (docs/RELEASE.md).
- Type annotations are checked with mypy in strict mode, locally and in every CI job. The
  check found imprecise annotations, which are corrected without any change in behavior; for
  example `OutputError.outcomes` is now declared as a tuple of `ArtifactOutcome`.
- CI tests every supported Python version (3.11 to 3.15) on Linux, and Python 3.11 and 3.15 on
  Windows and macOS. On macOS the distribution smoke test checks that `csv-tidy shortcut
  install` refuses with exit code 2, since shortcuts are made on Windows and Linux only.
- CI measures line and branch coverage of the tests (94% when this was added) and fails below
  92%.
- A dependency audit (pip-audit) checks every package pinned for development and CI against
  published vulnerabilities, on pull requests, on `main`, and weekly.
- CodeQL analyzes the Python code and the local interface's JavaScript with the
  `security-extended` queries, on pull requests, on `main`, and weekly.
- Package metadata: Documentation, Source, and Releases links.

### Fixed

- Local interface: a refused request (another origin, a missing session key, or a body that
  is not JSON) could reset the connection on Windows before the answer arrived, so the
  client saw a network error instead of the refusal. The server now reads the rest of a
  refused request's body (up to 1 MB) before it closes the connection.

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
