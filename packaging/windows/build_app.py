"""Build the Datakrit Windows app and its zip file.

Run from the repository root, in a build environment made as described in CONTRIBUTING.md
("Building the Windows app"):

    python packaging/windows/build_app.py [--dist dist-exe] [--work build/pyinstaller]

It writes, in the ``--dist`` folder (``dist-exe`` by default, never committed):

- ``Datakrit/``: the one-folder build, ``Datakrit.exe`` with its files, and
  ``Datakrit/licenses/`` with the license notices of Datakrit and of what the app bundles
  (see ``LICENSE_FILES``);
- ``Datakrit-<version>-windows-x64.zip``: that folder, as ``Datakrit\\...``;
- ``Datakrit-<version>-windows-x64.zip.sha256``: one line ``<hash>  <zip name>`` ending in
  LF (not CRLF), the format that ``sha256sum --check`` and ``shasum -a 256 --check`` read.

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
from importlib.metadata import distribution
from importlib.metadata import version as installed_version
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = HERE / "datakrit.spec"
ZIP = "Datakrit-{version}-windows-x64.zip"
LICENSES = "licenses"
# The notices in Datakrit/licenses/, in this order:
# - LICENSE: Datakrit's MIT License;
# - NOTICE.md: the notices of the interface's icons (Lucide, ISC; Feather, MIT);
# - Python-LICENSE.txt: LICENSE.txt of the Python that the app bundles. The Windows build of
#   Python ships it with the PSF License, the licenses of the libraries it bundles (OpenSSL,
#   libffi, bzip2, and others), and the conditions for the Microsoft Distributable Code;
# - tomli-w-LICENSE.txt: the MIT License of tomli-w, Datakrit's runtime dependency;
# - Microsoft-runtime-NOTICE.txt: the Microsoft runtime files in the app, with those
#   conditions quoted from Python-LICENSE.txt.
LICENSE_FILES = (
    "LICENSE",
    "NOTICE.md",
    "Python-LICENSE.txt",
    "tomli-w-LICENSE.txt",
    "Microsoft-runtime-NOTICE.txt",
)
# Microsoft Visual C++ runtime and Universal C Runtime files.
MICROSOFT_DLL = re.compile(
    r"(vcruntime\d+(_\d+)?|msvcp\d+(_\w+)?|concrt\d+|ucrtbase|api-ms-win-[\w.-]+)\.dll",
    re.IGNORECASE,
)
MICROSOFT_START = "Additional Conditions for this Windows binary build"
MICROSOFT_END = "or by other licenses as marked."


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


def microsoft_conditions(python_license: str) -> str:
    """The section of Python's LICENSE.txt about the Microsoft Distributable Code."""
    start = python_license.find(MICROSOFT_START)
    end = python_license.find(MICROSOFT_END, start)
    if start < 0 or end < 0:
        raise SystemExit(
            "the Python license has no section about the Microsoft Distributable Code; "
            "build with a Windows build of Python from python.org"
        )
    return python_license[start : end + len(MICROSOFT_END)].replace("\r\n", "\n")


def microsoft_notice(folder: Path, python_license: str) -> str:
    """The Microsoft runtime files in ``folder``, and the conditions that apply to them."""
    files = sorted(
        path.relative_to(folder).as_posix()
        for path in folder.rglob("*.dll")
        if MICROSOFT_DLL.fullmatch(path.name)
    )
    if not files:
        raise SystemExit(f"no Microsoft runtime files found in {folder}")
    listed = "\n".join(f"  {name}" for name in files)
    return (
        "Microsoft runtime files in the Datakrit Windows app\n"
        "===================================================\n\n"
        "The app bundles these files of the Microsoft Visual C++ runtime and the Universal C\n"
        "Runtime, copied with the Windows build of Python that the app contains:\n\n"
        f"{listed}\n\n"
        "They are Microsoft Distributable Code, copyrighted by Microsoft Corporation, and are\n"
        "redistributed as part of that Python. The conditions for their redistribution, quoted\n"
        "from Python's LICENSE.txt (in full in Python-LICENSE.txt next to this file):\n\n"
        f"{microsoft_conditions(python_license)}\n"
    )


def tomli_w_license() -> str:
    """The license file of the installed tomli-w (Datakrit's runtime dependency)."""
    files = [f for f in distribution("tomli_w").files or () if f.name.upper().startswith("LICENSE")]
    if len(files) != 1:
        raise SystemExit(f"expected one license file of tomli-w, found {files}")
    return files[0].read_text(encoding="utf-8")


def add_licenses(folder: Path, python_license_file: Path) -> list[Path]:
    """Write ``folder/licenses/`` (see ``LICENSE_FILES``) and return the files written."""
    if not python_license_file.is_file():
        raise SystemExit(f"{python_license_file} is missing; the app cannot ship without it")
    python_license = python_license_file.read_text(encoding="utf-8")
    texts = {
        "LICENSE": (ROOT / "LICENSE").read_text(encoding="utf-8"),
        "NOTICE.md": (ROOT / "NOTICE.md").read_text(encoding="utf-8"),
        "Python-LICENSE.txt": python_license,
        "tomli-w-LICENSE.txt": tomli_w_license(),
        "Microsoft-runtime-NOTICE.txt": microsoft_notice(folder, python_license),
    }
    target = folder / LICENSES
    target.mkdir(exist_ok=True)
    written = []
    for name in LICENSE_FILES:
        path = target / name
        path.write_text(texts[name], encoding="utf-8")
        written.append(path)
    return written


def sha256_line(target: Path, digest: str) -> bytes:
    """The checksum file's content. Written as bytes, so that Windows adds no CR: with CRLF,
    coreutils 8 ``sha256sum --check`` and ``shasum --check`` look for a file name with a CR."""
    return f"{digest}  {target.name}\n".encode("ascii")


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
    add_licenses(folder, Path(sys.base_prefix) / "LICENSE.txt")
    target = dist / ZIP.format(version=version)
    target.unlink(missing_ok=True)
    make_zip(folder, target)
    digest = sha256(target)
    Path(f"{target}.sha256").write_bytes(sha256_line(target, digest))

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
