# Benchmarks

`scripts/benchmark.py` generates synthetic Indonesian-format transactions with a fixed seed in
a temporary directory, then times, with `examples/profiles/transactions-id.toml`:

- `check_file`, and `clean_file` (the preview);
- building and rendering the report (JSON and text with the default limits);
- `export_clean` (cleaned CSV and output profile);
- a batch of five files holding the same number of rows in total, through `run_batch` (as
  `csv-tidy batch clean` without `--apply`) and through the local interface's session (the
  several-files preview followed by the "Save all results as ZIP" download, which recomputes
  and exports every ready file).

About 2% of rows contain problems by default (half fixable by trimming, half invalid dates).
Export and the batch need results without remaining errors, so those steps use files whose
problems are all repairable. No dataset is committed.

```powershell
.\.venv\Scripts\python.exe scripts\benchmark.py --rows 1000
.\.venv\Scripts\python.exe scripts\benchmark.py --rows 100000
.\.venv\Scripts\python.exe scripts\benchmark.py --rows 100000 --memory
```

## Recorded results

Measured on 2026-10-14 on one developer machine: Windows 11 (10.0.26300), CPython 3.13.3,
12 logical CPUs, CSV Tidy 0.3.0, seed 20260211, issue rate 0.02. Single runs; expect variation
between runs and machines. These numbers are not performance guarantees.

| Rows | File size | Check | Clean preview | Report (JSON + text) | Export (CSV + profile) |
|-----:|----------:|------:|--------------:|---------------------:|-----------------------:|
| 1,000 | 0.06 MiB | 0.005 s | 0.015 s | < 0.001 s | 0.006 s |
| 100,000 | 5.98 MiB | 0.594 s | 1.855 s | 0.006 s | 0.105 s |
| 500,000 | 30.34 MiB | 2.738 s | 10.139 s | 0.029 s | 0.651 s |

Batch of five files with the same rows in total:

| Rows in total | `run_batch` clean preview | Interface: batch preview + ZIP |
|--------------:|--------------------------:|-------------------------------:|
| 1,000 | 0.017 s | 0.153 s |
| 100,000 | 2.117 s | 4.684 s |
| 500,000 | 10.615 s | 23.201 s |

That is roughly 180,000 rows per second for `check` and 50,000 for the clean preview on this
machine. A batch costs about the same as one file of the same total size. The interface's ZIP
takes about twice as long as the preview because it computes every file again when it is
downloaded and then exports the ready ones; this keeps the download consistent with the
files and settings at that moment. Report time does not grow with the file because details are
limited (`--max-details`, `--max-examples`, or the interface's limits); totals stay complete.

Peak Python memory traced with `tracemalloc` (`--memory`, which also slows execution) for
100,000 rows: about 69 MiB for `check`, 168 MiB for the clean preview, 6 MiB for the report,
15 MiB for the export, 34 MiB for the five-file batch preview (files are processed one after
another and only a summary is kept per file), and 56 MiB for the interface's batch preview
plus ZIP (the ZIP itself is held in memory). This counts Python allocations only, not total
process memory.

**What has and has not been measured.** The largest file measured is 500,000 rows (30 MiB)
with five columns, also split over five files. Larger files, more files, very wide files, and
files with very long fields have not been measured, and no claim is made about them. The
interface builds the ZIP in memory, so its size is bounded by `--max-file-mb` for the files
chosen together.

The local interface adds the transfer of the file from the browser to the local process and
the drawing of the listed rows and problems (by default at most 50 preview rows and 200
problems; adjustable in More settings). In the browser walk-through of 2026-10-13, a
structure check of a 300,000-row, two-column file (about 5 MiB) took about 2
seconds from the click to the result in headless Chrome on the same machine (1.7 seconds when
repeated with 0.3.0 on 2026-10-14). That is one
observation, not a benchmark. The interface refuses files above `--max-file-mb` (default
200); that limit is a safeguard, not a tested capacity.

## Memory growth

- All records are kept in memory (source records, and for `clean` also transformed records).
- Duplicate detection keeps one entry per distinct row and per distinct key value.
- Reports keep every issue in memory; `--max-details` limits only what is printed or saved.

- A decoding failure reads the file a second time as bytes to locate the bad bytes exactly.

For files that do not fit comfortably in memory, split them first. Streaming processing is on
the roadmap.
