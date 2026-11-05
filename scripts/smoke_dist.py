"""Install the built wheel into a fresh virtual environment and exercise it end to end.

Usage: python scripts/smoke_dist.py [DIST_DIR] [--work-dir DIR]

The wheel is installed outside the source tree and commands run from a temporary
directory, so the local ``src/`` package cannot hide a broken distribution. ``--work-dir``
puts that temporary directory into DIR (for example on another drive than TEMP).

At the end, the switch to Datakrit that ``csv-tidy update`` performs for a Datakrit release
is run for real with a dummy ``datakrit`` wheel built here: a small hook in the fresh
environment answers the release lookup with that local wheel, so nothing is downloaded or
published.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import re
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
import io, json, threading, tomllib, urllib.request, zipfile
from pathlib import Path
from csv_tidy.ui import create_server
server, session, url = create_server(0)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = url.split("/?")[0]
page = urllib.request.urlopen(url, timeout=10).read().decode("utf-8")
assert session.token in page and "CSV Tidy" in page and "Several files" in page
for name in ("/app.css", "/app.js"):
    assert len(urllib.request.urlopen(base + name, timeout=10).read()) > 1000, name

def post(path, data, kind="application/json", extra=None):
    body = data if isinstance(data, bytes) else json.dumps(data).encode()
    headers = {"X-CSV-Tidy-Token": session.token, "Content-Type": kind, **(extra or {})}
    request = urllib.request.Request(base + path, data=body, headers=headers)
    return urllib.request.urlopen(request, timeout=30).read()

ids = []
for number, name in enumerate(("transactions_fixable.csv", "transactions_unfixable.csv")):
    mode = "?mode=append" if number else ""
    data = Path("examples", name).read_bytes()
    stored = post("/api/file" + mode, data, "application/octet-stream", {"X-File-Name": name})
    ids.append(json.loads(stored)["file_id"])
profile = tomllib.loads(Path("examples/profiles/transactions-id.toml").read_text(encoding="utf-8"))
limits = {"max_details": 5, "max_examples": 5, "preview_rows": 2}
request = {"action": "clean", "file_ids": ids, "profile": profile, "limits": limits}
result = json.loads(post("/api/batch", request))
assert [f["status"] for f in result["report"]["files"]] == ["ready", "blocked"]
wanted = {"batch_id": result["batch_id"], "profile": profile, "limits": limits, "kind": "batch-zip"}
archive = post("/api/download", wanted)
names = sorted(zipfile.ZipFile(io.BytesIO(archive)).namelist())
assert "transactions_fixable.clean.csv" in names, names
assert "transactions_unfixable.clean.csv" not in names, names
server.shutdown(); server.server_close(); session.close()
print("interface batch and ZIP ok")
"""


def run(cmd: list[str], cwd: Path, expect: int, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL
    )
    shown = " ".join([Path(cmd[0]).name, *cmd[1:]])
    if proc.returncode != expect:
        sys.exit(
            f"FAILED ({proc.returncode}, expected {expect}): {shown}\n{proc.stdout}\n{proc.stderr}"
        )
    print(f"ok ({proc.returncode}): {shown}")
    return proc.stdout


UI_ASSETS = ("index.html", "app.css", "app.js", "theme.js", "logo.png", "logo-mark.png")


def check_ui_assets(wheel: Path, dist: Path) -> None:
    """Both archives must carry every static file of the interface (UI_ASSETS)."""
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


# A hook for the fresh environment only: with SMOKE_SWITCH_WHEEL set, `csv-tidy update`
# finds a Datakrit release whose wheel is that local file, pip installs it from disk with the
# same #sha256= check, and CSV Tidy shortcuts are reported in the menu. The variable is
# removed at once, so pip and Datakrit, started by the update, run without the hook.
SWITCH_HOOK = """
import os
_wheel = os.environ.pop("SMOKE_SWITCH_WHEEL", None)
if _wheel:
    import hashlib, sys
    from pathlib import Path
    from csv_tidy import shortcuts, update
    _path = Path(_wheel)
    _digest = hashlib.sha256(_path.read_bytes()).hexdigest()
    _url = "https://github.com/JudikaM/datakrit/releases/download/v2.0.0/" + _path.name
    _real_pip = update.run_pip

    def _fetch_json(address):
        assert address == "https://api.github.com/repos/JudikaM/datakrit/releases/latest", address
        asset = {"name": _path.name, "browser_download_url": _url, "digest": "sha256:" + _digest}
        return address, {"tag_name": "v2.0.0", "assets": [asset]}

    def _run_pip(command):
        return _real_pip([part.replace(_url, _path.as_uri()) for part in command])

    _menu = [s for s in shortcuts.planned(Path("x"), Path("x")) if s.place == "menu"]
    update.fetch_json = _fetch_json
    update.run_pip = _run_pip
    shortcuts.existing = lambda folder=None, platform=sys.platform: _menu
"""

DUMMY_MAIN = """\
import sys

def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    print("datakrit dummy:", " ".join(args))
    return 0 if args[:2] == ["shortcut", "install"] else 2

if __name__ == "__main__":
    sys.exit(main())
"""

LEFTOVER = re.compile(r"sv[-_]tidy", re.IGNORECASE)


def build_dummy_datakrit(folder: Path, version: str = "2.0.0") -> Path:
    """A minimal, valid datakrit wheel: a module that answers `python -m datakrit`."""
    info = f"datakrit-{version}.dist-info"
    files = {
        "datakrit/__init__.py": f'__version__ = "{version}"\n',
        "datakrit/__main__.py": DUMMY_MAIN,
        f"{info}/METADATA": f"Metadata-Version: 2.1\nName: datakrit\nVersion: {version}\n",
        f"{info}/WHEEL": (
            "Wheel-Version: 1.0\nGenerator: smoke_dist\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        ),
        f"{info}/entry_points.txt": "[console_scripts]\ndatakrit = datakrit.__main__:main\n",
    }
    record = []
    for name, text in files.items():
        data = text.encode()
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        record.append(f"{name},sha256={digest},{len(data)}")
    record.append(f"{info}/RECORD,,")
    wheel = folder / f"datakrit-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
        archive.writestr(f"{info}/RECORD", "\n".join(record) + "\n")
    return wheel


def pip_temp_dirs() -> set[Path]:
    return set(Path(tempfile.gettempdir()).glob("pip-*"))


def assert_csv_tidy_gone(env_dir: Path, temp_before: set[Path], what: str) -> None:
    """No CSV Tidy file may stay in the environment or in pip's temporary folders."""
    left = [p for p in env_dir.rglob("*") if LEFTOVER.search(p.name)]
    for folder in pip_temp_dirs() - temp_before:
        left += [p for p in folder.rglob("*") if LEFTOVER.search(p.name)]
    if left:
        sys.exit(f"{what} left CSV Tidy files behind: {[str(p) for p in left]}")
    print(f"ok: {what} left no CSV Tidy files")


def check_switch(wheel: Path, python: Path, cli: Path, env_dir: Path, work: Path) -> None:
    """Run the switch to Datakrit from the shortcut's command line and from the console
    program, and check that CSV Tidy is removed completely (or, while its program runs on
    Windows, that the printed command removes it completely)."""
    dummy = build_dummy_datakrit(work)
    quiet = {**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    site = run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"], work, 0
    )
    hook_dir = Path(site.strip())
    (hook_dir / "_smoke_switch.py").write_text(SWITCH_HOOK, encoding="utf-8")
    (hook_dir / "_smoke_switch.pth").write_text("import _smoke_switch\n", encoding="utf-8")
    env = {**quiet, "SMOKE_SWITCH_WHEEL": str(dummy)}
    reinstall = [str(python), "-m", "pip", "install", "-q", "--no-deps", str(wheel.resolve())]
    starts = (
        ("the shortcut's command", [str(python), "-m", "csv_tidy", "update", "--pause"]),
        (f"the {cli.name} program", [str(cli), "update"]),
    )
    for number, (what, command) in enumerate(starts):
        if number:
            run(reinstall, work, 0, env=quiet)
        before = pip_temp_dirs()
        out = run(command, work, 0, env=env)
        for text in (
            "CSV Tidy is now called Datakrit",
            "Step 1 of 3 done: Datakrit 2.0.0 is installed",
            "datakrit dummy: shortcut install --no-desktop",
            "Step 2 of 3 done",
            "Next: start Datakrit",
        ):
            if text not in out:
                sys.exit(f"the switch from {what} did not print {text!r}:\n{out}")
        if sys.platform == "win32" and number:
            # Windows cannot remove the running csv-tidy.exe; the command is printed instead.
            if "CSV Tidy cannot be removed while it runs (csv-tidy.exe)" not in out:
                sys.exit(f"the switch from {what} should have printed the remove command:\n{out}")
            run([str(python), "-m", "pip", "uninstall", "-y", "csv-tidy"], work, 0, env=quiet)
        elif "Step 3 of 3 done: CSV Tidy" not in out:
            sys.exit(f"the switch from {what} did not remove CSV Tidy:\n{out}")
        assert_csv_tidy_gone(env_dir, before, f"the switch from {what}")
        run([str(python), "-m", "datakrit", "shortcut", "install"], work, 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("dist", nargs="?", default=str(ROOT / "dist"))
    parser.add_argument("--work-dir", help="make the temporary directory inside this folder")
    options = parser.parse_args()
    dist = Path(options.dist)
    wheels = sorted(dist.glob("csv_tidy-*.whl"))
    if len(wheels) != 1:
        sys.exit(f"expected exactly one csv_tidy wheel in {dist}, found {len(wheels)}")
    check_ui_assets(wheels[0], dist)
    if options.work_dir:
        Path(options.work_dir).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="csv-tidy-smoke-", dir=options.work_dir) as tmp:
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
        run([str(cli), "check", "examples/transactions_valid.csv", "--profile", profile], work, 0)
        run([str(cli), "check", "examples/transactions_fixable.csv", "--profile", profile], work, 1)
        run(
            [
                str(cli),
                "check",
                "examples/transactions_unfixable.csv",
                "--profile",
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
                "--profile",
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
                "--profile",
                profile,
                "--apply",
                "--output",
                "output/transactions_clean.csv",
                "--output-profile",
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
                "--profile",
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
                "--profile",
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
                "--profile",
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
                "--profile",
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
                "--profile",
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
        # The interface's page, style sheet and script must be inside the wheel, and its
        # several-files mode must work from the installed package.
        run([str(python), "-I", "-c", UI_CHECK], work, 0)
        # The no-console program and the shortcuts that start it.
        gui = bin_dir / ("csv-tidy-ui.exe" if sys.platform == "win32" else "csv-tidy-ui")
        if not gui.exists():
            sys.exit(f"the csv-tidy-ui program is missing from {bin_dir}")
        icons = work / "icons"
        if sys.platform == "darwin":
            # Shortcuts are made on Windows and Linux; macOS gets a refusal (exit code 2).
            run([str(cli), "shortcut", "install", "--folder", str(icons)], work, 2)
            if icons.exists():
                sys.exit("shortcut install wrote into the folder although it refused")
        else:
            made = run([str(cli), "shortcut", "install", "--folder", str(icons)], work, 0)
            if made.count("created: ") != 2 or len(list(icons.iterdir())) != 2:
                sys.exit(f"shortcut install did not create two shortcuts:\n{made}")
            gone = run([str(cli), "shortcut", "remove", "--folder", str(icons)], work, 0)
            if gone.count("removed: ") != 2 or any(icons.iterdir()):
                sys.exit(f"shortcut remove did not remove the shortcuts:\n{gone}")
        run([str(cli), "update", "--help"], work, 0)
        api = run([str(python), "-I", "examples/api_example.py"], work, 0)
        if "clean: export ready = True" not in api:
            sys.exit("API example output was unexpected")
        # Last, because it removes CSV Tidy from the fresh environment.
        check_switch(wheels[0], python, cli, env_dir, work)
    print(f"smoke test passed for {wheels[0].name}")


if __name__ == "__main__":
    main()
