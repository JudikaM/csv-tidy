# Configuration and data contracts

This is the authoritative reference for CSV Tidy 0.1 profiles, options, defaults, and the
input/output contracts of `check` and `clean`.

## Profiles

A profile is a strict TOML file. Unknown keys, wrong types, unsupported values, and
inconsistent settings are rejected with an error (exit code 2); nothing is silently ignored.

```toml
schema_version = 1            # required; only 1 is supported

[source]                      # how to read the input
delimiter = ";"               # "," or ";"                         default ","
encoding = "utf-8"            # any Python codec name               default "utf-8"
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
Calendar validity is checked (`31/02/2026` and `29/02/2025` are invalid; `29/02/2024` is valid).
`01/02/2026` is 1 February with `DD/MM/YYYY` and 2 January with `MM/DD/YYYY`; CSV Tidy never
guesses which one you meant. Month names, times, time zones, and compact `YYYYMMDD` are not
supported in 0.1.

## Reading rules

- The first non-blank row is the header; a header is required.
- Fields are always text. Quoted fields may contain delimiters, doubled quotes (`""`), and
  line breaks; such records span several physical lines and are reported with a line range.
- Comma and semicolon delimiters, LF and CRLF line endings, UTF-8 with or without BOM.
  With `encoding = "utf-8"` a UTF-8 BOM is accepted and removed from the header.
- Decoding is strict: undecodable bytes stop the scan with a fatal `decode_error`; nothing is
  replaced or skipped.
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
| Malformed quoting, unterminated quote | fatal `malformed_csv`; scan incomplete |
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

Duplicate comparison uses exact text (case-sensitive). A key with any empty part never forms
an identity, so records with empty identifiers are not grouped together.

## Transformations (`clean` only)

Applied in this fixed order, only to selected columns of records with the correct field count:

1. **trim** — remove leading/trailing whitespace; internal whitespace is kept.
2. **normalize** — rewrite valid `decimal`/`date` values from the source format to the output
   format. Invalid values are left unchanged and reported.
3. **deduplicate** — `rows` removes later exact duplicate rows; `keys` also removes later
   records whose configured key matches a kept record. The first record is always kept.
   Comparison uses the transformed values.
4. **output validation** — the result is validated with output rules: normalized columns use
   the output format; other columns keep their source format.

Source issues are marked `resolved`, `unresolved`, or `removed` (record removed by
deduplication). Output issues created by transformations are marked `introduced` (for example,
duplicate keys that appear after trimming).

## Commands and exit codes

| Code | `check` | `clean` (dry run or `--apply`) |
|------|---------|-------------------------------|
| 0 | no source errors (warnings allowed) | no remaining output errors |
| 1 | source data errors | output errors remain; nothing is exported |
| 2 | usage, profile/option, read, decoding/parsing, or write failure | same |

- `check` validates source rules and never modifies files. Profile transformations are ignored.
- `clean` is a dry run unless `--apply` is given. `--apply` requires `--output`; `--output` and
  `--output-schema` require `--apply`; `--dry-run` and `--apply` cannot be combined. A dry run
  may save a report with `--report` but never writes a CSV or output profile.
- A fatal parsing error makes the scan incomplete: reports say so, counts cover only what was
  read, and the exit code is 2. A partially scanned file is never reported as valid.

## Output safety

- The input CSV and input profile can never be an output, report, or output profile. Paths
  are compared after resolution and by file identity, so symlink and hardlink aliases are
  rejected.
- Two artifacts may not refer to the same file.
- Existing files are refused unless `--overwrite` is given (which still never allows writing
  an input).
- Each file is written to a temporary file in the same directory and moved into place. On
  failure the temporary file is removed and an existing file keeps its previous content.
  Writes are atomic per file, not across files: the CSV is written first, then the output
  profile, then the report. If a later write fails, the report and stderr state which files
  were written, and the exit code is 2.
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

`--format text|json` selects the report format for stdout and `--report PATH`. JSON contains
`schema_version` (currently 1), `tool`, `command`, `source`, `scan` (`complete`,
`data_records`, `physical_lines`, `blank_lines`, `fatal_error`), `summary`, issue lists, and
`details` (`limit`, totals, `shown`, `truncated`). `clean` adds `mode`, `output`,
`transformations`, `changes` (counts and limited before/after examples), `source_issues`,
`output_issues`, and `export.artifacts`. `--max-details` limits listed issues and
`--max-examples` limits examples; totals are always complete. Issue values longer than 200
characters are truncated in JSON (`value_truncated: true`). Reports contain no timestamps, so
the same input and settings produce the same report. Status messages go to stderr.

## Versioning

`schema_version` (profiles) and the report `schema_version` change only for incompatible
changes; compatible additions keep the version. The Python API follows the package version.
See [RELEASE.md](RELEASE.md).
