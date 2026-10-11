# CSV Tidy

A Python CLI and library for validating and cleaning CSV files with explicit number and date
formats.

CSV Tidy helps you find, understand, and explicitly repair CSV data problems before importing
the data elsewhere: inconsistent field counts, missing required values, duplicate records and
keys, numbers in Indonesian (`1.250,50`), US (`1,250.50`), or canonical (`1250.50`) notation,
and numeric dates such as `DD/MM/YYYY`. It never guesses: it repairs only what you select,
reports everything else with record and line locations, and refuses to export a result that
still has errors.

**Status:** 0.1.0, an early release. It works locally and offline, with no network access,
telemetry, or AI services. It has not yet been validated with external users. Feedback is
welcome (see [Feedback](#feedback-and-bug-reports)).

Intended for developers building import pipelines, administrators preparing spreadsheet
exports, small organizations, and anyone handling mixed number and date conventions.

## Features

- Strict CSV reading: comma or semicolon, UTF-8 with or without BOM (or an explicit
  encoding), quoted fields with delimiters, quotes and line breaks, LF/CRLF. Undecodable
  bytes and malformed quoting stop the scan instead of being skipped.
- Structure checks: empty file, header-only file, blank lines, empty/duplicate headers, and
  records with too few or too many fields.
- Reusable TOML profiles: required columns, `text`/`decimal`/`date` types, number grammars,
  date formats, duplicate-row policy, and uniqueness keys.
- Identifiers such as `00123` and `081234567890` stay text; nothing is converted to numbers.
- Explicit transformations: trim selected columns, normalize selected numbers/dates,
  remove duplicates keeping the first record. Exact decimal arithmetic; no floats, no rounding.
- Dry-run preview with before/after examples and complete counts.
- Safe export: never overwrites the input (including symlink/hardlink aliases), refuses
  existing files unless `--overwrite`, and writes each file atomically.
- Generated output profile that validates the cleaned file and makes a second clean a no-op.
- English text and JSON reports with stable issue codes and documented exit codes.
- A Python API that uses the same pipeline as the CLI.

## Installation

Requires Python 3.11 or newer. CSV Tidy is **not published on PyPI**; install it from a
source checkout (or from a wheel attached to a GitHub release, once one is published).

Windows PowerShell (calling the virtual environment's interpreter directly, so the
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

`python -m csv_tidy` works the same as the `csv-tidy` command. For development
setup, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Quick start

The repository includes synthetic examples. The commands below use the Windows path
`.\.venv\Scripts\csv-tidy.exe`; on Linux/macOS use `.venv/bin/csv-tidy`.

A profile describes the source data and which repairs you allow
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

### Check

```powershell
csv-tidy check examples/transactions_fixable.csv --schema examples/profiles/transactions-id.toml
```

```text
Scan: complete; 4 data records, 5 physical lines, 0 blank lines
Result: 2 errors, 0 warnings

Issues (showing 2 of 2):
  ERROR invalid_number (record 2, line 3, column 'amount')
    ' 980,00 ' is not a valid number: the value has leading or trailing whitespace.
    Suggestion: Select trimming for 'amount' (transform trim) or fix the source value.
  ERROR invalid_date (record 3, line 4, column 'date')
    '28/02/2026 ' is not a valid date: the value has leading or trailing whitespace.
    Suggestion: Select trimming for 'date' (transform trim) or fix the source value.

Status: source validation failed (exit code 1)
```

JSON for pipelines (stdout contains only JSON; status messages go to stderr):

```powershell
csv-tidy check examples/transactions_unfixable.csv --schema examples/profiles/transactions-id.toml --format json --report output/report.json
```

### Preview a clean (dry run is the default)

```powershell
csv-tidy clean examples/transactions_fixable.csv --schema examples/profiles/transactions-id.toml --dry-run
```

```text
Transformations (applied in this order):
  1. trim: customer_id, amount, date
  2. normalize: amount (id -> canonical), date (DD/MM/YYYY -> YYYY-MM-DD)
  3. deduplicate: off

Changes: 9 fields changed in 4 records; 0 records removed; 4 records in the result
  record 1 (line 2), 'amount': '1.250,50' -> '1250.50' [normalize]
  record 2 (line 3), 'amount': ' 980,00 ' -> '980.00' [trim, normalize]
  record 3 (line 4), 'customer_id': ' 00789' -> '00789' [trim]
  ...
Source issues: 2 errors, 0 warnings (2 resolved, 0 unresolved, 0 removed with records)
Remaining output issues: 0 errors, 0 warnings (0 introduced by transformations)

Export: ready (run with --apply --output PATH to write it)
```

### Apply, and save the output profile

```powershell
csv-tidy clean examples/transactions_fixable.csv --schema examples/profiles/transactions-id.toml --apply --output output/transactions_clean.csv --output-schema output/transactions.output.toml
```

Result (`customer_id` keeps its leading zeros; the untouched `note` column keeps its double
space):

```text
transaction_id;customer_id;amount;date;note
TX-001;00123;1250.50;2026-02-01;First payment
TX-002;00456;980.00;2026-02-15;Paid in  two parts
TX-003;00789;12000;2026-02-28;"Note with ; semicolon"
TX-004;00123;-75.25;2024-02-29;Refund
```

The generated output profile describes the cleaned file, so it validates and re-cleans
without changes:

```powershell
csv-tidy check output/transactions_clean.csv --schema output/transactions.output.toml
csv-tidy clean output/transactions_clean.csv --schema output/transactions.output.toml --dry-run
```

### Problems that cannot be repaired block the export

```powershell
csv-tidy clean examples/transactions_unfixable.csv --schema examples/profiles/transactions-id.toml --apply --output output/invalid_result.csv
```

```text
  ERROR invalid_date (record 1, line 2, column 'date')
    '31/02/2026' is not a valid date: it could not be normalized because it matches DD/MM/YYYY but is not a valid calendar date.
  ERROR missing_required (record 2, line 3, column 'customer_id')
  ERROR invalid_number (record 3, line 4, column 'amount')

Export: blocked by 3 remaining output errors; no CSV is written.
Status: exit code 1
```

Other examples: US-format customers ([customers-us.toml](examples/profiles/customers-us.toml)
with `customers_valid.csv`, `customers_fixable.csv`), canonical data
([transactions-canonical.toml](examples/profiles/transactions-canonical.toml)), and
`customers_trim_duplicates.csv`, where trimming creates a duplicate key. That file is blocked
until you add `--deduplicate keys`.

## Options

Command-line options override the profile; omitted options never do. `--trim`/`--normalize`
replace the profile list (repeat for several columns); `--no-trim`/`--no-normalize` clear it.

| Option | Commands | Meaning |
|--------|----------|---------|
| `--schema PROFILE` | both | TOML profile |
| `--delimiter`, `--encoding`, `--number-format`, `--date-format` | both | source settings |
| `--output-delimiter`, `--output-encoding`, `--output-number-format`, `--output-date-format`, `--line-ending` | clean | output settings (default: follow the source) |
| `--trim COL`, `--normalize COL`, `--deduplicate off\|rows\|keys` | clean | explicit transformations |
| `--dry-run` / `--apply`, `--output PATH`, `--output-schema PATH` | clean | preview (default) or write |
| `--format text\|json`, `--report PATH`, `--max-details N`, `--max-examples N` | both / clean | reports |
| `--overwrite` | both | allow replacing existing output files (never inputs) |

Exit codes: `0` no blocking errors (warnings allowed), `1` data errors (`check`: in the source;
`clean`: remaining in the cleaned result), `2` usage, configuration, decoding/parsing, read or
write failure. Run `csv-tidy check --help` and `csv-tidy clean --help` for details. The full
reference is in [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

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
```

A runnable example is in [examples/api_example.py](examples/api_example.py). See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for result types and exceptions.

## Supported conventions and limits

- Number grammars: `id` (`1.250,50`), `us` (`1,250.50`), `canonical` (`1250.50`). Optional
  leading `+`/`-`. No currency symbols, scientific notation, NaN/Infinity, or other locales.
- Dates: numeric formats built from `YYYY`, `MM`/`M`, `DD`/`D` and `-`, `/`, `.` separators.
  No month names, times, or compact `YYYYMMDD`.
- The header row is required. Delimiters are `,` or `;` and are never auto-detected.
- Files are processed in memory. Duplicate detection memory grows with distinct rows/keys.
  The default field limit is 131,072 characters (`max_field_chars`). See
  [docs/BENCHMARKS.md](docs/BENCHMARKS.md).
- CSV has no column types. Spreadsheet programs may turn `00123` into `123` when opening a
  CSV directly. Import the file instead and set identifier columns to Text (in Excel: Data >
  From Text/CSV > Transform Data, then change the column type to Text).
- Cells starting with `=`, `+`, `-` or `@` may be interpreted as formulas by spreadsheet
  programs. CSV Tidy does not alter such values; review untrusted data before opening it in a
  spreadsheet.
- Reports include source values. Keep them local if the data is private.
- Not included in 0.1: Excel files, web UI, databases, streaming for very large files,
  delimiter detection. See [docs/MAINTENANCE.md](docs/MAINTENANCE.md) for the roadmap.

## Feedback and bug reports

Please open an [issue](https://github.com/JudikaM/csv-tidy/issues) using the templates. Use
synthetic or anonymized data only, and never attach real personal or customer data. Security
issues: see [SECURITY.md](SECURITY.md). If you try CSV Tidy on real-world exports, the
questions in [docs/USER_VALIDATION.md](docs/USER_VALIDATION.md) describe the feedback that
helps most.

## Contributing and license

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md) and
[CHANGELOG.md](CHANGELOG.md). CSV Tidy is released under the [MIT License](LICENSE).
