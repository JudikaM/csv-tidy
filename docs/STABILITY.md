# Stability and compatibility

This document defines what Datakrit keeps stable from version **1.0.0** on, and lists that
surface in full. Before 1.0.0 the 0.x rules in [RELEASE.md](RELEASE.md) applied: no silent
changes, every change in the changelog, and incompatible changes only with a minor version
bump and a migration note.

Status: **in force from 1.0.0**. The decisions at the end settled the questions that the
first draft of the inventory raised; the changes they required were made in 1.0.0, each with
a migration note in the [changelog](../CHANGELOG.md#100---2026-11-04). 2.0.0 gave the product
its current name and removed the aliases deprecated in 1.0.0 (see
[The rename to Datakrit in 2.0.0](#the-rename-to-datakrit-in-200)). The inventory below
describes 2.1.1, which added distribution channels and changed nothing in it.

## What Semantic Versioning covers

From 1.0.0, Datakrit follows [Semantic Versioning](https://semver.org/) for the following
surface. The inventory below lists every item.

1. **Profiles**: the TOML keys, their allowed values, defaults, and meaning, and
   `schema_version`. This includes the output profiles that `clean --output-profile` writes
   and the profiles that `profile init` and the local interface save.
2. **Command line**: commands, subcommands, arguments, options, their defaults, and the rules
   for combining them (for example "`--apply` requires `--output`").
3. **Exit codes** of every command.
4. **Issue codes**, their severity, and the `remedy` values.
5. **JSON reports**: field names, types, nesting, enumerated values, and report
   `schema_version`, for `check`, `clean`, and `batch`.
6. **Files written**: the names `batch` gives its outputs, the CSV serialization rules, and the
   safety guarantees (inputs are never written, existing files need `--overwrite`, writes are
   atomic per file).
7. **The documented Python API**: the names exported by `datakrit` (`datakrit.__all__`), their
   parameters, return types, attributes, and exceptions.
8. **Program names**: `datakrit`, `datakrit-ui`, and `python -m datakrit`.
9. **Data behavior**: number grammars, date-format tokens, reading rules, validation rules,
   and the transformation order, as described in [CONFIGURATION.md](CONFIGURATION.md).

### Major, minor, and patch releases

| Release | May contain | Never contains |
|---------|-------------|----------------|
| Major (`2.0.0`) | Incompatible changes, each with a migration note; a new profile or report `schema_version` with an upgrade path; removal of deprecated items | Silent changes |
| Minor (`1.1.0`) | New commands and options; new optional profile keys whose default keeps the previous behavior; new JSON fields; new `remedy` values; new warning codes; new error codes for a new, opt-in setting; deprecations | Removed or renamed keys, options, fields, or codes; changed defaults; changed meaning of an existing setting; a file that passed before failing without a setting change |
| Patch (`1.0.1`) | Bug fixes, documentation, performance, and changes outside the covered surface | New features or deprecations |

A bug fix may make a check report a problem it missed before, if the documented rule already
required it. Such a fix is listed under **Fixed** with the affected rule and, when it can
change exit codes, an upgrade note.

### Rules for programs that read Datakrit output

- Read the JSON report, not the text report. Ignore JSON fields you do not know: minor releases
  add fields.
- Check `schema_version`: 2.x releases write `3`. 1.x releases wrote `2` and 0.x releases
  `1`; the changelog lists the differences (from `2` to `3` only `tool.name` changed).
- Accept issue codes you do not know, and decide by their `severity`: minor releases add
  codes. Treat an unknown `remedy` value like `null`.
- Fields that are `null` today stay present. `status` (source issues of `clean`) and
  `introduced` (output issues) appear only on the issues they describe.
- Use exit codes and `summary.exit_code` to decide success.

### Deprecation

A covered item is removed or renamed only in a major release. Before that, a minor release
marks it deprecated in the changelog and in the documentation. A deprecated option or profile key keeps working and prints a warning on
stderr that names its replacement; a deprecated Python keyword argument keeps working and
raises `DeprecationWarning` naming its replacement, and giving the old and the new name
together raises `TypeError`. Reports do not change because of a deprecation.

Deprecated now: nothing.

Deprecated in 1.0.0 and removed in 2.0.0 (giving a removed option is a usage error, exit code
2, that names its replacement; a removed keyword argument raises `TypeError`):

| Removed | Use instead |
|---------|-------------|
| `--schema` (`check`, `clean`, `batch check`, `batch clean`) | `--profile` |
| `--output-schema` (`clean`) | `--output-profile` |
| `--output-schemas` (`batch clean`) | `--output-profiles` |
| `export_clean(output_schema=...)` | `export_clean(output_profile=...)` |
| `run_batch(output_schemas=...)` | `run_batch(output_profiles=...)` |

Deprecated in 1.2.0 and changed in 2.0.0: the product name, with every program, module,
distribution, report, shortcut, and repository name that carries it (see
[The rename to Datakrit in 2.0.0](#the-rename-to-datakrit-in-200)).

### Supported Python versions

Datakrit supports Python 3.11 and newer, as listed in `pyproject.toml` and tested in CI.
Support for a Python version ends only in a minor release, after that version reached its end
of life, and the changelog announces it.

## What is not covered

These may change in any release, including patch releases, and are listed in the changelog
when users would notice:

- The look, layout, navigation, and wording of the local interface, its download names, and
  its internal HTTP endpoints (`/api/...`), which only its own page uses.
- The wording of human-readable text: messages, suggestions, verdict headlines, `next_steps`
  sentences, `--help` text, and the layout of text reports. The issue codes, `remedy`, and
  `verdict.state` carry the meaning that programs need.
- Benchmark numbers in [BENCHMARKS.md](BENCHMARKS.md).
- Names that are not exported by `datakrit` (modules such as `datakrit.schema` or
  `datakrit.ui`, their functions such as `schema.validate_profile` or `batch.batch_report`,
  and names that start with `_`), unless this document lists them.
- The order of keys inside JSON objects, and whitespace in JSON.
- The temporary files of the local interface and the `datakrit-ui-error.txt` file.
- The Windows app's look (it is the local interface) and its packaging: the folder layout,
  the bundled Python and its version, the files next to `Datakrit.exe`, the zip's size, and
  the smoke mode (`DATAKRIT_UI_URL_FILE`), which exists for automated checks.

## Distribution channels

From 2.1.1 every release is published as:

- the wheel `datakrit-X.Y.Z-py3-none-any.whl` and the sdist `datakrit-X.Y.Z.tar.gz` on the
  GitHub release, each with a published SHA-256 (`datakrit update` relies on the wheel);
- the same two files on PyPI, as the project `datakrit` (`pip install datakrit`);
- the Windows app `Datakrit-X.Y.Z-windows-x64.zip` with `Datakrit-X.Y.Z-windows-x64.zip.sha256`
  on the GitHub release: a folder `Datakrit` whose `Datakrit.exe` starts the local interface.

Removing one of these channels is announced in the changelog of a minor release first. The
app has no command line; the programs covered above are those of a pip install.

## Inventory of the covered surface

This inventory describes Datakrit 2.1.1. Details and examples are in
[CONFIGURATION.md](CONFIGURATION.md) (behavior) and [ARCHITECTURE.md](ARCHITECTURE.md)
(result types).

### Profiles (`schema_version = 1`)

| Table | Key | Values | Default |
|-------|-----|--------|---------|
| (top) | `schema_version` | `1` (required) | — |
| `[source]` | `delimiter` | `","`, `";"`, `"\t"` | `","` |
| `[source]` | `encoding` | a Python text encoding | `"utf-8"` |
| `[source]` | `number_format` | `"id"`, `"us"`, `"canonical"` | `"canonical"` |
| `[source]` | `date_format` | a date format (see CONFIGURATION.md) | `"YYYY-MM-DD"` |
| `[source]` | `max_field_chars` | integer 1 .. 100000000 | `131072` |
| `[output]` | `delimiter`, `encoding`, `number_format`, `date_format` | as in `[source]` | the resolved `[source]` value |
| `[output]` | `line_ending` | `"crlf"`, `"lf"` | `"crlf"` |
| `[columns.NAME]` | `type` | `"text"`, `"decimal"`, `"date"` | `"text"` |
| `[columns.NAME]` | `required` | boolean | `false` |
| `[columns.NAME]` | `number_format` | as in `[source]`; decimal columns only | `[source] number_format` |
| `[columns.NAME]` | `date_format` | a date format; date columns only | `[source] date_format` |
| `[duplicates]` | `rows` | `"warn"`, `"ignore"` | `"warn"` |
| `[duplicates]` | `keys` | list of lists of column names | `[]` |
| `[transform]` | `trim` | list of column names | `[]` |
| `[transform]` | `normalize` | list of decimal/date column names | `[]` |
| `[transform]` | `neutralize_formulas` | list of text column names | `[]` |
| `[transform]` | `deduplicate` | `"off"`, `"rows"`, `"keys"` | `"off"` |

Unknown keys and invalid values are refused (exit code 2). Number grammars: `id`, `us`,
`canonical`. Date tokens: `YYYY`, `MM`, `M`, `DD`, `D`; separators `-`, `/`, `.`, or none
(fixed-width tokens only). Profiles written by 0.x keep working unchanged.

### Commands and options

Every command also has `--help`; `datakrit --version` prints the version.

| Command | Arguments and options |
|---------|-----------------------|
| `check` | `INPUT`; source: `--profile`, `--delimiter`, `--encoding`, `--number-format`, `--date-format`; report: `--format`, `--report`, `--max-details` (default 100), `--overwrite` |
| `clean` | as `check`, plus output: `--output-delimiter`, `--output-encoding`, `--output-number-format`, `--output-date-format`, `--line-ending`; transformations: `--trim`, `--normalize`, `--neutralize-formulas`, `--no-trim`, `--no-normalize`, `--no-neutralize-formulas`, `--deduplicate`; mode: `--dry-run` (default) or `--apply`; `--output`, `--output-profile`, `--max-examples` (default 10) |
| `batch check` | `INPUT...` (files and folders); `--pattern` (default `*.csv`), `--recursive`, `--report-dir`; the source and report options of `check` |
| `batch clean` | as `batch check`, plus the output and transformation options of `clean`, `--dry-run`/`--apply`, `--output-dir`, `--output-profiles`, `--max-examples` |
| `profile init` | `INPUT`; `--output` (required), `--overwrite`, `--interactive`; `--delimiter`, `--encoding`, `--number-format`, `--date-format`; `--decimal`, `--date`, `--required`, `--column-number-format COLUMN=FORMAT`, `--column-date-format COLUMN=FORMAT`, `--key COLUMN [COLUMN ...]`; `--trim`, `--normalize`, `--deduplicate`, `--output-number-format`, `--output-date-format` |
| `ui` | `--port` (default 0: any free port), `--no-browser`, `--max-file-mb` (default 200), `--idle-minutes` (default 0: never) |
| `shortcut install` | `--folder`, `--no-desktop` |
| `shortcut remove` | `--folder` |
| `update` | `--check`, `--version X.Y.Z`, `--pause` |

`--schema`, `--output-schema`, and `--output-schemas`, deprecated in 1.0.0, were removed in
2.0.0 (see [Deprecation](#deprecation)).

Delimiter options accept `,`, `;`, and `tab` (or a tab character or `\t`). `--trim`,
`--normalize`, `--neutralize-formulas`, `--decimal`, `--date`, `--required`, `--key`, and the
per-column format options are repeatable. Precedence: option > profile > default.

Programs: `datakrit` (console), `datakrit-ui` (no console window; stops 10 minutes after its
page was last open), and `python -m datakrit` (same as `datakrit`). Shortcut files:
`Datakrit.lnk` and `Update Datakrit.lnk` (Windows), `datakrit.desktop` and
`datakrit-update.desktop` (Linux).

`datakrit update` relies on each GitHub release of `JudikaM/datakrit` carrying the wheel
`datakrit-X.Y.Z-py3-none-any.whl` with a published SHA-256 digest; every 2.x release does
so. It installs 2.0.0 and newer: `update --version` with an earlier version is refused (exit
code 2) with a hint to install that wheel by hand from the Releases page.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success: `check` found no source errors (warnings allowed); `clean` has no remaining output errors; `profile init`, `ui`, `shortcut`, and `update` finished |
| 1 | Data errors: `check` found source errors; `clean` has output errors left (nothing exported); `batch`: some file has data errors and none failed |
| 2 | Usage, profile or option, read, decoding/parsing, or write failure (including a failed `--report`); an incomplete scan; `batch`: some file failed or was not fully read; `ui` could not start; `update` could not reach GitHub or pip failed |
| 130 | Cancelled by the user (Ctrl+C, or cancelling `profile init --interactive`) |

### Issue codes

| Code | Severity | `remedy` |
|------|----------|----------|
| `empty_file` | error | `null` |
| `no_records` | warning | `null` |
| `blank_line` | warning (source only) | `null` |
| `empty_header` | error | `null` |
| `duplicate_header` | error | `null` |
| `header_whitespace` | warning | `null` |
| `possible_wrong_delimiter` | warning | `delimiter` |
| `missing_column` | error | `null` |
| `inconsistent_columns` | error | `null` |
| `missing_required` | error | `null` |
| `invalid_number` | error | `trim` or `number_format` |
| `invalid_date` | error | `trim`, `date_format`, or `null` (not a calendar date) |
| `duplicate_record` | warning | `deduplicate_rows` |
| `duplicate_key` | error | `deduplicate_keys` |
| `decode_error` | fatal (source only) | `encoding` |
| `malformed_csv` | fatal (source only) | `quoting` |
| `field_too_large` | fatal (source only): a field longer than `max_field_chars` stops reading | `max_field_chars` |
| `output_field_too_large` | error (output only): a cleaned value is longer than `max_field_chars` | `max_field_chars` |

`clean` validates both the source (`stage: "source"`) and the cleaned result
(`stage: "output"`); every code can appear in both stages unless the table says otherwise.

Severities: `error`, `warning`, `fatal`. Stages: `source`, `output`. `remedy` values: `trim`,
`number_format`, `date_format`, `deduplicate_rows`, `deduplicate_keys`, `delimiter`,
`encoding`, `quoting`, `max_field_chars`, or `null`.

### JSON reports (`schema_version = 3`)

Every report has `schema_version`, `tool` (`name`, `version`), `command`, `verdict` (`state`,
`headline`), `summary` (with `exit_code`), and `next_steps` (list of sentences).

| Report | Fields |
|--------|--------|
| `check` | `source` (`path`, `profile`, `delimiter`, `encoding`, `bom`, `number_format`, `date_format`, `max_field_chars`); `scan` (`complete`, `data_records`, `physical_lines`, `blank_lines`, `fatal_error`: `null` or `code`, `message`, `line`); `coverage` (`scope`, `structure`, `header_columns`, `declared_columns`: list of `column`, `type`, `required`, `format`; `undeclared_columns`, `unchecked_columns`, `unique_keys`, `duplicate_rows`); `summary` (`status`, `errors`, `warnings`, `fatal`, `exit_code`); `issues`; `details` (`limit`, `total`, `shown`, `truncated`); `artifacts` |
| `clean` | `mode`; `source`, `scan`, `coverage` as in `check`; `output` (`delimiter`, `encoding`, `number_format`, `date_format`, `line_ending`); `transformations` (`order`, `trim`, `normalize`: list of `column`, `type`, `from`, `to`; `neutralize_formulas`, `deduplicate`); `changes` (`changed_fields`, `changed_records`, `removed_records`, `output_records`, `examples`: list of `record`, `line_start`, `column`, `before`, `after`, `steps`; `removed`: list of `record`, `line_start`, `reason`, `kept_record`, `key`; `examples_limit`, `examples_truncated`); `source_issues` (`errors`, `warnings`, `fatal`, `resolved`, `unresolved`, `removed`, `items`); `output_issues` (`errors`, `warnings`, `introduced`, `items`); `details` (`limit`, `source_total`, `output_total`, `shown`, `truncated`); `summary` (`status`, `export_ready`, `output_errors`, `exit_code`); `artifacts`; `export` (`artifacts`, the same list) |
| `batch` | `action`, `mode`, `profile`; `files`: list of `path`, `status`, `exit_code`, `data_records`, `errors`, `warnings`, `output_errors`, `changed_fields`, `removed_records`, `structure_only`, `error`, `artifacts`; `totals` (`files`, `ok`, `data_errors`, `failed`, `data_records`, `errors`, `warnings`, `changed_fields`, `removed_records`, `written`); `summary` (`exit_code`); `artifacts` |

Each issue: `code`, `severity`, `stage`, `record`, `line_start`, `line_end`, `column`, `value`
(at most 200 characters), `value_truncated`, `message`, `suggestion`, `related_record`,
`related_line`, `remedy`; source issues of `clean` add `status`, output issues add
`introduced`. Each artifact: `kind`, `path`, `status`, `error`.

| Field | Values |
|-------|--------|
| `command` | `check`, `clean`, `batch` |
| `action` (batch) | `check`, `clean` |
| `mode` | `dry_run`, `apply` (`clean`, `batch clean`); `null` for `batch check` |
| `verdict.state` | `check`: `passed`, `passed_structure_only`, `failed`, `incomplete`; `clean`: `ready`, `blocked`, `incomplete`; `batch`: `ok`, `ok_structure_only`, `data_errors`, `failed` |
| `summary.status` | `check`: `valid`, `invalid`, `incomplete`; `clean`: `ready`, `blocked`, `incomplete` |
| `files[].status` (batch) | `valid`, `invalid`, `ready`, `blocked`, `incomplete`, `failed` |
| `coverage.scope` | `structure_only`, `structure_and_values` |
| issue `status` | `resolved`, `unresolved`, `removed` |
| `changes.examples[].steps` | `trim`, `normalize`, `neutralize_formulas` |
| `transformations.order` | `trim`, `normalize`, `neutralize_formulas` (only when selected), `deduplicate` |
| `changes.removed[].reason` | `duplicate_record`, `duplicate_key` |
| artifact `kind` | `output_csv`, `output_profile`, `report` (also the summary report that `batch --report` writes) |
| artifact `status` | `written`, `not_written`, `failed` |

Reports contain no timestamps: the same input and settings give the same report.

### Files written

- `clean --apply`: the paths given with `--output`, `--output-profile`, and `--report`.
- `batch clean --apply --output-dir DIR`: `DIR/NAME.clean.csv`, with `--output-profiles` also
  `DIR/NAME.output.toml`; `--report-dir RDIR`: `RDIR/NAME.report.json` (`.txt` with
  `--format text`). Files from subfolders keep their subfolder.
- CSV output: minimal quoting with doubled quotes, the output delimiter, encoding, and line
  ending. Field values of unselected columns are unchanged.

### Python API

Exported by `datakrit` (`datakrit.__all__`):

| Name | Kind | Stable parts |
|------|------|--------------|
| `__version__` | string | the package version |
| `check_file(path, profile=None, *, overrides=None)` | function | returns `CheckResult` |
| `clean_file(path, profile=None, *, overrides=None)` | function | returns `CleanResult`; writes nothing |
| `export_clean(result, output, *, output_profile=None, overwrite=False)` | function | returns a tuple of `ArtifactOutcome`; raises `OutputError` |
| `load_profile(path)` | function | returns `Profile`; raises `ProfileError` |
| `profile_to_toml(profile, header="")` | function | TOML text of a validated profile |
| `select_inputs(inputs, pattern="*.csv", recursive=False)` | function | list of `BatchInput` |
| `run_batch(action, inputs, profile=None, *, overrides, apply, output_dir, output_profiles, report_dir, report_format, overwrite, max_details, max_examples, extra_artifacts)` | function | returns `BatchResult` |
| `CheckResult` | class | `source_path`, `profile_path`, `settings`, `scan`, `issues`, `source_file`, `profile_file`, `header`, `errors`, `warnings`, `exit_code`, `ok` |
| `CleanResult` | class | `source_path`, `profile_path`, `settings`, `scan`, `header`, `rows`, `source_issues`, `output_issues`, `changes`, `removed`, `output_profile`, `source_file`, `profile_file`, `source_errors`, `source_warnings`, `output_errors`, `output_warnings`, `export_ready`, `export_blocked_reason`, `exit_code`, `ok`, `csv_text()`, `output_profile_toml()` |
| `ScanInfo` | class | `complete`, `data_records`, `physical_lines`, `blank_lines`, `bom`, `fatal` (a `FatalError` or `None`) |
| `FatalError` | class | `code`, `message`, `line` |
| `Issue` | class | `code`, `severity`, `message`, `suggestion`, `stage`, `record`, `line_start`, `line_end`, `column`, `value`, `related_record`, `related_line`, `status`, `introduced`, `remedy` |
| `FieldChange` | class | `record`, `line_start`, `column`, `before`, `after`, `steps` |
| `RemovedRecord` | class | `record`, `line_start`, `reason`, `kept_record`, `key` |
| `ArtifactOutcome` | class | `kind` (`output_csv`, `output_profile`, `report`), `path`, `status`, `error` |
| `BatchInput` | class | `path`, `relative`, `label`, `shown` |
| `BatchResult` | class | `action`, `mode` (`dry_run`, `apply`, or `None`), `profile_path`, `files` (a tuple of `FileOutcome`), `exit_code` |
| `FileOutcome` | class | `path`, `relative`, `status`, `exit_code`, `data_records`, `errors`, `warnings`, `output_errors`, `changed_fields`, `removed_records`, `structure_only`, `artifacts`, `error` |
| `Profile` | class | one field per profile key (`source_delimiter`, `source_encoding`, `source_number_format`, `source_date_format`, `max_field_chars`, `output_delimiter`, `output_encoding`, `output_number_format`, `output_date_format`, `line_ending`, `columns`, `duplicate_rows`, `duplicate_keys`, `trim`, `normalize`, `deduplicate`, `neutralize_formulas`), `path`, `resolved_path` |
| `ColumnSpec` | class | `name`, `type`, `required`, `number_format`, `date_format` |
| `Overrides` | class | `delimiter`, `encoding`, `number_format`, `date_format`, `output_delimiter`, `output_encoding`, `output_number_format`, `output_date_format`, `line_ending`, `trim`, `normalize`, `deduplicate`, `neutralize_formulas` |
| `Settings` | class | `source` (a `SourceSettings`), `output` (an `OutputSettings`), `columns`, `duplicate_rows`, `duplicate_keys`, `trim`, `normalize`, `deduplicate`, `neutralize_formulas`, `column()`, `source_format()`, `output_format()` |
| `SourceSettings` | class | `delimiter`, `encoding`, `number_format`, `date_format`, `max_field_chars` |
| `OutputSettings` | class | `delimiter`, `encoding`, `number_format`, `date_format`, `line_ending` |
| `DatakritError` | exception | base class of the three below |
| `ProfileError`, `InputError`, `OutputError` | exceptions | `OutputError.outcomes` lists artifacts already written |

Result and settings classes are frozen dataclasses. New attributes and new keyword-only
parameters with defaults may be added in minor releases. Core functions never print or exit.

## The rename to Datakrit in 2.0.0

Decided by the maintainer on 2026-11-05, announced as a deprecation in 1.2.0, and done in
2.0.0 (released 2026-11-05): **the product is called Datakrit.** Every program, module,
distribution, error class, report `tool.name`, shortcut, interface storage key, and the
repository address took the new name. There are no aliases for the old names: no old command
and no import shim. The [changelog's upgrade notes](../CHANGELOG.md#upgrading-to-200) give
the old and the new value of every renamed item and the two upgrade paths.

### Changes made in 2.0.0

| Change | Compatibility |
|--------|---------------|
| Programs `datakrit`, `datakrit-ui`, and `python -m datakrit`; module, distribution, and wheel `datakrit` | Incompatible: scripts and imports use the new names |
| Exception base class `DatakritError` | Incompatible: `except` clauses use the new name |
| Report `tool.name` is `datakrit`, report `schema_version` is `3`; nothing else in the reports changed | Incompatible: report `schema_version` 3 |
| `--schema`, `--output-schema`, `--output-schemas`, `export_clean(output_schema=...)`, and `run_batch(output_schemas=...)` removed (deprecated in 1.0.0) | Incompatible: use the new names, available since 1.0.0 |
| `update` installs only Datakrit releases of `JudikaM/datakrit`, 2.0.0 and newer | Earlier versions are installed by hand from the Releases page |
| Shortcuts "Datakrit" and "Update Datakrit"; `shortcut install` and `shortcut remove` also remove the shortcuts that the 1.x versions made, and keep files with those names that belong to other programs | Compatible: the 1.2.0 update runs `python -m datakrit shortcut install [--no-desktop]` |
| Interface storage keys `datakrit-theme`, `datakrit-nav`, `datakrit-howto`; a choice saved by 1.x moves to its new key when the page loads | Compatible: choices are kept |

Profiles keep `schema_version = 1`: profiles written by 0.x and 1.x, and the output profiles
of 1.x, load unchanged and give the same results. The tests compare the results of every
example profile with those of the last 1.x release.

## Decisions for 1.0

The maintainer answered the questions raised by the first draft of the inventory on
2026-11-04. The changes they required were made in 1.0.0, with a migration note for each in
the changelog; the inventory above already includes them.

### Kept as they are

| # | Topic | Decision |
|---|-------|----------|
| 2 | `--output` is the cleaned CSV in `clean` and the profile file in `profile init` | Kept |
| 3 | `update --version X.Y.Z` next to `datakrit --version` | Kept |
| 4 | `verdict.state` differs per report (`check`: `passed`/`failed`; `batch`: `ok`/`data_errors`; `clean`: `ready`/`blocked`) | Frozen as they are, documented per report in [CONFIGURATION.md](CONFIGURATION.md#reports) |
| 12 | Defaults that differ: `--max-details` 100 (CLI) and 200 (interface); `run_batch` writes per-file reports as JSON, the CLI as text | Frozen as they are |
| 13 | Settings without an option (`max_field_chars`, `[duplicates] rows`; `profile init` cannot record `neutralize_formulas` or output delimiter, encoding, line ending) | Not needed for 1.0; options may be added in 1.x minor releases |
| 14 | Layout of text reports, including the first two lines | Not covered; programs read JSON |

### Policy

- **New issue codes (9).** A minor release may add issue codes, including an error code for a
  new, opt-in setting. Programs that read reports must accept codes they do not know and
  decide by `severity` (see "Rules for programs that read Datakrit output").
- **Public Python API (10).** The public API is exactly `datakrit.__all__`. Every type that a
  public function returns or raises, or that a returned object contains, is exported. Other
  names, including module functions such as `schema.validate_profile`,
  `schema.canonical_profile`, and `batch.batch_report`, are internal.

### Changes made in 1.0.0

| # | Change | Compatibility |
|---|--------|---------------|
| 1 | Add `--profile`, `--output-profile` (`clean`), and `--output-profiles` (`batch clean`). `--schema`, `--output-schema`, and `--output-schemas` keep working as deprecated aliases that print a warning on stderr naming the new option; they are removed in 2.0.0. Help text, next-step sentences, documentation, and examples use the new names | Compatible: old commands keep working |
| 5 | Artifact `kind` values become identifiers: `output CSV` → `output_csv`, `output profile` → `output_profile` (`report` is unchanged). Also `ArtifactOutcome.kind` in the Python API | Incompatible: report `schema_version` 2 |
| 6 | `mode` value `dry-run` → `dry_run` (`apply` is unchanged), in `clean` and `batch` reports and in `BatchResult.mode` | Incompatible: report `schema_version` 2 |
| 7 | `clean` reports gain a top-level `artifacts` list, the same as `export.artifacts`, which stays | Compatible addition |
| 8 | A cleaned value longer than `max_field_chars` gets its own code, `output_field_too_large` (severity `error`, stage `output`, remedy `max_field_chars`); `field_too_large` stays the fatal reading error | Incompatible: released with report `schema_version` 2 |
| 10 | Export `FatalError`, `SourceSettings`, `OutputSettings`, `BatchInput`, and `FileOutcome` from `datakrit`; ARCHITECTURE.md describes the module functions it mentions as internal | Compatible addition |
| 11 | `CleanResult` gains `ok` (exit code 0), `source_errors`, `source_warnings`, and `output_warnings`, matching `CheckResult.errors`, `warnings`, and `ok` | Compatible addition |
| 16 | The Python keyword arguments follow decision 1: `export_clean(output_profile=...)` and `run_batch(output_profiles=...)`. `output_schema` and `output_schemas` keep working as deprecated aliases that raise `DeprecationWarning`; passing the old and the new name together raises `TypeError`; the aliases are removed in 2.0.0 (decided 2026-11-04) | Compatible: old calls keep working |

Reports written by 1.0.0 carry `schema_version: 2`; no option writes version 1. The changelog
gives the old and new value for every renamed item.

Inventory correction: the first draft listed `batch report` as an artifact `kind`. No report
ever contained it: it was only the word that error messages use for the summary file of
`batch --report`, whose artifact has always had the kind `report`. Decision 5 therefore had
nothing to rename there.

### Documentation corrections (15)

Made in the pull request that added this document: the README options table no longer lists
`--max-examples` for `check`; CONFIGURATION.md no longer names a version in its title
paragraph and documents `coverage.structure` and the verdict states of every report; the
package docstring points to `__all__` as the public API.

## Conditions for 1.0.0

1.0.0 was released when these held:

- every question of the inventory was answered and every change it required was made, each
  with a migration note in the changelog;
- the automatic checks of the local interface passed: names, roles, landmarks, focus order
  and visibility, keyboard-only use, reduced motion, and contrast in both themes, in a
  headless browser at three window widths (see [TEST_CASES.md](../TEST_CASES.md));
- the release checks of [RELEASE.md](RELEASE.md) passed, and CI was green on the exact `main`
  commit that was tagged.

Planned after 1.0 (not done for 1.0.0): sessions with people using the
[user testing plan](USER_TESTING.md), and a session with a screen reader (NVDA on Windows)
following its checklist. Findings from them are handled in 1.x releases under the rules
above.
