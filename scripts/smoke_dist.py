"""Install the built wheel into a fresh virtual environment and exercise it end to end.

Usage: python scripts/smoke_dist.py [DIST_DIR]

The wheel is installed outside the source tree and commands run from a temporary
directory, so the local ``src/`` package cannot hide a broken distribution.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UI_CHECK = """
import threading, urllib.request
from csv_tidy.ui import create_server
server, session, url = create_server(0)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = url.split("/?")[0]
page = urllib.request.urlopen(url, timeout=10).read().decode("utf-8")
assert session.token in page and "CSV Tidy" in page
for name in ("/app.css", "/app.js"):
    assert len(urllib.request.urlopen(base + name, timeout=10).read()) > 1000, name
server.shutdown(); server.server_close(); session.close()
"""


def run(cmd: list[str], cwd: Path, expect: int) -> str:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    shown = " ".join([Path(cmd[0]).name, *cmd[1:]])
    if proc.returncode != expect:
        sys.exit(
            f"FAILED ({proc.returncode}, expected {expect}): {shown}\n{proc.stdout}\n{proc.stderr}"
        )
    print(f"ok ({proc.returncode}): {shown}")
    return proc.stdout


UI_ASSETS = ("index.html", "app.css", "app.js")


def check_ui_assets(wheel: Path, dist: Path) -> None:
    """The interface is three static files; both archives must carry all of them."""
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = set(archive.namelist())
    missing = [n for n in UI_ASSETS if f"csv_tidy/ui_static/{n}" not in wheel_names]
    if missing:
        sys.exit(f"{wheel.name} lacks interface assets: {missing}")
    sdists = sorted(dist.glob("csv_tidy-*.tar.gz"))
    if len(sdists) != 1:
        sys.exit(f"expected exactly one csv_tidy sdist in {dist}, found {len(sdists)}")
    with tarfile.open(sdists[0]) as archive:
        sdist_names = archive.getnames()
    missing = [
        n
        for n in UI_ASSETS
        if not any(m.endswith(f"/src/csv_tidy/ui_static/{n}") for m in sdist_names)
    ]
    if missing:
        sys.exit(f"{sdists[0].name} lacks interface assets: {missing}")
    print(f"ok: interface assets present in {wheel.name} and {sdists[0].name}")


def main() -> None:
    dist = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "dist")
    wheels = sorted(dist.glob("csv_tidy-*.whl"))
    if len(wheels) != 1:
        sys.exit(f"expected exactly one csv_tidy wheel in {dist}, found {len(wheels)}")
    check_ui_assets(wheels[0], dist)
    with tempfile.TemporaryDirectory(prefix="csv-tidy-smoke-") as tmp:
        tmp_path = Path(tmp)
        env_dir = tmp_path / "venv"
        venv.EnvBuilder(with_pip=True).create(env_dir)
        bin_dir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
        python = bin_dir / ("python.exe" if sys.platform == "win32" else "python")
        cli = bin_dir / ("csv-tidy.exe" if sys.platform == "win32" else "csv-tidy")
        run([str(python), "-m", "pip", "install", "-q", str(wheels[0].resolve())], tmp_path, 0)

        work = tmp_path / "work"
        shutil.copytree(
            ROOT / "examples", work / "examples", ignore=shutil.ignore_patterns("__pycache__")
        )
        where = run([str(python), "-I", "-c", "import csv_tidy; print(csv_tidy.__file__)"], work, 0)
        if not Path(where.strip()).resolve().is_relative_to(env_dir.resolve()):
            sys.exit(f"csv_tidy was imported from {where.strip()}, not from the fresh environment")

        source = work / "examples" / "transactions_fixable.csv"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        profile = "examples/profiles/transactions-id.toml"
        run([str(cli), "--version"], work, 0)
        run([str(cli), "--help"], work, 0)
        run([str(python), "-I", "-m", "csv_tidy", "--version"], work, 0)
        run([str(cli), "check", "examples/transactions_valid.csv", "--schema", profile], work, 0)
        run([str(cli), "check", "examples/transactions_fixable.csv", "--schema", profile], work, 1)
        run(
            [
                str(cli),
                "check",
                "examples/transactions_unfixable.csv",
                "--schema",
                profile,
                "--format",
                "json",
                "--report",
                "output/report.json",
            ],
            work,
            1,
        )
        run(
            [
                str(cli),
                "clean",
                "examples/transactions_fixable.csv",
                "--schema",
                profile,
                "--dry-run",
            ],
            work,
            0,
        )
        run(
            [
                str(cli),
                "clean",
                "examples/transactions_fixable.csv",
                "--schema",
                profile,
                "--apply",
                "--output",
                "output/transactions_clean.csv",
                "--output-schema",
                "output/transactions.output.toml",
            ],
            work,
            0,
        )
        run(
            [
                str(cli),
                "check",
                "output/transactions_clean.csv",
                "--schema",
                "output/transactions.output.toml",
            ],
            work,
            0,
        )
        again = run(
            [
                str(cli),
                "clean",
                "output/transactions_clean.csv",
                "--schema",
                "output/transactions.output.toml",
                "--dry-run",
            ],
            work,
            0,
        )
        if "Changes: 0 fields changed" not in again:
            sys.exit("second clean with the output profile changed data")
        run(
            [
                str(cli),
                "clean",
                "examples/transactions_unfixable.csv",
                "--schema",
                profile,
                "--apply",
                "--output",
                "output/invalid_result.csv",
            ],
            work,
            1,
        )
        if (work / "output" / "invalid_result.csv").exists():
            sys.exit("an invalid result CSV was written")
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            sys.exit("the source file changed")
        run(
            [
                str(cli),
                "profile",
                "init",
                "examples/transactions_fixable.csv",
                "--delimiter",
                ";",
                "--output",
                "output/starting.toml",
            ],
            work,
            0,
        )
        started = run(
            [
                str(cli),
                "check",
                "examples/transactions_fixable.csv",
                "--schema",
                "output/starting.toml",
            ],
            work,
            0,
        )
        if "PASSED (structure only)" not in started:
            sys.exit("a starting profile should check the structure only")
        batch = run(
            [
                str(cli),
                "batch",
                "clean",
                "examples",
                "--pattern",
                "transactions_*fix*.csv",
                "--schema",
                profile,
                "--apply",
                "--output-dir",
                "output/batch",
            ],
            work,
            1,
        )
        if "1 CSV file written" not in batch:
            sys.exit("batch clean did not write exactly the one exportable file")
        if not (work / "output" / "batch" / "transactions_fixable.clean.csv").exists():
            sys.exit("batch clean did not write the expected output name")
        # The interface's page, style sheet and script must be inside the wheel.
        run([str(python), "-I", "-c", UI_CHECK], work, 0)
        api = run([str(python), "-I", "examples/api_example.py"], work, 0)
        if "clean: export ready = True" not in api:
            sys.exit("API example output was unexpected")
    print(f"smoke test passed for {wheels[0].name}")


if __name__ == "__main__":
    main()
