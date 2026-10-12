# Benchmarks

`scripts/benchmark.py` generates synthetic Indonesian-format transactions with a fixed seed in
a temporary directory, then times `check_file`, `clean_file` (the preview), building and
rendering the report (JSON and text with the default limits), and `export_clean` (cleaned
CSV and output profile) with `examples/profiles/transactions-id.toml`. About 2% of rows contain problems by default
(half fixable by trimming, half invalid dates). Export needs a result without remaining
errors, so that step uses a second file of the same size whose problems are all repairable.
No dataset is committed.

```powershell
.\.venv\Scripts\python.exe scripts\benchmark.py --rows 1000
.\.venv\Scripts\python.exe scripts\benchmark.py --rows 100000
.\.venv\Scripts\python.exe scripts\benchmark.py --rows 100000 --memory
```

## Recorded results

Measured on 2026-10-13 on one developer machine: Windows 11 (10.0.26300), CPython 3.13.3,
12 logical CPUs, CSV Tidy 0.2.0, seed 20260211, issue rate 0.02.
Single runs; expect variation between runs and machines. These numbers are not performance
guarantees.

| Rows | File size | Check | Clean preview | Report (JSON + text) | Export (CSV + profile) |
|-----:|----------:|------:|--------------:|---------------------:|-----------------------:|
| 1,000 | 0.06 MiB | 0.005 s | 0.016 s | < 0.001 s | 0.006 s |
| 100,000 | 5.98 MiB | 0.586 s | 1.861 s | 0.007 s | 0.106 s |
| 500,000 | 30.34 MiB | 2.686 s | 10.795 s | 0.034 s | 0.542 s |

That is roughly 170,000 to 200,000 rows per second for `check` and 46,000 to 62,000 for the
clean preview on this machine. Report time does not grow with the file because details are
limited (`--max-details`, `--max-examples`); totals are still complete.

Peak Python memory traced with `tracemalloc` (`--memory`, which also slows execution) for
100,000 rows: about 69 MiB for `check`, 168 MiB for the clean preview, 6 MiB for the report,
and 15 MiB for the export. This counts Python allocations only, not total process memory.

**What has and has not been measured.** The largest file measured is 500,000 rows (30 MiB)
with five columns. Larger files, very wide files, and files with very long fields have not
been measured, and no claim is made about them. `batch` processes files one after another
through the same functions, so its time is the sum of its files and its memory is that of
the largest file; it was not benchmarked separately.

The local interface adds the transfer of the file from the browser to the local process and
the drawing of at most 50 preview rows and 200 problems. In the browser walk-through of
2026-10-13, a structure check of a 300,000-row, two-column file (about 5 MiB) took about 2
seconds from the click to the result in headless Chrome on the same machine. That is one
observation, not a benchmark. The interface refuses files above `--max-file-mb` (default
200); that limit is a safeguard, not a tested capacity.

## Memory growth

- All records are kept in memory (source records, and for `clean` also transformed records).
- Duplicate detection keeps one entry per distinct row and per distinct key value.
- Reports keep every issue in memory; `--max-details` limits only what is printed or saved.

- A decoding failure reads the file a second time as bytes to locate the bad bytes exactly.

For files that do not fit comfortably in memory, split them first. Streaming processing is on
the roadmap.
