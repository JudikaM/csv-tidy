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
                    └─► normalization.transform: trim → normalize → neutralize formulas → deduplicate
                              │
                              └─► validation.validate_table(stage="output") ─► output issues
                                        │
                                        └─► api.export_clean ─► output.write_artifact (CSV, profile)
reporting: CheckResult / CleanResult ─► JSON dict ─► text or JSON

entry points that all call api.check_file / clean_file / export_clean:
  cli (check, clean) · batch.run_batch (many files) · ui (local HTTP page) ·
  profile_init (header ─► Profile ─► schema.profile_to_toml)
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
| `profile_init.py` | Starting profiles from a header: explicit choices, guided questions through injected `ask`/`say` callables |
| `batch.py` | Input selection, artifact planning and collision checks, per-file isolation, batch summary |
| `ui.py`, `ui_static/` | Loopback HTTP server, session token and origin checks, and the single page: `index.html`, `app.css`, `theme.js` (theme and folded side bar before the first paint), `app.js`, `logo.png`; no dependencies (see "The local page" below) |
| `shortcuts.py` | Desktop and Start Menu shortcuts (Windows `.lnk` through PowerShell and the Windows Script Host, Linux desktop entries) |
| `update.py` | `csv-tidy update`: GitHub release lookup, wheel and SHA-256 selection, the pip command; the only network access |
| `cli.py` | Argument parsing, exit codes, stdout/stderr separation |

## Result model and public API

```python
from csv_tidy import check_file, clean_file, export_clean, load_profile, Overrides

profile = load_profile("examples/profiles/transactions-id.toml")
check = check_file("data.csv", profile)  # CheckResult

# CleanResult, computed in memory only; nothing is written yet.
result = clean_file("data.csv", profile, overrides=Overrides(trim=("amount",)))
if result.export_ready:
    export_clean(result, "output/clean.csv", output_profile="output/clean.output.toml")
```

- `CheckResult`: `issues`, `errors`, `warnings`, `scan` (`ScanInfo`), `settings`, `header`,
  `exit_code` (0 valid, 1 source errors, 2 incomplete scan), `ok`.
- `CleanResult`: `source_issues` (with `status`), `output_issues` (with `introduced`),
  `changes` (`FieldChange`), `removed` (`RemovedRecord`), `header`, `rows`, `output_profile`,
  `source_errors`, `source_warnings`, `output_errors`, `output_warnings`, `export_ready`,
  `export_blocked_reason` (`None` when ready), `exit_code`, `ok`, `csv_text()`,
  `output_profile_toml()`.
- `ScanInfo.fatal` is a `FatalError` (`code`, `message`, `line`) or `None`; `Settings.source`
  and `Settings.output` are `SourceSettings` and `OutputSettings`.
- `export_clean(result, output, *, output_profile=None, overwrite=False)` returns one
  `ArtifactOutcome` per file written, with `kind` `output_csv` or `output_profile`.
- `run_batch(action, select_inputs(paths), profile, ...)` returns a `BatchResult` with one
  `FileOutcome` per file and the aggregate `exit_code`. `BatchInput(path, relative, label)`
  may carry a `label` that names the file in outcomes and reports instead of its path (the
  local interface passes the original file name). `BatchResult.mode` is `dry_run`, `apply`,
  or `None` (check). The internal `batch.batch_report` turns the result into the summary
  dictionary that the CLI prints.
- `Issue`: `code`, `severity` (`error`, `warning`, `fatal`), `stage`, `record`,
  `line_start`, `line_end`, `column`, `value`, `message`, `suggestion`, `related_record`,
  `related_line`, `status`, `introduced`, `remedy`.
- `Profile` and `ColumnSpec` objects built directly are validated with the same rules as
  TOML profiles (by the internal `schema.validate_profile`) before any data is read. Lists are
  accepted wherever tuples are: the internal `schema.canonical_profile` validates a profile and
  returns a tuple-based copy (unset values stay unset), used by both settings resolution and
  `profile_to_toml`.
- Results keep `source_file`/`profile_file`: absolute paths captured when the inputs were read.
  `export_clean` protects them even if the working directory changes afterwards.
- Exceptions (all subclasses of `CsvTidyError`, CLI exit code 2): `ProfileError` (invalid
  profile/option), `InputError` (input cannot be opened), `OutputError` (unsafe path, existing
  file without `overwrite`, blocked export, or write failure; `outcomes` lists artifacts
  already written). Data problems, including fatal parsing failures, are returned as issues.
- Core functions never print or call `sys.exit`. The CLI uses exactly these functions.
- The public API is exactly `csv_tidy.__all__` ([STABILITY.md](STABILITY.md)). Module
  functions named in this document (`schema.validate_profile`, `schema.canonical_profile`,
  `batch.batch_report`, and the like) are internal and may change in any release.
- Renamed keyword arguments keep their 0.x names as deprecated aliases through the internal
  decorator `api.renamed_keyword`: the old name raises `DeprecationWarning`, both names
  together raise `TypeError`. The CLI does the same for renamed options (a hidden option
  with its own destination, a warning on stderr).

## Invariants (covered by tests)

1. Source bytes are never modified (hash checked before and after `check`/`clean`).
2. A value selected for normalization counts as repaired only if it was parsed in its source
   format and converted; otherwise it stays an output error.
3. Fields of unselected columns are byte-for-byte unchanged in the output.
4. Records keep source order; records disappear only through explicit deduplication.
5. Records with a wrong field count are never transformed or removed and always block export.
6. An exported CSV passes `check` with its generated output profile.
7. A second `clean` with the output profile makes no changes (idempotence).
8. Report totals are complete even when details are truncated; incomplete scans are never valid.
   After a decoding failure the counts cover every complete line in front of the bad bytes.
9. Issue order and report content are deterministic for the same input and settings.
10. Each read enforces its own `max_field_chars`, also when reads overlap in threads, and the
    process-wide `csv.field_size_limit` is restored after the last read.
11. The CLI, batch processing, and the local interface produce the same results for the same
    file and settings, because all of them call the functions in `api.py`.

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
- **Per-read field limit.** `csv.field_size_limit` is one value for the whole process. While
  reads overlap, the reader holds it at the largest limit any active read needs and checks
  each parsed field against that read's own limit; the previous value is restored when the
  last read ends, including after exceptions. Code outside CSV Tidy that changes the limit
  during a read is outside this guarantee.
- **Decoding failures are located by parsing the valid prefix again.** Text decoding is
  buffered, so the stream fails before the lines in front of the bad bytes are parsed. The
  reader then decodes the bytes up to the failure and parses those complete lines, which
  gives exact counts and a line number for LF, CRLF, and CR files in any encoding.
- **Several files in the interface use `run_batch`.** The page's several-files mode calls the
  same batch function as `csv-tidy batch`, so statuses and exit codes cannot drift apart.
  Downloads recompute each file with `clean_file` and export it with `export_clean` into
  the private session folder; the ZIP is refused if a file's export readiness differs from
  the status shown.
- **A local web page instead of a desktop toolkit.** The interface is a standard-library
  HTTP server on the loopback address plus one static page. This adds no dependency, works
  with keyboard and screen readers through ordinary HTML controls, and can be tested over
  HTTP. The browser cannot hand the server a path, so the page sends the file's bytes to
  the local process and receives results as downloads; that also means the original file
  cannot be overwritten. The server holds one session: the latest file and results.
- **Icons instead of an installer or a bundled executable.** A `gui-scripts` entry point
  (`csv-tidy-ui`) gives a program without a console window, made by pip itself, and
  `csv-tidy shortcut install` points icons at it. Updates replace the package in place, so
  the icons keep working. A self-contained executable was not chosen: unsigned
  executables trigger SmartScreen warnings, and every user would have to replace the file
  on each update. Without a console nobody can press Ctrl+C, so the server stops itself
  after a period without contact from its page.
- **Updates are explicit and verified.** Only `csv-tidy update` connects to the internet.
  It installs the wheel attached to a GitHub release and passes GitHub's SHA-256 digest to
  pip in the URL fragment, which pip checks before installing.
- **Remedies, not interface text, come from validation.** Issues carry a short `remedy`
  code. The CLI keeps its English suggestions; the interface writes its own instructions
  that name its controls.
- **No type detection, also in the interface and `profile init`.** Both start every column
  as text and show example values only as a reading aid.
- **Delimiter auto-detection is not provided.** A single-column header containing the other
  supported delimiter produces a `possible_wrong_delimiter` hint instead.
- **`tomli-w` for TOML output.** Writing TOML correctly requires escaping rules; the generated
  profile is also parsed back and compared before it is written.

## The local page

The page is one static HTML file with its style sheet and two scripts, served by `ui.py` with
a content security policy that allows nothing else: no inline styles or scripts, no `eval`,
no `innerHTML`, and no external fonts, icons, or requests. Icons are inline SVG paths from
Lucide, drawn in `currentColor`. `app.js` builds every dynamic element with
`document.createElement` and `textContent`, so file contents are never parsed as HTML.

```
body
├── a.skip (to main)
├── nav#sidebar ── fold and step buttons · New check · Find (#find-box) · Files · Profiles ·
│                  Reports · Settings · section "In this session" (#session-files) ·
│                  version, theme switch, Quit
└── div.content
    ├── header.mobile-bar (narrow windows: opens the side bar over the page)
    ├── main#main ── breadcrumb and file menu · h1 · input card (file, separator, encoding,
    │                mode, primary button) · step navigation · status line · step area
    │                (sections step-1 … step-6; one is shown)
    └── aside.side-panel ── About this page · Profile · Columns · Unique keys · Output · Theme
```

All state lives in one `state` object in `app.js` and on the server's session; the side bar
list and the side panel rows are redrawn from it after every change (`refreshLook`), so they
cannot disagree with the steps. The server API (`/api/file`, `/api/preview`, `/api/check`,
`/api/clean`, `/api/batch`, `/api/download`, and the others in `ui.py`) is used only by this
page and is not part of the covered surface.
