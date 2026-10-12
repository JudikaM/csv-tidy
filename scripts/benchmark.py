"""Reproducible synthetic benchmark for check, clean preview, reports, and export.

Usage:
    python scripts/benchmark.py --rows 1000            # smoke size
    python scripts/benchmark.py --rows 200000 --memory # larger run with peak-memory tracing

Data is generated with a fixed seed into a temporary directory and deleted afterwards. The
results describe this machine and configuration only; they are not performance guarantees.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

from csv_tidy import check_file, clean_file, export_clean, load_profile
from csv_tidy.reporting import clean_report, render_clean_text, to_json

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "examples" / "profiles" / "transactions-id.toml"


def id_amount(rng: random.Random) -> str:
    whole = rng.randint(0, 9_999_999)
    grouped = f"{whole:,}".replace(",", ".")
    return f"{'-' if rng.random() < 0.05 else ''}{grouped},{rng.randint(0, 99):02d}"


def generate(path: Path, rows: int, issue_rate: float, seed: int, unfixable: bool = True) -> None:
    rng = random.Random(seed)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("transaction_id;customer_id;amount;date;note\r\n")
        for i in range(1, rows + 1):
            amount = id_amount(rng)
            date = f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(2020, 2026)}"
            customer = f"{rng.randint(0, 99999):05d}"
            roll = rng.random()
            if roll < issue_rate / 2:
                amount = f" {amount} "  # fixable by trim
            elif roll < issue_rate and unfixable:
                date = "31/02/2026"  # unfixable
            handle.write(f"TX-{i:08d};{customer};{amount};{date};synthetic row {i}\r\n")


def measure(label: str, func, memory: bool) -> dict:
    if memory:
        tracemalloc.start()
    start = time.perf_counter()
    result = func()
    elapsed = time.perf_counter() - start
    peak = None
    if memory:
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    return {
        "step": label,
        "seconds": round(elapsed, 3),
        "peak_traced_mib": None if peak is None else round(peak / 2**20, 1),
        "result": result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument(
        "--issue-rate", type=float, default=0.02, help="share of rows with problems"
    )
    parser.add_argument("--seed", type=int, default=20260211)
    parser.add_argument("--memory", action="store_true", help="trace peak Python memory (slower)")
    args = parser.parse_args()
    profile = load_profile(PROFILE)
    with tempfile.TemporaryDirectory(prefix="csv-tidy-bench-") as tmp:
        data = Path(tmp) / "transactions.csv"
        generate(data, args.rows, args.issue_rate, args.seed)
        size = data.stat().st_size
        preview = clean_file(data, profile)

        def report() -> int:
            built = clean_report(preview, "dry-run", 100, 10)
            return len(to_json(built)) + len(render_clean_text(built))

        # Export needs a result without remaining errors, so it uses a second file whose
        # problems are all repairable by the profile's trim selection.
        fixable = Path(tmp) / "fixable.csv"
        generate(fixable, args.rows, args.issue_rate, args.seed, unfixable=False)
        ready = clean_file(fixable, profile)

        def export() -> int:
            written = export_clean(
                ready, Path(tmp) / "out.csv", output_schema=Path(tmp) / "out.toml", overwrite=True
            )
            return len(written)

        steps = [
            measure("check", lambda: check_file(data, profile).errors, args.memory),
            measure("clean preview", lambda: len(clean_file(data, profile).changes), args.memory),
            measure("report (JSON + text, default limits)", report, args.memory),
            measure("export (CSV + output profile)", export, args.memory),
        ]
    report = {
        "rows": args.rows,
        "file_mib": round(size / 2**20, 2),
        "issue_rate": args.issue_rate,
        "seed": args.seed,
        "profile": "examples/profiles/transactions-id.toml",
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "memory_traced": args.memory,
        "steps": [
            {**s, "rows_per_second": round(args.rows / s["seconds"]) if s["seconds"] else None}
            for s in steps
        ],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
