"""Install the built wheel into a fresh virtual environment and exercise it end to end.

Usage: python scripts/smoke_dist.py [DIST_DIR] [--work-dir DIR]

The wheel is installed outside the source tree and commands run from a temporary
directory, so the local ``src/`` package cannot hide a broken distribution. ``--work-dir``
puts that temporary directory into DIR (for example on another drive than TEMP).

At the end, the shortcut command that CSV Tidy 1.2.0's update runs when it switches an
installation to Datakrit replaces old shortcuts made in a folder, and ``update --version``
refuses versions before 2.0.0 (nothing is downloaded).
"""

from __future__ import annotations

import argparse
import hashlib
import os
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
from datakrit.ui import create_server
server, session, url = create_server(0)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = url.split("/?")[0]
page = urllib.request.urlopen(url, timeout=10).read().decode("utf-8")
assert session.token in page and "Datakrit" in page and "Several files" in page
for name in ("/app.css", "/app.js"):
    assert len(urllib.request.urlopen(base + name, timeout=10).read()) > 1000, name

def post(path, data, kind="application/json", extra=None):
    body = data if isinstance(data, bytes) else json.dumps(data).encode()
    headers = {"X-Datakrit-Token": session.token, "Content-Type": kind, **(extra or {})}
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


UI_ASSETS = ("index.html", "app.css", "app.js", "theme.js", "logo-mark.png")


def check_ui_assets(wheel: Path, dist: Path) -> None:
    """Both archives must carry every static file of the interface (UI_ASSETS)."""
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = set(archive.namelist())
    missing = [n for n in UI_ASSETS if f"datakrit/ui_static/{n}" not in wheel_names]
    if missing:
        sys.exit(f"{wheel.name} lacks interface assets: {missing}")
    # One package only: no module under another name, and no static file beyond UI_ASSETS.
    tops = {name.split("/", 1)[0] for name in wheel_names}
    info = wheel.name.split("-py3-")[0] + ".dist-info"
    if tops != {"datakrit", info}:
        sys.exit(f"{wheel.name} has unexpected top-level entries: {sorted(tops - {info})}")
    static = {n.rsplit("/", 1)[1] for n in wheel_names if n.startswith("datakrit/ui_static/")}
    if static != set(UI_ASSETS):
        sys.exit(f"{wheel.name} has other interface files: {sorted(static - set(UI_ASSETS))}")
    sdists = sorted(dist.glob("datakrit-*.tar.gz"))
    if len(sdists) != 1:
        sys.exit(f"expected exactly one datakrit sdist in {dist}, found {len(sdists)}")
    with tarfile.open(sdists[0]) as archive:
        sdist_names = archive.getnames()
    missing = [
        n
        for n in UI_ASSETS
        if not any(m.endswith(f"/src/datakrit/ui_static/{n}") for m in sdist_names)
    ]
    if missing:
        sys.exit(f"{sdists[0].name} lacks interface assets: {missing}")
    print(f"ok: interface assets present in {wheel.name} and {sdists[0].name}")


# Migration: shortcuts as CSV Tidy (Datakrit until 1.2.0) made them. CSV Tidy 1.2.0's update
# switches an installation with `python -m datakrit shortcut install [--no-desktop]`, which
# must replace them; here they are made in a folder instead of the Start Menu.
LEGACY_LNK = r"""
$s = New-Object -ComObject WScript.Shell
$a = $s.CreateShortcut((Join-Path $env:SMOKE_ICONS 'CSV Tidy.lnk'))
$a.TargetPath = (Join-Path $env:SMOKE_ICONS 'csv-tidy-ui.exe'); $a.Save()
$b = $s.CreateShortcut((Join-Path $env:SMOKE_ICONS 'Update CSV Tidy.lnk'))
$b.TargetPath = (Join-Path $env:SMOKE_ICONS 'python.exe')
$b.Arguments = '-m csv_tidy update --pause'; $b.Save()
"""


def make_legacy_shortcuts(folder: Path) -> list[str]:
    folder.mkdir(parents=True)
    if sys.platform == "win32":
        env = {**os.environ, "SMOKE_ICONS": str(folder)}
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", LEGACY_LNK],
            env=env,
            check=True,
        )
        return ["CSV Tidy.lnk", "Update CSV Tidy.lnk"]
    for name, command in (
        ("csv-tidy.desktop", '"/opt/old/bin/csv-tidy-ui"'),
        ("csv-tidy-update.desktop", '"/opt/old/bin/python" -m csv_tidy update --pause'),
    ):
        (folder / name).write_text(
            f"[Desktop Entry]\nType=Application\nName=CSV Tidy\nExec={command}\nX-CSV-Tidy=1\n",
            encoding="utf-8",
        )
    return ["csv-tidy-update.desktop", "csv-tidy.desktop"]


def check_migration(python: Path, cli: Path, work: Path) -> None:
    """The call that CSV Tidy 1.2.0's update makes replaces its shortcuts, and `update`
    refuses versions before 2.0.0 without going online."""
    if sys.platform != "darwin":
        icons = work / "legacy-icons"
        old = make_legacy_shortcuts(icons)
        if sorted(p.name for p in icons.iterdir()) != sorted(old):
            sys.exit(f"could not make the old shortcuts: {list(icons.iterdir())}")
        command = [str(python), "-m", "datakrit", "shortcut", "install", "--no-desktop"]
        out = run([*command, "--folder", str(icons)], work, 0)
        left = sorted(p.name for p in icons.iterdir())
        wanted = (
            ["Datakrit.lnk", "Update Datakrit.lnk"]
            if sys.platform == "win32"
            else ["datakrit-update.desktop", "datakrit.desktop"]
        )
        if left != wanted or out.count("removed: ") != 2 or out.count("created: ") != 2:
            sys.exit(f"the old shortcuts were not replaced: {left}\n{out}")
        print("ok: the old shortcuts were replaced by Datakrit's")
    refused = subprocess.run(
        [str(cli), "update", "--version", "1.2.0"],
        cwd=work,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    if refused.returncode != 2 or "2.0.0 or newer" not in refused.stderr:
        sys.exit(f"update --version 1.2.0 was not refused:\n{refused.stdout}{refused.stderr}")
    print("ok: update --version 1.2.0 is refused")


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("dist", nargs="?", default=str(ROOT / "dist"))
    parser.add_argument("--work-dir", help="make the temporary directory inside this folder")
    options = parser.parse_args()
    dist = Path(options.dist)
    wheels = sorted(dist.glob("datakrit-*.whl"))
    if len(wheels) != 1:
        sys.exit(f"expected exactly one datakrit wheel in {dist}, found {len(wheels)}")
    check_ui_assets(wheels[0], dist)
    if options.work_dir:
        Path(options.work_dir).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="datakrit-smoke-", dir=options.work_dir) as tmp:
        tmp_path = Path(tmp)
        env_dir = tmp_path / "venv"
        venv.EnvBuilder(with_pip=True).create(env_dir)
        bin_dir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
        python = bin_dir / ("python.exe" if sys.platform == "win32" else "python")
        cli = bin_dir / ("datakrit.exe" if sys.platform == "win32" else "datakrit")
        run([str(python), "-m", "pip", "install", "-q", str(wheels[0].resolve())], tmp_path, 0)

        work = tmp_path / "work"
        shutil.copytree(
            ROOT / "examples", work / "examples", ignore=shutil.ignore_patterns("__pycache__")
        )
        where = run([str(python), "-I", "-c", "import datakrit; print(datakrit.__file__)"], work, 0)
        if not Path(where.strip()).resolve().is_relative_to(env_dir.resolve()):
            sys.exit(f"datakrit was imported from {where.strip()}, not from the fresh environment")

        source = work / "examples" / "transactions_fixable.csv"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        profile = "examples/profiles/transactions-id.toml"
        run([str(cli), "--version"], work, 0)
        run([str(cli), "--help"], work, 0)
        run([str(python), "-I", "-m", "datakrit", "--version"], work, 0)
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
        gui = bin_dir / ("datakrit-ui.exe" if sys.platform == "win32" else "datakrit-ui")
        if not gui.exists():
            sys.exit(f"the datakrit-ui program is missing from {bin_dir}")
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
        check_migration(python, cli, work)
    print(f"smoke test passed for {wheels[0].name}")


if __name__ == "__main__":
    main()
