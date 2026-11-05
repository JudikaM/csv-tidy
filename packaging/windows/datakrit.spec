# PyInstaller spec of the Datakrit Windows app: a one-folder build, Datakrit\Datakrit.exe
# with its files, and no console window. Build it with packaging/windows/build_app.py, which
# also makes the zip; see CONTRIBUTING.md ("Building the Windows app").
#
# The app bundles the datakrit package installed in the build environment
# (`python -m pip install --no-deps .`), so the build refuses to run when that package is not
# the version in src/datakrit/__init__.py.

import re
from importlib.metadata import version as installed_version
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

HERE = Path(SPECPATH)  # noqa: F821 (set by PyInstaller)
ROOT = HERE.parents[1]

source = (ROOT / "src" / "datakrit" / "__init__.py").read_text(encoding="utf-8")
VERSION = re.search(r'^__version__ = "(\d+)\.(\d+)\.(\d+)"$', source, re.M)
if VERSION is None:
    raise SystemExit("src/datakrit/__init__.py has no __version__ such as 2.1.0")
TEXT_VERSION = ".".join(VERSION.groups())
if installed_version("datakrit") != TEXT_VERSION:
    raise SystemExit(
        f"the build environment has datakrit {installed_version('datakrit')}, not "
        f"{TEXT_VERSION}; run `python -m pip install --no-deps .` from the repository root"
    )
NUMBERS = (*(int(part) for part in VERSION.groups()), 0)

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=NUMBERS, prodvers=NUMBERS),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",  # U.S. English, Unicode
                    [
                        StringStruct("FileDescription", "Datakrit local interface"),
                        StringStruct("FileVersion", TEXT_VERSION),
                        StringStruct("InternalName", "Datakrit"),
                        StringStruct(
                            "LegalCopyright", "Copyright (c) 2026 Judika Marpaung (MIT License)"
                        ),
                        StringStruct("OriginalFilename", "Datakrit.exe"),
                        StringStruct("ProductName", "Datakrit"),
                        StringStruct("ProductVersion", TEXT_VERSION),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
    ],
)

a = Analysis(  # noqa: F821
    [str(HERE / "launcher.py")],
    # The page and its files (index.html, app.css, theme.js, app.js, logo-mark.png).
    datas=collect_data_files("datakrit", includes=["ui_static/*"]),
    # Every module of the package, also those that the interface does not import.
    hiddenimports=collect_submodules("datakrit"),
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Datakrit",
    console=False,
    icon=str(HERE / "datakrit.ico"),
    version=version_info,
    upx=False,
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="Datakrit",
    upx=False,
)
