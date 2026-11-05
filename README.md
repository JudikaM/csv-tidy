<div align="center">

# Datakrit

**Check and clean table files, explicitly.**

CSV files with numbers and dates in the formats you declare, nothing guessed. A Python CLI,
library, and local browser interface. Offline, typed, and MIT licensed.

Datakrit was called CSV Tidy until 1.2.0.

[![CI](https://github.com/JudikaM/datakrit/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/JudikaM/datakrit/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/JudikaM/datakrit?label=release&color=6d5dfc)](https://github.com/JudikaM/datakrit/releases/latest)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab?logo=python&logoColor=white)](https://github.com/JudikaM/datakrit/blob/main/README.md#installation)
[![Typed](https://img.shields.io/badge/typing-typed-2f855a)](https://github.com/JudikaM/datakrit/blob/main/src/datakrit/py.typed)
[![License: MIT](https://img.shields.io/github/license/JudikaM/datakrit?color=blue)](https://github.com/JudikaM/datakrit/blob/main/LICENSE)

[Quick start](https://github.com/JudikaM/datakrit/blob/main/README.md#quick-start) ·
[Local interface](https://github.com/JudikaM/datakrit/blob/main/README.md#local-interface-for-people-who-prefer-forms) ·
[Profiles](https://github.com/JudikaM/datakrit/blob/main/README.md#create-a-profile) ·
[Library](https://github.com/JudikaM/datakrit/blob/main/README.md#library) ·
[Configuration](https://github.com/JudikaM/datakrit/blob/main/docs/CONFIGURATION.md) ·
[Changelog](https://github.com/JudikaM/datakrit/blob/main/CHANGELOG.md)

</div>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/JudikaM/datakrit/main/docs/images/interface-dark.png">
  <img src="https://raw.githubusercontent.com/JudikaM/datakrit/main/docs/images/interface-light.png" alt="The Datakrit local interface with a semicolon-separated file loaded: a side bar with New check, Find, and the file in this session marked ready to save; in the middle the file card with the Save button and the status line saying 4 rows are ready with 9 values changed; on the right a panel with the loaded profile, 4 of 5 columns with rules, the unique key, and the output settings.">
</picture>

Datakrit helps you find, understand, and explicitly repair CSV data problems before importing
the data elsewhere: inconsistent field counts, missing required values, duplicate records and
keys, numbers in Indonesian (`1.250,50`), US (`1,250.50`), or canonical (`1250.50`) notation,
and numeric dates such as `DD/MM/YYYY`. It never guesses: it repairs only what you select,
reports everything else with record and line locations, and refuses to export a result that
still has errors.

**Status:** 2.1. Profiles, command-line options, exit codes, issue codes, JSON reports, and
the Python API follow Semantic Versioning; [docs/STABILITY.md](https://github.com/JudikaM/datakrit/blob/main/docs/STABILITY.md) lists
exactly what stays compatible in 2.x. The look and layout of the local interface are not part
of that promise. Coming from an earlier version? See the upgrade section near the end, or
[Migrating from 0.x](https://github.com/JudikaM/datakrit/blob/main/README.md#migrating-from-0x). It works
locally and offline, with no telemetry or AI services; only the explicit `datakrit update`
command goes online. It has not yet been tested in sessions with outside users; that is
planned after 1.0, and feedback is welcome (see [Feedback](https://github.com/JudikaM/datakrit/blob/main/README.md#feedback-and-bug-reports)).

There are three ways to use the same engine:

| You are | Use | Start with |
|---------|-----|------------|
| A developer automating imports | the `datakrit` command or the Python API | [Quick start](https://github.com/JudikaM/datakrit/blob/main/README.md#quick-start) |
| Someone who works in Excel and prefers forms | the local interface, `datakrit ui` (one file or several files) | [Local interface](https://github.com/JudikaM/datakrit/blob/main/README.md#local-interface-for-people-who-prefer-forms) |
| Processing a folder of exports | `datakrit batch`, or several files in `datakrit ui` | [Many files](https://github.com/JudikaM/datakrit/blob/main/README.md#many-files-at-once) |

## Features

- Strict CSV reading: comma, semicolon, or tab, UTF-8 with or without BOM (or an explicit
  encoding), quoted fields with delimiters, quotes and line breaks, LF/CRLF. Undecodable
  bytes and malformed quoting stop the scan instead of being skipped.
- Structure checks: empty file, header-only file, blank lines, empty/duplicate headers, and
  records with too few or too many fields.
- Reusable TOML profiles: required columns, `text`/`decimal`/`date` types, number grammars,
  date formats, duplicate-row policy, and uniqueness keys. `datakrit profile init` writes a
  starting profile from a file's header, with optional guided questions.
- Identifiers such as `00123` and `081234567890` stay text; nothing is converted to numbers.
- Explicit transformations: trim selected columns, normalize selected numbers/dates,
  neutralize spreadsheet formulas in selected text columns, remove duplicates keeping the
  first record. Exact decimal arithmetic; no floats, no rounding.
- Dry-run preview with before/after examples and complete counts.
- Safe export: never overwrites the input (including symlink/hardlink aliases), refuses
  existing files unless `--overwrite`, and writes each file atomically.
- Generated output profile that validates the cleaned file and makes a second clean a no-op.
- Reports that start with the verdict, say what was and was not checked, list unresolved
  problems before repaired ones, and end with the next step. English text and JSON with
  stable issue codes and documented exit codes.
- Batch processing of files and folders with one profile and separate results per file.
- A local browser interface that runs the same pipeline without a command line, for one
  file or several files with the same rules (results per file, all results as one ZIP).

## Installation

There are three ways to install Datakrit. This README describes version 2.1.0; changes made
after a release are listed under "Unreleased" in the [changelog](https://github.com/JudikaM/datakrit/blob/main/CHANGELOG.md).

### From PyPI

Requires Python 3.11 or newer. Install Datakrit from
[PyPI](https://pypi.org/project/datakrit/) inside a virtual environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install datakrit
.\.venv\Scripts\datakrit.exe --version
```

On Linux/macOS: `python3 -m venv .venv`, then `.venv/bin/python -m pip install datakrit`.
If you use [pipx](https://pipx.pypa.io/), `pipx install datakrit` installs the programs into
their own environment and puts them on your `PATH`.

### Windows app (no Python needed)

The Windows app contains the local interface only: no Python, no terminal, and no console
window. For the `datakrit` command or the Python API, install from PyPI instead.

1. Open the latest release on the
   [Releases page](https://github.com/JudikaM/datakrit/releases) and download
   `Datakrit-2.1.0-windows-x64.zip`.
2. Check the file. In PowerShell, in the folder that holds the download, run

   ```powershell
   Get-FileHash .\Datakrit-2.1.0-windows-x64.zip -Algorithm SHA256
   ```

   and compare the hash with the SHA-256 of the zip in the release notes. If they differ, do
   not run the app; delete the file and download it again from the Releases page.
3. Unzip the file (right-click, **Extract All...**), open the `Datakrit` folder, and
   double-click `Datakrit.exe`. The local interface opens in your browser. It stops when you
   press **Quit** on the page, or by itself 10 minutes after its page was closed.

The app is not code-signed, so Windows SmartScreen may say "Windows protected your PC" the
first time. Only for a file you downloaded from the official release page and checked as
above: choose **More info**, then **Run anyway**. Never do this for a copy from anywhere
else.

To update the app, download the zip of the new release, check it in the same way, and
replace the old `Datakrit` folder. Profiles keep working. The `licenses` folder inside it
holds the license notices of Datakrit and of the software the app bundles.

### From the GitHub release (wheel) or a source checkout

Requires Python 3.11 or newer. Every release on the
[GitHub Releases page](https://github.com/JudikaM/datakrit/releases) also carries a wheel and
a source distribution. Download the wheel `datakrit-2.1.0-py3-none-any.whl` from the latest
release and install it inside a virtual environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install <path-to>\datakrit-2.1.0-py3-none-any.whl
.\.venv\Scripts\datakrit.exe --version
```

On Linux/macOS: `python3 -m venv .venv`, then
`.venv/bin/python -m pip install <path-to>/datakrit-2.1.0-py3-none-any.whl`. You can also
install from a source checkout:

Windows PowerShell (calling the virtual environment's programs directly, so the
ExecutionPolicy does not need to change):

```powershell
git clone https://github.com/JudikaM/datakrit.git
cd datakrit
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\datakrit.exe --version
```

Linux/macOS:

```bash
git clone https://github.com/JudikaM/datakrit.git
cd datakrit
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/datakrit --version
```

### After installing with pip

**For people who do not use a command line.** After installing with pip, run this once for
each Windows user (or Linux user) who will use Datakrit:

```powershell
.\.venv\Scripts\datakrit.exe shortcut install
```

It adds a **Datakrit** icon to the Desktop and the Start Menu, which opens the
[local interface](https://github.com/JudikaM/datakrit/blob/main/README.md#local-interface-for-people-who-prefer-forms) in the browser without a
console window, and an **Update Datakrit** entry to the Start Menu. The icons keep working
after updates; `datakrit shortcut remove` removes them again.

**Updating.** `datakrit update` (or the **Update Datakrit** entry) installs the latest
release from GitHub with pip, which verifies the SHA-256 that GitHub publishes for the wheel;
it is the same file as on PyPI, so `python -m pip install --upgrade datakrit` works as well.
`datakrit update` is the only command that connects to the internet, and only when you run
it; `datakrit update --check` just reports whether a newer version exists. Close Datakrit
before updating. Profiles keep working across versions.

**How the examples are written.** Every command below is written for Windows PowerShell and
a virtual environment named `.venv`, so it can be pasted as is from the folder that holds
it:
`.\.venv\Scripts\datakrit.exe ...`. On Linux/macOS replace that program with
`.venv/bin/datakrit` (and `\` in paths with `/`). If the virtual environment is activated, or
Datakrit is installed where your shell finds it, plain `datakrit ...` works; the hints
printed by the tool use that short form. `python -m datakrit` is equivalent. For development
setup, see [CONTRIBUTING.md](https://github.com/JudikaM/datakrit/blob/main/CONTRIBUTING.md).

## Quick start

Four steps with the synthetic examples in this repository: **check → preview → apply →
re-check**.

```powershell
# 1. Check: what is wrong? (exit code 1: two errors)
.\.venv\Scripts\datakrit.exe check examples\transactions_fixable.csv --profile examples\profiles\transactions-id.toml

# 2. Preview: what would the selected repairs change? (writes nothing)
.\.venv\Scripts\datakrit.exe clean examples\transactions_fixable.csv --profile examples\profiles\transactions-id.toml

# 3. Apply: write the cleaned copy and a profile that describes it
.\.venv\Scripts\datakrit.exe clean examples\transactions_fixable.csv --profile examples\profiles\transactions-id.toml --apply --output output\transactions_clean.csv --output-profile output\transactions.output.toml

# 4. Re-check the result with its generated profile (exit code 0)
.\.venv\Scripts\datakrit.exe check output\transactions_clean.csv --profile output\transactions.output.toml
```

The profile describes the source data and which repairs you allow
([examples/profiles/transactions-id.toml](https://github.com/JudikaM/datakrit/blob/main/examples/profiles/transactions-id.toml)):

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
Datakrit 2.1.0 - check
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
  - Fix the listed values in the source file, or preview explicit repairs (a dry run that writes nothing): datakrit clean examples\transactions_fixable.csv --profile examples\profiles\transactions-id.toml

Status: source validation failed (exit code 1)
```

The `Checked` and `Not checked` lines state the coverage of the run. **Without column rules
only the file structure is checked**: numbers, dates, required values, and unique keys are
checked only for columns declared in a profile, and nothing is inferred from the data. A run
without rules says so even when it passes:

```powershell
.\.venv\Scripts\datakrit.exe check examples\transactions_unfixable.csv --delimiter ";"
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
profile declares `date` and `amount` (see [Create a profile](https://github.com/JudikaM/datakrit/blob/main/README.md#create-a-profile)).

JSON for pipelines (stdout contains only JSON; status messages go to stderr):

```powershell
.\.venv\Scripts\datakrit.exe check examples\transactions_unfixable.csv --profile examples\profiles\transactions-id.toml --format json --report output\report.json
```

### 2. Preview a clean (dry run is the default)

```text
Datakrit 2.1.0 - clean (dry run, nothing written)
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
.\.venv\Scripts\datakrit.exe clean output\transactions_clean.csv --profile output\transactions.output.toml
```

### Problems that cannot be repaired block the export

```powershell
.\.venv\Scripts\datakrit.exe clean examples\transactions_unfixable.csv --profile examples\profiles\transactions-id.toml --apply --output output\invalid_result.csv
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

Other examples: US-format customers ([customers-us.toml](https://github.com/JudikaM/datakrit/blob/main/examples/profiles/customers-us.toml)
with `customers_valid.csv`, `customers_fixable.csv`), canonical data
([transactions-canonical.toml](https://github.com/JudikaM/datakrit/blob/main/examples/profiles/transactions-canonical.toml)), and
`customers_trim_duplicates.csv`, where trimming creates a duplicate key. That file is blocked
until you add `--deduplicate keys`.

## Create a profile

`profile init` reads the header of a file and writes a starting profile in which **every
column is text**. It never guesses types from values or column names; you choose them.

```powershell
# A template to edit by hand (never prompts; safe in scripts and CI)
.\.venv\Scripts\datakrit.exe profile init examples\transactions_fixable.csv --delimiter ";" --output output\my-profile.toml

# Guided questions: which columns are numbers or dates, required, unique, and what to repair
.\.venv\Scripts\datakrit.exe profile init examples\transactions_fixable.csv --output output\my-profile.toml --interactive

# Everything as options, for automation
.\.venv\Scripts\datakrit.exe profile init examples\transactions_fixable.csv --delimiter ";" --output output\my-profile.toml --decimal amount --date date --number-format id --date-format DD/MM/YYYY --required transaction_id --key transaction_id --trim amount --trim date --normalize amount --normalize date --output-number-format canonical --output-date-format YYYY-MM-DD
```

A column whose format differs from the rest of the file gets its own with
`--column-number-format amount=us` or `--column-date-format due=MM/DD/YYYY`.

The delimiter and encoding you give are written into the profile. An existing profile file is
refused unless `--overwrite` is given, the input can never be the output, unknown column
names and inconsistent choices are rejected before anything is written, and the guided mode
can be cancelled with `q` or Ctrl+C (exit code 130, nothing written). Profiles made this way
work with `check`, `clean`, `batch`, and the local interface. Details:
[docs/CONFIGURATION.md](https://github.com/JudikaM/datakrit/blob/main/docs/CONFIGURATION.md#creating-profiles).

## Local interface (for people who prefer forms)

Start it with the **Datakrit** icon (see [Installation](https://github.com/JudikaM/datakrit/blob/main/README.md#installation)), the `datakrit-ui`
program, or from a command line:

```powershell
.\.venv\Scripts\datakrit.exe ui
```

This starts a small web server **on this computer only** and opens a page in your browser.
The page is laid out like a desktop application:

- **Side bar** (left; it folds to a row of icons, and opens over the page in a phone-sized
  window): **New check** (start again with nothing loaded), **Find** (show only the table rows
  of the current step that contain a word: a column, a value, or a problem), **Files**,
  **Profiles**, **Reports**, and **Settings** (each leads to where that part lives), and
  **In this session**: every loaded file with its row count and whether it is not checked
  yet, has problems, or is fine. Clicking a file opens its latest result. At the bottom: the
  version, the theme switch (dark and light), and **Quit Datakrit**.
- **Main column**: a card takes the file (drop it, or use **+**) with its separator,
  encoding, and one file or several files, and one button that does the next thing:
  **Check**, then **Preview cleaning**, then **Save**. Under it, the steps show one at a
  time: the one you pick, or the one with the newest result.
- **Side panel** (right; under the main column in narrower windows): the current
  **Profile** (Load, Save), how many **Columns** have rules (Edit), the **Unique keys**
  (Add), and the **Output** separator, encoding, line ending, and formula protection (Edit).
  Each action leads to the control in step 3; nothing is changed from the panel itself.
  Under these rows, **How to use** opens a short guide: the six steps in one line each (each
  step name leads to that step) and a tip about reusing profiles. It is closed until you
  open it, and the page remembers your choice.

The steps:

1. Choose **one file** or **several files with the same rules**, then the separator (comma
   semicolon, or tab) and the encoding.
2. Look at the first rows exactly as they are stored (with several files, pick which one).
3. Describe the columns with drop-downs and checkboxes, or load a profile.
4. Check: problems are listed with record, file line, column, and what to do. With several
   files there is one row per file (No problems, Problems found, Not fully read, Failed) and
   **Details** opens the problems of a file.
5. Preview the cleaned copy: every changed value is shown before and after. With several
   files each file is **Ready** or **Blocked** (or could not be read), with the reason.
6. Save the cleaned CSV, the profile of the cleaned file, the report, and your rules as a
   profile (through the browser's download folder). With several files: **Save CSV** per
   ready file, or **Save all results as ZIP**: a cleaned CSV and output profile for every
   ready file, a report for every file, and a batch summary. Files that are blocked or could
   not be read are never exported; they are in the ZIP as reports only.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/JudikaM/datakrit/main/docs/images/interface-preview-dark.png">
  <img src="https://raw.githubusercontent.com/JudikaM/datakrit/main/docs/images/interface-preview-light.png" alt="Step 5 of the local interface: the cleaned copy has no problems, a table lists every changed value before and after with the repair that changed it, and the cleaned rows are shown with changed values highlighted.">
</picture>

Dates are chosen from a list of common formats (with an example such as `31/12/2026`), and
**Other…** accepts any supported format. Suggestions name the page's own controls, for
example *Tick "Repair: trim spaces" for "amount" in step 3*. Every control works with the
keyboard alone, focus is always visible, the page follows the system's reduced-motion
setting, and text keeps a contrast of at least 4.5:1 in both themes (checked automatically
in a headless browser; a session with a screen reader is planned after 1.0).

**More settings** also holds the longest allowed value (`max_field_chars`, saved in profiles)
and how many problems, changed values, and preview rows are listed (counts stay complete;
saved reports use the same limits).

The page always shows the current status and the next step, clears results that no longer
match when the file or a setting changes, and explains why saving is blocked while problems
remain. It uses the same functions as the commands; a profile saved from the page works with
`datakrit check`, and a profile written for the commands can be loaded into the page.

Privacy and safety: the server listens on `127.0.0.1` only, the page loads nothing from the
internet, and the address contains a one-time key without which other programs and web pages
cannot use it. The chosen files are copied into a private temporary folder that is removed
when you select **Quit** (or press Ctrl+C in the window that started it). Started from the icon,
without a console window, it also stops by itself 10 minutes after its page was closed
(`datakrit ui --idle-minutes N` does the same from a command line). Your original files
are never written to. Options: `--port N`, `--no-browser`, `--max-file-mb N` (largest file,
and largest total of several files together; default 200). The limits of the interface are
listed under [Supported conventions and limits](https://github.com/JudikaM/datakrit/blob/main/README.md#supported-conventions-and-limits). A
step-by-step guide for first-time users is in
[docs/USER_TESTING.md](https://github.com/JudikaM/datakrit/blob/main/docs/USER_TESTING.md#guide-for-administrative-staff).

## Many files at once

```powershell
# Preview every transactions_*.csv file directly inside examples\ with one profile
.\.venv\Scripts\datakrit.exe batch clean examples --pattern "transactions_*.csv" --profile examples\profiles\transactions-id.toml

# Write the files that are ready, their output profiles, and one report per file
.\.venv\Scripts\datakrit.exe batch clean examples --pattern "transactions_*.csv" --profile examples\profiles\transactions-id.toml --apply --output-dir output\cleaned --output-profiles --report-dir output\reports --format json
```

```text
Datakrit 2.1.0 - batch clean (dry run, nothing written)
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
- **Without a command line:** the several-files mode of `datakrit ui` runs the same batch
  function and gives the same status per file.

## Options

Command-line options override the profile; omitted options never do. `--trim`/`--normalize`
replace the profile list (repeat for several columns); `--no-trim`/`--no-normalize` clear it.

| Option | Commands | Meaning |
|--------|----------|---------|
| `--profile PROFILE` | check, clean, batch | TOML profile |
| `--delimiter`, `--encoding`, `--number-format`, `--date-format` | check, clean, batch, profile init | source settings |
| `--output-delimiter`, `--output-encoding`, `--output-number-format`, `--output-date-format`, `--line-ending` | clean, batch clean | output settings (default: follow the source) |
| `--trim COL`, `--normalize COL`, `--deduplicate off\|rows\|keys` | clean, batch clean, profile init | explicit transformations |
| `--neutralize-formulas COL` | clean, batch clean | protect formula-like values in a text column |
| `--dry-run` / `--apply`, `--output PATH`, `--output-profile PATH` | clean | preview (default) or write |
| `--apply`, `--output-dir DIR`, `--output-profiles`, `--report-dir DIR`, `--pattern GLOB`, `--recursive` | batch | many files |
| `--format text\|json`, `--report PATH`, `--max-details N` | check, clean, batch | reports |
| `--max-examples N` | clean, batch clean | before/after examples listed in reports |
| `--overwrite` | all writing commands | allow replacing existing output files (never inputs) |

Exit codes: `0` no blocking errors (warnings allowed), `1` data errors (`check`: in the source;
`clean`: remaining in the cleaned result), `2` usage, configuration, decoding/parsing, read or
write failure, `130` cancelled by the user. Every command has `--help`. The full reference is
in [docs/CONFIGURATION.md](https://github.com/JudikaM/datakrit/blob/main/docs/CONFIGURATION.md). What stays compatible in 1.x (profiles,
options, exit codes, issue codes, JSON reports, the Python API) is listed in
[docs/STABILITY.md](https://github.com/JudikaM/datakrit/blob/main/docs/STABILITY.md).

The 0.x names `--schema`, `--output-schema`, and `--output-schemas` were removed in 2.0.0.

## Upgrading from CSV Tidy

Profiles keep working unchanged. The programs, the module, the error class, the shortcuts,
and the repository have the new name, and JSON reports carry `schema_version` 3 with
`tool.name` `datakrit` (nothing else in them changed):

| CSV Tidy 1.x | Datakrit 2.0 |
|--------------|--------------|
| `csv-tidy`, `csv-tidy-ui`, `python -m csv_tidy` | `datakrit`, `datakrit-ui`, `python -m datakrit` |
| `import csv_tidy`, `CsvTidyError` | `import datakrit`, `DatakritError` |
| shortcuts "CSV Tidy" and "Update CSV Tidy" | "Datakrit" and "Update Datakrit" |
| `https://github.com/JudikaM/csv-tidy` | `https://github.com/JudikaM/datakrit` |

- **From CSV Tidy 1.2.0:** run `csv-tidy update` (or the **Update CSV Tidy** entry). It
  installs Datakrit with the same SHA-256 check, replaces the old shortcuts if you have any,
  and removes CSV Tidy. On Windows, `csv-tidy update` cannot remove its own running program,
  so it prints the command to run afterwards (`python -m pip uninstall -y csv-tidy`); the
  **Update CSV Tidy** entry does it by itself. Then start Datakrit with the **Datakrit** icon
  or `datakrit ui`.
- **From CSV Tidy 1.1.x or older:** run `python -m pip install datakrit` (or install the
  wheel from the [Releases page](https://github.com/JudikaM/datakrit/releases)), then `datakrit shortcut install` if you used the
  icons (it replaces the old ones), then `python -m pip uninstall csv-tidy`.

The full table, with the removed options and keywords, is in the
[changelog](https://github.com/JudikaM/datakrit/blob/main/CHANGELOG.md#upgrading-to-200).

## Migrating from 0.x

Profiles need no change. What differs:

| 0.x | 1.0 and later |
|-----|---------------|
| `--schema`, `--output-schema`, `--output-schemas` | `--profile`, `--output-profile`, `--output-profiles` (the old names were removed in 2.0.0) |
| JSON reports: `schema_version: 1` | `schema_version: 2` |
| `"mode": "dry-run"`; artifact kinds `"output CSV"`, `"output profile"` | `"mode": "dry_run"`; `"output_csv"`, `"output_profile"` |
| a cleaned value longer than `max_field_chars`: code `field_too_large` | `output_field_too_large` (reading still stops with `field_too_large`) |
| `export_clean(output_schema=...)`, `run_batch(output_schemas=...)` | `output_profile=...`, `output_profiles=...` (the old names were removed in 2.0.0) |

Programs that read JSON reports should accept `schema_version` 3 (2.x; 1.x wrote 2); clean
reports also have a top-level `artifacts` list. The full list, with the reasons, is in the
[changelog](https://github.com/JudikaM/datakrit/blob/main/CHANGELOG.md#100---2026-11-04).

## Library

```python
from datakrit import check_file, clean_file, export_clean, load_profile

profile = load_profile("examples/profiles/transactions-id.toml")
check = check_file("examples/transactions_fixable.csv", profile)
print(check.exit_code, [(i.code, i.record, i.column) for i in check.issues])
# 1 [('invalid_number', 2, 'amount'), ('invalid_date', 3, 'date')]

result = clean_file("examples/transactions_fixable.csv", profile)
if result.export_ready:
    export_clean(result, "output/clean.csv", output_profile="output/clean.output.toml")
else:
    print(result.export_blocked_reason)
```

Many files: `run_batch("clean", select_inputs(["exports/"]), profile)`. A runnable example is
in [examples/api_example.py](https://github.com/JudikaM/datakrit/blob/main/examples/api_example.py). See
[docs/ARCHITECTURE.md](https://github.com/JudikaM/datakrit/blob/main/docs/ARCHITECTURE.md) for result types and exceptions, and
[docs/STABILITY.md](https://github.com/JudikaM/datakrit/blob/main/docs/STABILITY.md) for the names that form the public API.

## Supported conventions and limits

- Number grammars: `id` (`1.250,50`), `us` (`1,250.50`), `canonical` (`1250.50`). Optional
  leading `+`/`-`. No currency symbols, scientific notation, NaN/Infinity, or other locales.
- Dates: numeric formats built from `YYYY`, `MM`/`M`, `DD`/`D` and `-`, `/`, `.` separators,
  or without separators from `YYYY`, `MM`, `DD` (for example `YYYYMMDD`). No month names or
  times.
- The header row is required. Delimiters are `,`, `;`, or tab (`--delimiter tab`, `"\t"` in
  profiles) and are never auto-detected.
- Files are processed in memory, one file at a time. Duplicate detection memory grows with
  distinct rows/keys. The default field limit is 131,072 characters (`max_field_chars`).
  Measured times and memory for up to 500,000 rows are in
  [docs/BENCHMARKS.md](https://github.com/JudikaM/datakrit/blob/main/docs/BENCHMARKS.md); larger files have not been measured.
- CSV has no column types. Spreadsheet programs may turn `00123` into `123` when opening a
  CSV directly. Import the file instead and set identifier columns to Text (in Excel: Data >
  From Text/CSV > Transform Data, then change the column type to Text).
- Cells starting with `=`, `+`, `-` or `@` may be interpreted as formulas by spreadsheet
  programs (CSV injection). Datakrit changes such values only when you select
  `--neutralize-formulas COLUMN` (or `neutralize_formulas` in the profile, or **Repair:
  protect formulas** in the local interface): it then puts a `'` in front of them in text
  columns. Otherwise review untrusted data before opening it in a spreadsheet.
- The local interface serves one person on this computer, in one session: files and results
  are kept in memory (and in a private temporary folder) only while it runs, nothing is kept
  after **Quit**, and there is no list of recent files. Each file, or several files together,
  may be up to 200 MB (`--max-file-mb N`). Larger or many files are better handled by
  `datakrit batch`.
- Reports include source values. Keep them local if the data is private.
- Not included: Excel (`.xlsx`) files, hosted or multi-user web access, accounts, databases,
  streaming for very large files, delimiter detection. See
  [docs/MAINTENANCE.md](https://github.com/JudikaM/datakrit/blob/main/docs/MAINTENANCE.md) for the roadmap.

## Feedback and bug reports

Please open an [issue](https://github.com/JudikaM/datakrit/issues) using the templates. Use
synthetic or anonymized data only, and never attach real personal or customer data. Security
issues: see [SECURITY.md](https://github.com/JudikaM/datakrit/blob/main/SECURITY.md). If you try Datakrit on real-world exports, the task
lists in [docs/USER_TESTING.md](https://github.com/JudikaM/datakrit/blob/main/docs/USER_TESTING.md) and the questions in
[docs/USER_VALIDATION.md](https://github.com/JudikaM/datakrit/blob/main/docs/USER_VALIDATION.md) describe the feedback that helps most.

## Contributing and license

Contributions are welcome; see [CONTRIBUTING.md](https://github.com/JudikaM/datakrit/blob/main/CONTRIBUTING.md) and
[CHANGELOG.md](https://github.com/JudikaM/datakrit/blob/main/CHANGELOG.md). Everyone taking part is expected to follow the
[Code of Conduct](https://github.com/JudikaM/datakrit/blob/main/CODE_OF_CONDUCT.md). Datakrit is released under the [MIT License](https://github.com/JudikaM/datakrit/blob/main/LICENSE). The icons of the local
interface are covered by the copyright and license notices in [NOTICE.md](https://github.com/JudikaM/datakrit/blob/main/NOTICE.md),
which the wheel and the sdist include.
