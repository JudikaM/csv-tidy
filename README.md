# CSV Tidy

A Python CLI, library, and local browser interface for validating and cleaning CSV files with
explicit number and date formats.

CSV Tidy helps you find, understand, and explicitly repair CSV data problems before importing
the data elsewhere: inconsistent field counts, missing required values, duplicate records and
keys, numbers in Indonesian (`1.250,50`), US (`1,250.50`), or canonical (`1250.50`) notation,
and numeric dates such as `DD/MM/YYYY`. It never guesses: it repairs only what you select,
reports everything else with record and line locations, and refuses to export a result that
still has errors.

**Status:** early alpha (0.x); interfaces may still change between minor versions, and
changes are listed in [CHANGELOG.md](CHANGELOG.md). It works locally and offline, with no
telemetry, internet access, or AI services. It has not yet been validated with external
users. Feedback is welcome (see [Feedback](#feedback-and-bug-reports)).

There are three ways to use the same engine:

| You are | Use | Start with |
|---------|-----|------------|
| A developer automating imports | the `csv-tidy` command or the Python API | [Quick start](#quick-start) |
| Someone who works in Excel and prefers forms | the local interface, `csv-tidy ui` | [Local interface](#local-interface-for-people-who-prefer-forms) |
| Processing a folder of exports | `csv-tidy batch` | [Many files](#many-files-at-once) |

## Features

- Strict CSV reading: comma or semicolon, UTF-8 with or without BOM (or an explicit
  encoding), quoted fields with delimiters, quotes and line breaks, LF/CRLF. Undecodable
  bytes and malformed quoting stop the scan instead of being skipped.
- Structure checks: empty file, header-only file, blank lines, empty/duplicate headers, and
  records with too few or too many fields.
- Reusable TOML profiles: required columns, `text`/`decimal`/`date` types, number grammars,
  date formats, duplicate-row policy, and uniqueness keys. `csv-tidy profile init` writes a
  starting profile from a file's header, with optional guided questions.
- Identifiers such as `00123` and `081234567890` stay text; nothing is converted to numbers.
- Explicit transformations: trim selected columns, normalize selected numbers/dates,
  remove duplicates keeping the first record. Exact decimal arithmetic; no floats, no rounding.
- Dry-run preview with before/after examples and complete counts.
- Safe export: never overwrites the input (including symlink/hardlink aliases), refuses
  existing files unless `--overwrite`, and writes each file atomically.
- Generated output profile that validates the cleaned file and makes a second clean a no-op.
- Reports that start with the verdict, say what was and was not checked, list unresolved
  problems before repaired ones, and end with the next step. English text and JSON with
  stable issue codes and documented exit codes.
- Batch processing of files and folders with one profile and separate results per file.
- A local browser interface that runs the same pipeline without a command line.

## Installation

Requires Python 3.11 or newer. CSV Tidy is **not published on PyPI**. Published versions and
installation files (a wheel and a source distribution) are listed on the
[GitHub Releases page](https://github.com/JudikaM/csv-tidy/releases); a downloaded wheel
installs with `python -m pip install <path-to-wheel>` inside a virtual environment. This
README describes version 0.2.0; changes made after a release are listed under "Unreleased"
in the [changelog](CHANGELOG.md). You can also install from a source checkout:

Windows PowerShell (calling the virtual environment's programs directly, so the
ExecutionPolicy does not need to change):

```powershell
git clone https://github.com/JudikaM/csv-tidy.git
cd csv-tidy
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\csv-tidy.exe --version
```

Linux/macOS:

```bash
git clone https://github.com/JudikaM/csv-tidy.git
cd csv-tidy
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/csv-tidy --version
```

**How the examples are written.** Every command below is written for Windows PowerShell and
this installation, so it can be pasted as is from the `csv-tidy` folder:
`.\.venv\Scripts\csv-tidy.exe ...`. On Linux/macOS replace that program with
`.venv/bin/csv-tidy` (and `\` in paths with `/`). If the virtual environment is activated, or
CSV Tidy is installed where your shell finds it, plain `csv-tidy ...` works; the hints
printed by the tool use that short form. `python -m csv_tidy` is equivalent. For development
setup, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Quick start

Four steps with the synthetic examples in this repository: **check → preview → apply →
re-check**.

```powershell
# 1. Check: what is wrong? (exit code 1: two errors)
.\.venv\Scripts\csv-tidy.exe check examples\transactions_fixable.csv --schema examples\profiles\transactions-id.toml

# 2. Preview: what would the selected repairs change? (writes nothing)
.\.venv\Scripts\csv-tidy.exe clean examples\transactions_fixable.csv --schema examples\profiles\transactions-id.toml

# 3. Apply: write the cleaned copy and a profile that describes it
.\.venv\Scripts\csv-tidy.exe clean examples\transactions_fixable.csv --schema examples\profiles\transactions-id.toml --apply --output output\transactions_clean.csv --output-schema output\transactions.output.toml

# 4. Re-check the result with its generated profile (exit code 0)
.\.venv\Scripts\csv-tidy.exe check output\transactions_clean.csv --schema output\transactions.output.toml
```

The profile describes the source data and which repairs you allow
([examples/profiles/transactions-id.toml](examples/profiles/transactions-id.toml)):

```toml
schema_version = 1

[source]
delimiter = ";"
number_format = "id"          # 1.250,50
date_format = "DD/MM/YYYY"

[output]
number_format = "canonical"   # 1250.50
date_format = "YYYY-MM-DD"

[columns.transaction_id]
type = "text"
required = true

[columns.customer_id]
type = "text"
required = true

[columns.amount]
type = "decimal"
required = true

[columns.date]
type = "date"
required = true

[duplicates]
keys = [["transaction_id"]]

[transform]
trim = ["customer_id", "amount", "date"]
normalize = ["amount", "date"]
```

### 1. Check

```text
CSV Tidy 0.2.0 - check
Verdict: FAILED - 2 errors found in the source file.
Source: examples\transactions_fixable.csv
Profile: examples\profiles\transactions-id.toml
  delimiter ';', encoding utf-8 (BOM absent), numbers id, dates DD/MM/YYYY
Scan: complete; 4 data records, 5 physical lines, 0 blank lines
Checked: file structure; values in 4 of 5 columns: transaction_id (text, required), customer_id (text, required), amount (decimal, id, required), date (date, DD/MM/YYYY, required); unique key (transaction_id); duplicate rows (warning)
Not checked: values in 1 column without rules (note)
Result: 2 errors, 0 warnings

Issues (showing 2 of 2, errors first):
  ERROR invalid_number (record 2, line 3, column 'amount')
    ' 980,00 ' is not a valid number: the value has leading or trailing whitespace.
    Suggestion: Select trimming for 'amount' (transform trim) or fix the source value.
  ERROR invalid_date (record 3, line 4, column 'date')
    '28/02/2026 ' is not a valid date: the value has leading or trailing whitespace.
    Suggestion: Select trimming for 'date' (transform trim) or fix the source value.

Next steps:
  - Fix the listed values in the source file, or preview explicit repairs (a dry run that writes nothing): csv-tidy clean examples\transactions_fixable.csv --schema examples\profiles\transactions-id.toml

Status: source validation failed (exit code 1)
```

The `Checked` and `Not checked` lines state the coverage of the run. **Without column rules
only the file structure is checked**: numbers, dates, required values, and unique keys are
checked only for columns declared in a profile, and nothing is inferred from the data. A run
without rules says so even when it passes:

```powershell
.\.venv\Scripts\csv-tidy.exe check examples\transactions_unfixable.csv --delimiter ";"
```

```text
Verdict: PASSED (structure only) - the file structure is consistent, but values were not checked because no column rules are declared.
...
Checked: file structure; duplicate rows (warning)
Not checked: values in all 5 columns without rules (transaction_id, customer_id, amount, date, note)
...
Status: structure check passed; values were not checked (exit code 0)
```

That file contains the date `31/02/2026` and the amount `abc`; they are reported as soon as a
profile declares `date` and `amount` (see [Create a profile](#create-a-profile)).

JSON for pipelines (stdout contains only JSON; status messages go to stderr):

```powershell
.\.venv\Scripts\csv-tidy.exe check examples\transactions_unfixable.csv --schema examples\profiles\transactions-id.toml --format json --report output\report.json
```

### 2. Preview a clean (dry run is the default)

```text
CSV Tidy 0.2.0 - clean (dry run, nothing written)
Verdict: READY TO EXPORT - no errors remain in the cleaned result; 2 source problems repaired.
...
Transformations (applied in this order):
  1. trim: customer_id, amount, date
  2. normalize: amount (id -> canonical), date (DD/MM/YYYY -> YYYY-MM-DD)
  3. deduplicate: off

Changes: 9 fields changed in 4 records; 0 records removed; 4 records in the result
  record 1 (line 2), 'amount': '1.250,50' -> '1250.50' [normalize]
  record 2 (line 3), 'amount': ' 980,00 ' -> '980.00' [trim, normalize]
  record 3 (line 4), 'customer_id': ' 00789' -> '00789' [trim]
  ...

Still to fix: nothing; the cleaned result has no errors or warnings.

Repaired by the selected transformations: 2 (no action needed)
  FIXED invalid_number (record 2, line 3, column 'amount')
    Was: ' 980,00 ' is not a valid number: the value has leading or trailing whitespace.
  FIXED invalid_date (record 3, line 4, column 'date')
    Was: '28/02/2026 ' is not a valid date: the value has leading or trailing whitespace.

Source issues before cleaning: 2 errors, 0 warnings (2 resolved, 0 unresolved, 0 removed with records)

Export: ready (run with --apply --output PATH to write it)
```

Problems that remain are listed first under `Still to fix`; problems that the selected
transformations repaired are listed separately as `FIXED` (or `REMOVED` when the record was
removed as a duplicate), so the report never shows a solved problem as an open error.

### 3. Apply, and save the output profile

Result of step 3 (`customer_id` keeps its leading zeros; the untouched `note` column keeps
its double space):

```text
transaction_id;customer_id;amount;date;note
TX-001;00123;1250.50;2026-02-01;First payment
TX-002;00456;980.00;2026-02-15;Paid in  two parts
TX-003;00789;12000;2026-02-28;"Note with ; semicolon"
TX-004;00123;-75.25;2024-02-29;Refund
```

### 4. Re-check

The generated output profile describes the cleaned file, so step 4 reports
`Verdict: PASSED - no errors found by the declared rules.`, and a second clean with it makes
no changes:

```powershell
.\.venv\Scripts\csv-tidy.exe clean output\transactions_clean.csv --schema output\transactions.output.toml
```

### Problems that cannot be repaired block the export

```powershell
.\.venv\Scripts\csv-tidy.exe clean examples\transactions_unfixable.csv --schema examples\profiles\transactions-id.toml --apply --output output\invalid_result.csv
```

```text
Verdict: BLOCKED - 3 errors remain in the cleaned result; nothing can be exported.
...
Still to fix: 3 errors, 0 warnings in the cleaned result (0 introduced by transformations)
  ERROR invalid_date (record 1, line 2, column 'date')
    '31/02/2026' is not a valid date: it could not be normalized because it matches DD/MM/YYYY but is not a valid calendar date.
    Suggestion: Correct the date in the source; invalid calendar dates are never guessed.
  ERROR missing_required (record 2, line 3, column 'customer_id')
  ERROR invalid_number (record 3, line 4, column 'amount')
...
Export: blocked by 3 remaining output errors; no CSV is written.
  output CSV: output\invalid_result.csv - not_written (output errors remain)
```

Other examples: US-format customers ([customers-us.toml](examples/profiles/customers-us.toml)
with `customers_valid.csv`, `customers_fixable.csv`), canonical data
([transactions-canonical.toml](examples/profiles/transactions-canonical.toml)), and
`customers_trim_duplicates.csv`, where trimming creates a duplicate key. That file is blocked
until you add `--deduplicate keys`.

## Create a profile

`profile init` reads the header of a file and writes a starting profile in which **every
column is text**. It never guesses types from values or column names; you choose them.

```powershell
# A template to edit by hand (never prompts; safe in scripts and CI)
.\.venv\Scripts\csv-tidy.exe profile init examples\transactions_fixable.csv --delimiter ";" --output output\my-profile.toml

# Guided questions: which columns are numbers or dates, required, unique, and what to repair
.\.venv\Scripts\csv-tidy.exe profile init examples\transactions_fixable.csv --output output\my-profile.toml --interactive

# Everything as options, for automation
.\.venv\Scripts\csv-tidy.exe profile init examples\transactions_fixable.csv --delimiter ";" --output output\my-profile.toml --decimal amount --date date --number-format id --date-format DD/MM/YYYY --required transaction_id --key transaction_id --trim amount --trim date --normalize amount --normalize date --output-number-format canonical --output-date-format YYYY-MM-DD
```

The delimiter and encoding you give are written into the profile. An existing profile file is
refused unless `--overwrite` is given, the input can never be the output, unknown column
names and inconsistent choices are rejected before anything is written, and the guided mode
can be cancelled with `q` or Ctrl+C (exit code 130, nothing written). Profiles made this way
work with `check`, `clean`, `batch`, and the local interface. Details:
[docs/CONFIGURATION.md](docs/CONFIGURATION.md#creating-profiles).

## Local interface (for people who prefer forms)

```powershell
.\.venv\Scripts\csv-tidy.exe ui
```

This starts a small web server **on this computer only** and opens a page in your browser:

1. Choose the CSV file, the separator (comma or semicolon), and the encoding.
2. Look at the first rows exactly as they are stored.
3. Describe the columns with drop-downs and checkboxes, or load a profile.
4. Check the file: problems are listed with record, file line, column, and what to do.
5. Preview the cleaned copy: every changed value is shown before and after.
6. Save the cleaned CSV, the profile of the cleaned file, the report, and your rules as a
   profile (through the browser's download folder).

The page always shows the current status and the next step, clears results that no longer
match when the file or a setting changes, and explains why saving is blocked while problems
remain. It uses the same functions as the commands; a profile saved from the page works with
`csv-tidy check`, and a profile written for the commands can be loaded into the page.

Privacy and safety: the server listens on `127.0.0.1` only, the page loads nothing from the
internet, and the address contains a one-time key without which other programs and web pages
cannot use it. The chosen file is copied into a private temporary folder that is removed when
you select **Quit** (or press Ctrl+C in the window that started it); your original file is
never written to. Options: `--port N`, `--no-browser`, `--max-file-mb N` (default 200). A
step-by-step guide for first-time users is in
[docs/USER_TESTING.md](docs/USER_TESTING.md#guide-for-administrative-staff).

## Many files at once

```powershell
# Preview every transactions_*.csv file directly inside examples\ with one profile
.\.venv\Scripts\csv-tidy.exe batch clean examples --pattern "transactions_*.csv" --schema examples\profiles\transactions-id.toml

# Write the files that are ready, their output profiles, and one report per file
.\.venv\Scripts\csv-tidy.exe batch clean examples --pattern "transactions_*.csv" --schema examples\profiles\transactions-id.toml --apply --output-dir output\cleaned --output-schemas --report-dir output\reports --format json
```

```text
CSV Tidy 0.2.0 - batch clean (dry run, nothing written)
Verdict: 2 of 4 files need attention (2 with data errors).
Profile: examples\profiles\transactions-id.toml

Files:
  BLOCKED    examples\transactions_canonical.csv: 3 records; 4 errors remaining; 0 fields changed; 0 records removed
  READY      examples\transactions_fixable.csv: 4 records; 0 errors remaining; 9 fields changed; 0 records removed
  BLOCKED    examples\transactions_unfixable.csv: 4 records; 3 errors remaining; 6 fields changed; 0 records removed
  READY      examples\transactions_valid.csv: 4 records; 0 errors remaining; 8 fields changed; 0 records removed

Totals: 4 files: 2 ready, 2 with data errors, 0 failed; 15 records, 7 errors, 1 warning; 23 fields changed, 0 records removed, 0 CSV files written

Status: exit code 1
```

- **Selection:** a file is taken as given; a folder selects the files directly inside it that
  match `--pattern` (default `*.csv`, case-insensitive), sorted by name; `--recursive` adds
  subfolders.
- **Outputs:** `NAME.csv` becomes `NAME.clean.csv` (plus `NAME.output.toml` and
  `NAME.report.json`) in the folders you name. If two inputs would produce the same path, or
  a path is an input or an existing file, the batch stops before reading anything.
- **Isolation:** every file gets its own result. A file that fails, or stays blocked, is not
  written and never removes the results of the others.
- **Exit code:** 2 if any file failed or could not be fully read or written; otherwise 1 if
  any file has data errors; otherwise 0. `batch check` works the same way without writing.

## Options

Command-line options override the profile; omitted options never do. `--trim`/`--normalize`
replace the profile list (repeat for several columns); `--no-trim`/`--no-normalize` clear it.

| Option | Commands | Meaning |
|--------|----------|---------|
| `--schema PROFILE` | check, clean, batch | TOML profile |
| `--delimiter`, `--encoding`, `--number-format`, `--date-format` | check, clean, batch, profile init | source settings |
| `--output-delimiter`, `--output-encoding`, `--output-number-format`, `--output-date-format`, `--line-ending` | clean, batch clean | output settings (default: follow the source) |
| `--trim COL`, `--normalize COL`, `--deduplicate off\|rows\|keys` | clean, batch clean, profile init | explicit transformations |
| `--dry-run` / `--apply`, `--output PATH`, `--output-schema PATH` | clean | preview (default) or write |
| `--apply`, `--output-dir DIR`, `--output-schemas`, `--report-dir DIR`, `--pattern GLOB`, `--recursive` | batch | many files |
| `--format text\|json`, `--report PATH`, `--max-details N`, `--max-examples N` | check, clean, batch | reports |
| `--overwrite` | all writing commands | allow replacing existing output files (never inputs) |

Exit codes: `0` no blocking errors (warnings allowed), `1` data errors (`check`: in the source;
`clean`: remaining in the cleaned result), `2` usage, configuration, decoding/parsing, read or
write failure, `130` cancelled by the user. Every command has `--help`. The full reference is
in [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Library

```python
from csv_tidy import check_file, clean_file, export_clean, load_profile

profile = load_profile("examples/profiles/transactions-id.toml")
check = check_file("examples/transactions_fixable.csv", profile)
print(check.exit_code, [(i.code, i.record, i.column) for i in check.issues])
# 1 [('invalid_number', 2, 'amount'), ('invalid_date', 3, 'date')]

result = clean_file("examples/transactions_fixable.csv", profile)
if result.export_ready:
    export_clean(result, "output/clean.csv", output_schema="output/clean.output.toml")
else:
    print(result.export_blocked_reason)
```

Many files: `run_batch("clean", select_inputs(["exports/"]), profile)`. A runnable example is
in [examples/api_example.py](examples/api_example.py). See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for result types and exceptions.

## Supported conventions and limits

- Number grammars: `id` (`1.250,50`), `us` (`1,250.50`), `canonical` (`1250.50`). Optional
  leading `+`/`-`. No currency symbols, scientific notation, NaN/Infinity, or other locales.
- Dates: numeric formats built from `YYYY`, `MM`/`M`, `DD`/`D` and `-`, `/`, `.` separators.
  No month names, times, or compact `YYYYMMDD`.
- The header row is required. Delimiters are `,` or `;` and are never auto-detected.
- Files are processed in memory, one file at a time. Duplicate detection memory grows with
  distinct rows/keys. The default field limit is 131,072 characters (`max_field_chars`).
  Measured times and memory for up to 500,000 rows are in
  [docs/BENCHMARKS.md](docs/BENCHMARKS.md); larger files have not been measured.
- CSV has no column types. Spreadsheet programs may turn `00123` into `123` when opening a
  CSV directly. Import the file instead and set identifier columns to Text (in Excel: Data >
  From Text/CSV > Transform Data, then change the column type to Text).
- Cells starting with `=`, `+`, `-` or `@` may be interpreted as formulas by spreadsheet
  programs. CSV Tidy does not alter such values; review untrusted data before opening it in a
  spreadsheet.
- Reports include source values. Keep them local if the data is private.
- Not included: Excel (`.xlsx`) files, hosted or multi-user web access, accounts, databases,
  streaming for very large files, delimiter detection. See
  [docs/MAINTENANCE.md](docs/MAINTENANCE.md) for the roadmap.

## Feedback and bug reports

Please open an [issue](https://github.com/JudikaM/csv-tidy/issues) using the templates. Use
synthetic or anonymized data only, and never attach real personal or customer data. Security
issues: see [SECURITY.md](SECURITY.md). If you try CSV Tidy on real-world exports, the task
lists in [docs/USER_TESTING.md](docs/USER_TESTING.md) and the questions in
[docs/USER_VALIDATION.md](docs/USER_VALIDATION.md) describe the feedback that helps most.

## Contributing and license

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md) and
[CHANGELOG.md](CHANGELOG.md). CSV Tidy is released under the [MIT License](LICENSE).
