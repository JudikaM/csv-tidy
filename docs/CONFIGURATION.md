# Configuration and data contracts

This is the authoritative reference for CSV Tidy 0.4 profiles, options, defaults, and the
input/output contracts of `check`, `clean`, `profile init`, `batch`, `ui`, `shortcut`, and
`update`.

## Profiles

A profile is a strict TOML file. Unknown keys, wrong types, unsupported values, and
inconsistent settings are rejected with an error (exit code 2); nothing is silently ignored.

```toml
schema_version = 1            # required; only 1 is supported

[source]                      # how to read the input
delimiter = ";"               # "," or ";"                         default ","
encoding = "utf-8"            # a Python text encoding              default "utf-8"
number_format = "id"          # "id", "us" or "canonical"           default "canonical"
date_format = "DD/MM/YYYY"    # see "Date formats"                  default "YYYY-MM-DD"
max_field_chars = 131072      # 1 .. 100000000                       default 131072

[output]                      # how to write cleaned data; each key defaults to the
delimiter = ";"               # resolved [source] value
encoding = "utf-8"
number_format = "canonical"   # used only for columns listed in transform.normalize
date_format = "YYYY-MM-DD"    # used only for columns listed in transform.normalize
line_ending = "crlf"          # "crlf" or "lf"                      default "crlf"

[columns.amount]              # one table per declared column (names are case-sensitive)
type = "decimal"              # "text", "decimal" or "date"         default "text"
required = true               # default false
number_format = "id"          # decimal only: overrides source.number_format for this column
# date_format = "MM/DD/YYYY"  # date only: overrides source.date_format for this column

[duplicates]
rows = "warn"                 # whole-row duplicates: "warn" or "ignore"   default "warn"
keys = [["transaction_id"], ["customer_id", "date"]]   # uniqueness keys   default []

[transform]                   # nothing is transformed unless listed here or on the CLI
trim = ["customer_id", "amount"]
normalize = ["amount", "date"]  # decimal/date columns only
deduplicate = "off"           # "off", "rows" or "keys"             default "off"
```

Rejected with a clear message: unsupported `schema_version`, unknown keys (with a "did you
mean" hint), invalid delimiters/encodings/number formats/date directives/line endings,
`number_format` on a non-decimal column, `date_format` on a non-date column, normalizing a
column that is not declared `decimal` or `date`, empty or repeated key definitions, and
`deduplicate = "keys"` without keys. Columns referenced by the profile or options but absent
from the CSV header are reported as `missing_column` errors when the file is read.

## Creating profiles

`csv-tidy profile init INPUT --output PROFILE` reads the header of `INPUT` and writes a
starting profile. It reuses the profile validation and the TOML serializer described here, so
a generated profile is always a valid profile.

- **Nothing is inferred.** Every column is `type = "text"`, `required = false`, unless you
  select otherwise. Values and column names are never used to guess a type or format.
- **Reading settings are explicit.** `--delimiter` (default `,`) and `--encoding` (default
  `utf-8`) are used to read the header and are written into `[source]`. The source number
  and date formats (`--number-format`, `--date-format`, or the defaults) are written too.
- **Options (non-interactive).** `--decimal COLUMN`, `--date COLUMN`, `--required COLUMN`,
  `--trim COLUMN`, `--normalize COLUMN` (each repeatable), `--key COLUMN [COLUMN ...]`
  (repeatable; several columns after one `--key` form a combined key), `--deduplicate`,
  `--output-number-format`, `--output-date-format`. Per-column formats are added by editing
  the file.
- **Never waits for input by default.** Without `--interactive` the command does not prompt
  and does not read standard input.
- **Guided mode.** `--interactive` asks for the delimiter and encoding (unless given as
  options), then which columns are decimal, date, required, unique keys, trimmed, and
  normalized, the formats, and the duplicate handling. Answers are column numbers (`1,3`,
  `2-4`), exact names, `all`, or Enter for none. One example value per column is shown as a
  reading aid only. Questions go to stderr. An invalid answer is asked again. The profile is
  shown and written only after confirmation.
- **Cancellation.** Answering `q`, declining the confirmation, the end of input, or Ctrl+C
  cancels with exit code 130; nothing is written.
- **Refused with exit code 2, nothing written:** an existing `PROFILE` without `--overwrite`;
  `PROFILE` being the input file; a file without a header row or whose start cannot be
  decoded; an empty or duplicate header name; a header that is a single column containing the
  other delimiter (pass the right `--delimiter`); a column name that is not in the header; a
  column selected as both decimal and date; and every inconsistency a profile would be
  rejected for (for example normalizing a text column).
- Header names with spaces, dots, quotes, brackets, or non-ASCII letters are written as quoted
  TOML keys and read back unchanged.

The local interface can also save its current rules as a profile; both kinds are ordinary
profiles.

## Defaults and precedence

For every setting: **explicit CLI option > profile value > application default**.

- Options you do not pass never overwrite profile values.
- `[output]` values that are not set explicitly follow the *resolved* source value, so
  `--delimiter ","` also changes the output delimiter unless `--output-delimiter` or
  `[output] delimiter` is set.
- `--trim` and `--normalize` **replace** the profile's list (repeat the option for several
  columns). `--no-trim` / `--no-normalize` clear the list for one run. Lists are never merged.
- Undeclared columns are text. Text columns are never modified unless selected for trimming.
- Declaring a type validates values but does not normalize them.
- Optional empty values stay empty; `0` is a value; missing values are never invented.

## Number grammars

| id | Grouping | Decimal | Example | Note |
|----|----------|---------|---------|------|
| `id` | `.` | `,` | `1.250,50` | `1.250` means one thousand two hundred fifty |
| `us` | `,` | `.` | `1,250.50` | `1.250` means one point two five |
| `canonical` | none | `.` | `1250.50` | `1.250` means one point two five |

These are data grammars, not interface languages or a claim of full locale coverage.

- Digits are ASCII `0-9`. An optional leading `+` or `-` is accepted; parentheses, trailing
  signs, and spaces are not.
- Grouping is optional, but when used every group after the first has exactly three digits
  and the first group is 1-3 digits not starting with `0`.
- Leading/trailing whitespace makes a value invalid (select `trim` to repair it).
- `NaN`, `Infinity`, scientific notation (`1e5`), and currency symbols are rejected.
- Values are parsed from text into exact digits; floats are never used. Normalization keeps
  every fraction digit (`980,00` → `980.00`), never rounds, drops a leading `+`, removes
  leading zeros of the integer part (`007,5` → `7.5`), and keeps a written `-` (also for zero).
  `id`/`us` output always groups thousands.

## Date formats

A date format combines exactly one year, month, and day token with single separators `-`, `/`
or `.` between them: `YYYY` (4 digits), `MM`/`DD` (exactly 2 digits), `M`/`D` (1-2 digits).
Examples: `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, `D.M.YYYY`. Tokens are uppercase.

A format may also have no separators at all, as in `YYYYMMDD` (`20261231`) or `DDMMYYYY`. It
must then use only the fixed-width tokens `YYYY`, `MM`, and `DD`, because with `M` or `D` a
value such as `2026111` could be 1 November or 11 January. Separators are used between every
two tokens or not at all; `YYYY-MMDD` is rejected.
Calendar validity is checked (`31/02/2026` and `29/02/2025` are invalid; `29/02/2024` is valid).
`01/02/2026` is 1 February with `DD/MM/YYYY` and 2 January with `MM/DD/YYYY`; CSV Tidy never
guesses which one you meant. Month names, times, and time zones are not supported.

## Reading rules

- The first non-blank row is the header; a header is required.
- Fields are always text. Quoted fields may contain delimiters, doubled quotes (`""`), and
  line breaks; such records span several physical lines and are reported with a line range.
- Comma and semicolon delimiters, LF and CRLF line endings, UTF-8 with or without BOM.
  Line numbers count LF, CRLF, and lone CR line breaks, as Python's `csv` module does.
  With `encoding = "utf-8"` a UTF-8 BOM is accepted and removed from the header.
- Decoding is strict: undecodable bytes stop the scan with a fatal `decode_error`; nothing is
  replaced or skipped. The reported line is the physical line that contains the bytes, and
  the scan counts cover every complete line in front of it. Encodings must be text encodings (for example `utf-8`, `utf-16`,
  `cp1252`, `latin-1`); binary or text-to-text codecs such as `base64_codec`, `hex_codec`, or
  `rot_13`, and the placeholder `undefined` codec, are rejected as configuration errors.
- Parsing follows Python's `csv` module in strict mode. It stops on malformed quoting such as
  an unterminated quoted field or text after a closing quote (`"bad"x`). A quote character
  inside an *unquoted* field (`a"b`) is accepted and kept literally; CSV Tidy does not enforce
  every RFC 4180 rule beyond what Python's parser checks.
- `record` numbers count data records (header excluded); `line` numbers are physical lines.
- Header names are matched exactly (case and whitespace).

| Situation | Result |
|-----------|--------|
| Empty file (or only blank lines) | `empty_file` error |
| Header only | `no_records` warning |
| Blank line | `blank_line` warning; not a record and not exported |
| Empty / whitespace-only header | `empty_header` error |
| Duplicate header | `duplicate_header` error (values are never overwritten) |
| Header with surrounding spaces | `header_whitespace` warning |
| Single-column header containing the other delimiter | `possible_wrong_delimiter` warning |
| Too few / too many fields | `inconsistent_columns` error; the record is not checked further, never transformed or removed |
| Malformed quoting (unterminated quoted field, text after a closing quote) | fatal `malformed_csv`; scan incomplete |
| Field longer than `max_field_chars` | fatal `field_too_large`; scan incomplete |
| Undecodable bytes | fatal `decode_error`; scan incomplete |

## Validation

| Code | Severity | Rule |
|------|----------|------|
| `missing_required` | error | required column empty or whitespace-only |
| `invalid_number` | error | non-empty decimal value not valid in its grammar |
| `invalid_date` | error | non-empty date value not matching its format or not a calendar date |
| `duplicate_record` | warning | whole row identical to an earlier row (`rows = "warn"`) |
| `duplicate_key` | error | key values equal to an earlier record's; the earlier record is reported |
| `missing_column` | error | referenced column not in the header |
| `field_too_large` | error (output only) | a cleaned value is longer than `max_field_chars` (see below) |

Duplicate comparison uses exact text (case-sensitive). A key with any empty part never forms
an identity, so records with empty identifiers are not grouped together.

## Transformations (`clean` only)

Applied in this fixed order, only to selected columns of records with the correct field count:

1. **trim** — remove leading/trailing whitespace; internal whitespace is kept.
2. **normalize** — rewrite valid `decimal`/`date` values from the source format to the output
   format. A value that cannot be parsed in its source format is left unchanged and stays an
   error, **even if it happens to look valid in the output format** (for example `1.25` with
   source `id` and output `canonical`, or `12/31/2026` with source `DD/MM/YYYY` and output
   `MM/DD/YYYY`). Only a successful conversion repairs a value.
3. **deduplicate** — `rows` removes later exact duplicate rows; `keys` also removes later
   records whose configured key matches a kept record. The first record is always kept.
   Comparison uses the transformed values.
4. **output validation** — the result is validated with output rules: normalized columns use
   the output format; other columns keep their source format. Every cleaned value must also
   fit `max_field_chars`; normalization can make values longer (`1000000` → `1,000,000`), and
   a longer value is reported as `field_too_large` and blocks the export, so an exported file
   can always be read back with its generated output profile. Raise `max_field_chars` if needed.

Source issues are marked `resolved` (a selected transformation actually repaired the value),
`unresolved`, or `removed` (record removed by deduplication). Output issues created by transformations are marked `introduced` (for example,
duplicate keys that appear after trimming).

## Commands and exit codes

| Code | `check` | `clean` (dry run or `--apply`) |
|------|---------|-------------------------------|
| 0 | no source errors (warnings allowed) | no remaining output errors |
| 1 | source data errors | output errors remain; nothing is exported |
| 2 | usage, profile/option, read, decoding/parsing, or write failure (including a failed `--report` write) | same |

- `check` validates source rules and never modifies files. Profile transformations are ignored.
- `clean` is a dry run unless `--apply` is given. `--apply` requires `--output`; `--output` and
  `--output-schema` require `--apply`; `--dry-run` and `--apply` cannot be combined. A dry run
  may save a report with `--report` but never writes a CSV or output profile.
- A fatal parsing error makes the scan incomplete: reports say so, counts cover only what was
  read, and the exit code is 2. A partially scanned file is never reported as valid.
- `profile init` exits with 0 when the profile was written, 2 for the refusals listed under
  "Creating profiles", and 130 when cancelled.
- `ui` exits with 0 after it was stopped, and 2 if the server cannot start.

### Validation coverage

`check` validates only what the settings declare:

| Declared | Checked |
|----------|---------|
| nothing (no profile, or a profile without column rules) | file structure only: header names, field counts, blank lines, and identical rows (warning) |
| `type = "decimal"` / `"date"` | the values of that column, in its number grammar or date format |
| `required = true` | the column is not empty |
| `[duplicates] keys` | uniqueness of the key columns |

`--number-format` and `--date-format` set the *format of declared columns*; on their own they
check nothing. A file can therefore pass with exit code 0 while containing `31/02/2026` in a
column that no profile declares as a date. Reports make this explicit: the text report has
`Checked:` and `Not checked:` lines and the verdict `PASSED (structure only)`, and JSON has a
`coverage` object. CSV Tidy does not detect types; create a profile with `profile init`.

## Shortcuts

`csv-tidy shortcut install [--folder DIR] [--no-desktop]` and
`csv-tidy shortcut remove [--folder DIR]`.

| System | Install creates | Started program |
|--------|-----------------|-----------------|
| Windows | `CSV Tidy.lnk` on the Desktop and in the Start Menu (Programs); `Update CSV Tidy.lnk` in the Start Menu | `csv-tidy-ui` next to the Python that runs the command; for Update: that Python with `-m csv_tidy update --pause` (a console window that waits for Enter) |
| Linux | `csv-tidy.desktop` and `csv-tidy-update.desktop` in `$XDG_DATA_HOME/applications` (default `~/.local/share/applications`); `csv-tidy.desktop` on the Desktop when `$XDG_DESKTOP_DIR` (default `~/Desktop`) exists | the same |
| macOS | not supported; start `csv-tidy-ui` | — |

- `--folder DIR` puts the shortcuts in `DIR` (one "CSV Tidy" and one "Update CSV Tidy").
  `--no-desktop` skips the Desktop.
- A file with one of these names is replaced or removed only when it was made by CSV Tidy
  (Windows: it starts `csv-tidy-ui` or runs `-m csv_tidy`; Linux: it contains
  `X-CSV-Tidy=1`). Otherwise it is reported as `skipped` and left as it is.
- Each shortcut is reported as `created`, `updated`, `removed`, `absent`, or `skipped`; the
  exit code is 0, or 2 if the shortcuts cannot be made (for example no `csv-tidy-ui`
  program next to this Python, or Windows PowerShell is unavailable).
- On Windows the `.lnk` files are written through the Windows Script Host by Windows
  PowerShell; nothing else on the system is changed.

## Updates

`csv-tidy update [--check] [--version X.Y.Z] [--pause]` is the only command that connects to
the internet, and only when it is run.

1. It asks the GitHub API for the latest release of `JudikaM/csv-tidy` (or the release
   `vX.Y.Z`).
2. It takes the wheel `csv_tidy-X.Y.Z-py3-none-any.whl` attached to that release. A release
   without that wheel, without a published `sha256:` digest for it, or whose download address
   is not under `https://github.com/JudikaM/csv-tidy/releases/download/` is refused.
3. If the release is newer than the installed version (or `--version` was given), it runs
   `python -m pip install --upgrade <wheel URL>#sha256=<digest>` with the Python that runs
   CSV Tidy. pip refuses a file whose SHA-256 differs. pip also installs missing
   dependencies (`tomli-w`) from PyPI.

`--check` only reports. `--pause` waits for Enter at the end (used by the shortcut). Exit
codes: 0 updated, up to date, or `--check`; 2 if GitHub cannot be reached, the release is
unusable, or pip fails (the installed version is kept). Close CSV Tidy before updating.

## Batch processing

`csv-tidy batch check INPUT...` and `csv-tidy batch clean INPUT...` apply one profile and one
set of options to several files through the same functions as the single-file commands.

- **Selection.** An `INPUT` that is a file is taken as given, whatever its name. An `INPUT`
  that is a folder selects the files directly inside it whose names match `--pattern`
  (default `*.csv`, case-insensitive), sorted by name without regard to case; `--recursive`
  also selects matching files in subfolders. Inputs are processed in the order given.
  Selecting no file (a folder without matches) or the same file twice is an error (exit 2).
- **Same pipeline, explicitly.** `--schema` and all source, output, and transformation options
  of `check`/`clean` are accepted and apply to every file. Without column rules only the
  structure is checked, and the summary says so.
- **Preview by default.** `batch clean` writes no cleaned file unless `--apply` is given.
  `--apply` requires `--output-dir DIR`; `--output-dir` and `--output-schemas` require
  `--apply`.
- **Output names.** For an input `NAME.ext`: `DIR/NAME.clean.csv`, with `--output-schemas`
  also `DIR/NAME.output.toml`, and with `--report-dir RDIR` a full single-file report
  `RDIR/NAME.report.json` (`.txt` with `--format text`). A file found in a subfolder of a
  selected folder keeps that subfolder below `DIR`/`RDIR`. `--report PATH` saves the batch
  summary.
- **Checked before anything is read (exit 2, nothing written):** two inputs that would
  produce the same output path, an output path that is an input file or the profile
  (including hard-link aliases), an output path that is a directory, an existing output file
  without `--overwrite`, and invalid settings.
- **Isolation.** Files are processed one after another. A file that cannot be read, stops on
  a fatal error, stays blocked, or whose output cannot be written is reported with its reason
  and exit code; other files are still processed and their outputs stay in place. A blocked
  file's CSV and profile are `not_written`; its report is still written.
- **Summary.** Text and JSON list every file with `status` (`valid`/`invalid` for `check`,
  `ready`/`blocked` for `clean`, `incomplete`, or `failed`), `exit_code`, record and issue
  counts, `structure_only`, `error`, and `artifacts`, followed by `totals` (`files`, `ok`,
  `data_errors`, `failed`, `data_records`, `errors`, `warnings`, `changed_fields`,
  `removed_records`, `written`). `totals.errors` counts source errors for `check` and errors
  remaining in the results for `clean`. JSON has `command: "batch"` and `action`.
- **Exit code.** 2 if any file failed, was not fully scanned, or could not be written;
  otherwise 1 if any file has data errors; otherwise 0.

## Local interface

`csv-tidy ui [--port N] [--no-browser] [--max-file-mb N] [--idle-minutes N]` serves one page
from a server bound to `127.0.0.1` and opens it in the default browser.

- **Without a console.** The `csv-tidy-ui` program (a standard pip `gui-scripts` entry point)
  starts the same interface without a console window, opens the browser, and stops by itself
  10 minutes after the page last contacted it; the page checks in every minute while it is
  open, including in a background tab. `--idle-minutes N` gives the console command the same
  behavior (default 0: run until Quit or Ctrl+C). Only requests that carry the session key
  count as contact. If `csv-tidy-ui` cannot start, the reason is written to
  `csv-tidy-ui-error.txt` in the temporary folder, because there is no window to show it.
- **Plain suggestions.** The page explains problems with its own controls, based on each
  issue's `remedy` (see Reports); for other issues it shows the suggestion text.
- **Look.** A dark theme (default) and a light theme, switched in the header and remembered
  in the browser's local storage for this address. Quit asks for confirmation. Files can be
  dropped onto the file area. The page uses only its own style sheet and scripts
  (`app.css`, `theme.js`, `app.js`); no fonts or styles are loaded from elsewhere.
- **One server per port.** On Windows the port is claimed exclusively, so starting a second
  interface on a port that is in use fails with an explanation instead of sharing the port.
- **Dates from a list.** Date formats are chosen from `YYYY-MM-DD`, `DD/MM/YYYY`,
  `MM/DD/YYYY`, `DD-MM-YYYY`, `DD.MM.YYYY`, `YYYY/MM/DD`, `D/M/YYYY`, and `M/D/YYYY`;
  **Other…** accepts any format valid under "Date formats". Profiles with other formats load
  into **Other…** unchanged.

- The page sends the chosen files to that local process, which stores them in a private
  temporary folder (removed when they are replaced or removed, on **Quit**, and on Ctrl+C).
  The original files are never opened for writing. A file larger than `--max-file-mb`
  (default 200), or several files that are larger together, are refused.
- Preview, check, and cleaning call `check_file`/`clean_file`; the rules set on the page are
  sent as a profile and validated by the profile loader; saving calls `export_clean`. Saved
  files are browser downloads named `NAME.clean.csv`, `NAME.output.toml`,
  `NAME.clean-report.txt|json` (or `NAME.check-report.*`), and `NAME.profile.toml`.
- The cleaned CSV and its profile cannot be downloaded while the scan is incomplete or errors
  remain; the page states the reason. Reports can always be saved. Reports from the page have
  `mode: "dry-run"` because the server itself writes no file to a user location.
- A result belongs to the file and settings it was made with. Choosing another file or
  changing any setting discards it on the page, and the server refuses to serve a download
  for a result whose settings no longer match.
- **Several files with the same rules.** The page sends the rules once and the server calls
  `run_batch` (the function behind `csv-tidy batch clean`/`check`, as a preview) on all chosen
  files, labelled with their own names. Statuses, counts, and the aggregate exit code are the
  same as `csv-tidy batch` reports for the same files and rules: `valid`/`invalid` (check),
  `ready`/`blocked` (clean), `incomplete`, or `failed`, with the reason. **Details** recomputes
  one file with `check_file`/`clean_file`. Two chosen files whose names differ only in the
  extension or in letter case are refused, because their results would share a name.
- **Batch downloads.** Per ready file: `NAME.clean.csv`. All results: `csv-tidy-batch.zip`
  with `NAME.clean.csv` and `NAME.output.toml` for every ready file (written by
  `export_clean`), `NAME.report.json` for every file, `batch-summary.json`, and
  `batch-summary.txt` (the same summary as `csv-tidy batch --format json|text`). Blocked or
  incomplete files are never exported. The ZIP is built in memory.
- **More settings.** `max_field_chars` (1 to 100,000,000, validated by the profile loader,
  applied to the preview, saved in profiles) and three display limits: problems listed (0 to
  10,000, like `--max-details`), changed values listed (0 to 10,000, like `--max-examples`),
  and rows shown in previews (1 to 1,000). Defaults: 200, 200, 50. Totals are always complete,
  and saved reports use the same limits. A result belongs to the limits it was made with.
- Requests are served only if they are addressed to the loopback host name, carry the session
  key from the page address, and (when the browser sends one) a same-origin `Origin` header.
  The page uses a content security policy that allows only its own script and style sheet;
  file contents are inserted as text. No external resources are loaded.

## Output safety

- The input CSV and input profile can never be an output, report, or output profile. Paths
  are compared after resolution and by file identity, so symlink and hardlink aliases are
  rejected.
- Two artifacts may not refer to the same file.
- Existing files are refused unless `--overwrite` is given (which still never allows writing
  an input). Without `--overwrite` the final rename itself refuses an existing destination,
  so a file created by another process while CSV Tidy is writing is never replaced.
- `export_clean` refuses a result that is not export-ready and states the actual reason:
  an incomplete scan (with the fatal code and line), a missing header row, or the number of
  remaining output errors (`CleanResult.export_blocked_reason`).
- Library results remember the absolute paths of the input CSV and profile when they are
  read, so a later `export_clean` call is protected even if the working directory changed.
- Each file is written to a temporary file in the same directory and moved into place. On
  failure the temporary file is removed and an existing file keeps its previous content.
  Writes are atomic per file, not across files: the CSV is written first, then the output
  profile, then the report. If a later write fails, the report and stderr state which files
  were written, and the exit code is 2. A partially written file is never left at the final
  path. Outside Windows, writing without `--overwrite` relies on hard links; on a file system
  without hard-link support it fails with an error (exit code 2) instead of risking a partial
  or overwritten file. Write elsewhere, or use `--overwrite` if replacing is acceptable.
- Missing parent directories of output paths are created.
- Output quoting is minimal (`"` doubled); fields containing the delimiter, quotes, or line
  breaks are quoted. Serialization may differ from the source bytes; field values do not.

## Output profiles

`--output-schema PATH` saves the effective output profile: the resolved output delimiter,
encoding, number and date formats (as its source settings), per-column formats as they appear
in the cleaned file, the same validation policies, and the same transformation selections.
On cleaned output those transformations are no-ops, so `check` passes and a second `clean`
makes no changes. The profile reflects CLI overrides, not just the original TOML.

## Reports

Text reports are ordered for reading top-down:

1. `Verdict:` on the second line: `PASSED`, `PASSED (structure only)`, `FAILED`, or
   `INCOMPLETE` for `check`; `READY TO EXPORT`, `BLOCKED`, or `INCOMPLETE` for `clean`.
2. Source, scan counts, and the `Checked:` / `Not checked:` coverage lines.
3. `check`: issues with errors in front of warnings. `clean`: transformations and changes,
   then `Still to fix` (what remains in the cleaned result, errors first), then separately
   `Repaired by the selected transformations` (`FIXED`) and `Gone with records removed as
   duplicates` (`REMOVED`), then the `Source issues before cleaning` totals.
4. `Export:` state and artifacts (`clean`), `Next steps:`, and the `Status:` line.

JSON keeps every earlier field and adds `verdict` (`state`, `headline`), `coverage` (`scope`:
`structure_only` or `structure_and_values`, `declared_columns`, `undeclared_columns`,
`unchecked_columns`, `unique_keys`, `duplicate_rows`, `header_columns`), and `next_steps` (a
list of sentences). Every issue in JSON also has `remedy`: the kind of repair its
suggestion describes (`trim`, `number_format`, `date_format`, `deduplicate_rows`,
`deduplicate_keys`, `delimiter`, `encoding`, `quoting`, `max_field_chars`), or `null` when
only the source can be corrected. Text reports do not show it. Source issues keep their
`severity` and `status` (`resolved`,
`unresolved`, `removed`) in JSON; only the text layout separates them. `verdict.state` for
`check` is `passed`, `passed_structure_only`, `failed`, or `incomplete`; `summary.status`
is unchanged (`valid`, `invalid`, `incomplete`).

`--format text|json` selects the report format for stdout and `--report PATH`. JSON contains
`schema_version` (currently 1), `tool`, `command`, `source`, `scan` (`complete`,
`data_records`, `physical_lines`, `blank_lines`, `fatal_error`), `summary`, issue lists, and
`details` (`limit`, totals, `shown`, `truncated`). `clean` adds `mode`, `output`,
`transformations`, `changes` (counts and limited before/after examples), `source_issues`,
`output_issues`, and `export.artifacts`; `check` lists `artifacts`. Artifact lists include the
report itself (`written` or `failed`). `summary.exit_code` is the command's exit code: it is 2
if saving the report (or another artifact) failed, even when the data are valid
(`summary.status` still describes the data). The report file is written before stdout, so
stdout always shows the final outcome. `--max-details` limits listed issues and
`--max-examples` limits examples; totals are always complete. Issue values longer than 200
characters are truncated in JSON (`value_truncated: true`). Reports contain no timestamps, so
the same input and settings produce the same report. Status messages go to stderr.

## Versioning

`schema_version` (profiles) and the report `schema_version` change only for incompatible
changes; compatible additions keep the version. The Python API follows the package version.
See [RELEASE.md](RELEASE.md).
