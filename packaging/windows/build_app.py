"""Build the Datakrit Windows app and its zip file.

Run from the repository root, in a build environment made as described in CONTRIBUTING.md
("Building the Windows app"):

    python packaging/windows/build_app.py [--dist dist-exe] [--work build/pyinstaller]

It writes, in the ``--dist`` folder (``dist-exe`` by default, never committed):

- ``Datakrit/``: the one-folder build, ``Datakrit.exe`` with its files;
- ``Datakrit-<version>-windows-x64.zip``: that folder, as ``Datakrit\\...``;
- ``Datakrit-<version>-windows-x64.zip.sha256``: ``<hash>  <zip name>``, the format that
  ``sha256sum --check`` reads.

It prints the version, the zip's name, size, and SHA-256 as ``key=value`` lines, and also
appends them to the file named by ``GITHUB_OUTPUT`` when GitHub Actions sets it.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from importlib.metadata import version as installed_version
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = HERE / "datakrit.spec"
ZIP = "Datakrit-{version}-windows-x64.zip"


def source_version() -> str:
    text = (ROOT / "src" / "datakrit" / "__init__.py").read_text(encoding="utf-8")
    found = re.search(r'^__version__ = "(\d+\.\d+\.\d+)"$', text, re.M)
    if found is None:
        raise SystemExit("src/datakrit/__init__.py has no __version__ such as 2.1.0")
    return found.group(1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def make_zip(folder: Path, target: Path) -> None:
    """Zip ``folder`` so that every entry starts with its name (``Datakrit/...``)."""
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, f"{folder.name}/{path.relative_to(folder).as_posix()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Datakrit Windows app and its zip.")
    parser.add_argument("--dist", type=Path, default=ROOT / "dist-exe")
    parser.add_argument("--work", type=Path, default=ROOT / "build" / "pyinstaller")
    args = parser.parse_args(argv)
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        raise SystemExit("the Windows app is built on 64-bit Windows with a 64-bit Python")
    version = source_version()
    if installed_version("datakrit") != version:
        raise SystemExit(
            f"this environment has datakrit {installed_version('datakrit')}, not {version}; "
            "run `python -m pip install --no-deps .` from the repository root first"
        )
    dist, work = args.dist.resolve(), args.work.resolve()
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean"]
    command += ["--distpath", str(dist), "--workpath", str(work), str(SPEC)]
    subprocess.run(command, check=True)

    folder = dist / "Datakrit"
    program = folder / "Datakrit.exe"
    pages = list(folder.rglob("datakrit/ui_static/index.html"))
    if not program.is_file() or len(pages) != 1:
        raise SystemExit(f"the build in {folder} lacks Datakrit.exe or the interface files")
    target = dist / ZIP.format(version=version)
    target.unlink(missing_ok=True)
    make_zip(folder, target)
    digest = sha256(target)
    Path(f"{target}.sha256").write_text(f"{digest}  {target.name}\n", encoding="ascii")

    result = {
        "version": version,
        "zip": target.name,
        "zip_path": str(target),
        "bytes": str(target.stat().st_size),
        "sha256": digest,
    }
    lines = [f"{key}={value}" for key, value in result.items()]
    print("\n".join(lines))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write("\n".join(lines) + "\n")
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
