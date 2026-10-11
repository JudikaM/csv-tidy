# Architecture

CSV Tidy is a small, dependency-light pipeline. Runtime code uses the Python standard library
plus `tomli-w` (writing TOML output profiles; Python only ships a TOML reader).

## Pipeline

```
profile.toml ──► schema.load_profile ──┐
CLI options ──► Overrides ─────────────┴─► schema.resolve_settings ─► Settings
                                                                        │
input.csv ──► reader.read_csv ─► Table (header, records, lines, fatal) ◄┘
                    │
                    ├─► validation.validate_table(stage="source") ─► source issues   (check stops here)
                    │
                    └─► normalization.transform: trim → normalize → deduplicate
                              │
                              └─► validation.validate_table(stage="output") ─► output issues
                                        │
                                        └─► api.export_clean ─► output.write_artifact (CSV, profile)
reporting: CheckResult / CleanResult ─► JSON dict ─► text or JSON
```

| Module | Responsibility |
|--------|----------------|
| `formats.py` | Number grammars (`id`, `us`, `canonical`) and date-format tokens; exact parsing/formatting |
| `schema.py` | Strict profile loading, override precedence, output-profile generation and TOML writing |
| `reader.py` | Strict decoding and CSV parsing into text fields with record indexes and line ranges |
| `validation.py` | Header, structure, required, number, date, and duplicate checks → `Issue` list |
| `normalization.py` | Selected transformations and change/removal tracking |
| `output.py` | Path identity checks, collisions, overwrite policy, atomic writes, CSV serialization |
| `api.py` | Public `check_file`, `clean_file`, `export_clean`; result types |
| `reporting.py` | Report dictionaries, JSON, and English text |
| `cli.py` | Argument parsing, exit codes, stdout/stderr separation |

## Result model and public API

```python
from csv_tidy import check_file, clean_file, export_clean, load_profile, Overrides

profile = load_profile("examples/profiles/transactions-id.toml")
check = check_file("data.csv", profile)  # CheckResult

# CleanResult, computed in memory only; nothing is written yet.
result = clean_file("data.csv", profile, overrides=Overrides(trim=("amount",)))
if result.export_ready:
    export_clean(result, "output/clean.csv", output_schema="output/clean.output.toml")
```

- `CheckResult`: `issues`, `errors`, `warnings`, `scan` (`ScanInfo`), `settings`, `exit_code`
  (0 valid, 1 source errors, 2 incomplete scan), `ok`.
- `CleanResult`: `source_issues` (with `status`), `output_issues` (with `introduced`),
  `changes` (`FieldChange`), `removed` (`RemovedRecord`), `header`, `rows`, `output_profile`,
  `export_ready`, `exit_code`, `csv_text()`, `output_profile_toml()`.
- `Issue`: `code`, `severity` (`error`, `warning`, `fatal`), `stage`, `record`,
  `line_start`, `line_end`, `column`, `value`, `message`, `suggestion`, `related_record`,
  `related_line`.
- Exceptions (all subclasses of `CsvTidyError`, CLI exit code 2): `ProfileError` (invalid
  profile/option), `InputError` (input cannot be opened), `OutputError` (unsafe path, existing
  file without `overwrite`, blocked export, or write failure; `outcomes` lists artifacts
  already written). Data problems, including fatal parsing failures, are returned as issues.
- Core functions never print or call `sys.exit`. The CLI uses exactly these functions.

## Invariants (covered by tests)

1. Source bytes are never modified (hash checked before and after `check`/`clean`).
2. Fields of unselected columns are byte-for-byte unchanged in the output.
3. Records keep source order; records disappear only through explicit deduplication.
4. Records with a wrong field count are never transformed or removed and always block export.
5. An exported CSV passes `check` with its generated output profile.
6. A second `clean` with the output profile makes no changes (idempotence).
7. Report totals are complete even when details are truncated; incomplete scans are never valid.
8. Issue order and report content are deterministic for the same input and settings.

## Important decisions

- **Explicit over automatic.** Types validate; only listed columns are trimmed/normalized;
  deduplication is opt-in and keeps the first record. Nothing is guessed (dates, delimiters,
  number grammars, missing values).
- **No floats.** Numbers are parsed into digit strings; `Decimal` is built from text only.
- **Own date tokens instead of `strptime`.** Results never depend on the machine locale.
- **Separate source and output validation.** Output rules apply to cleaned values, so
  canonical output is never validated with Indonesian source rules.
- **In-memory processing.** The file is read as a stream but records are kept in memory for
  cleaning and duplicate detection. Memory grows with file size and distinct rows/keys
  (see [BENCHMARKS.md](BENCHMARKS.md)). Streaming is a roadmap item.
- **Delimiter auto-detection is not provided.** A single-column header containing the other
  supported delimiter produces a `possible_wrong_delimiter` hint instead.
- **`tomli-w` for TOML output.** Writing TOML correctly requires escaping rules; the generated
  profile is also parsed back and compared before it is written.
