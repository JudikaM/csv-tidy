# Benchmarks

`scripts/benchmark.py` generates synthetic Indonesian-format transactions with a fixed seed in
a temporary directory, then times `check_file` and `clean_file` (dry run, nothing exported)
with `examples/profiles/transactions-id.toml`. About 2% of rows contain problems by default
(half fixable by trimming, half invalid dates). No dataset is committed.

```powershell
.\.venv\Scripts\python.exe scripts\benchmark.py --rows 1000
.\.venv\Scripts\python.exe scripts\benchmark.py --rows 100000
.\.venv\Scripts\python.exe scripts\benchmark.py --rows 100000 --memory
```

## Recorded results

Measured on 2026-10-11 on one developer machine: Windows 11 (10.0.26300), CPython 3.13.3,
12 logical CPUs, CSV Tidy 0.1.0, seed 20260211, issue rate 0.02. Single runs; expect
variation between runs and machines. These numbers are not performance guarantees.

| Rows | File size | Step | Time | Rows/second |
|-----:|----------:|------|-----:|------------:|
| 1,000 | 0.06 MiB | check | 0.014 s | ~71,000 |
| 1,000 | 0.06 MiB | clean (dry run) | 0.014 s | ~71,000 |
| 100,000 | 5.98 MiB | check | 0.485 s | ~206,000 |
| 100,000 | 5.98 MiB | clean (dry run) | 1.612 s | ~62,000 |

Peak Python memory traced with `tracemalloc` (`--memory`, which also slows execution) for
100,000 rows: about 69 MiB for `check` and 162 MiB for `clean`. This counts Python
allocations only, not total process memory.

## Memory growth

- All records are kept in memory (source records, and for `clean` also transformed records).
- Duplicate detection keeps one entry per distinct row and per distinct key value.
- Reports keep every issue in memory; `--max-details` limits only what is printed or saved.

For files that do not fit comfortably in memory, split them first. Streaming processing is on
the roadmap.
