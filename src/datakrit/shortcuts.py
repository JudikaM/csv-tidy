"""Shortcuts that start the local interface or run the update, without a command line.

Windows: "Datakrit" on the Desktop and in the Start Menu, and "Update Datakrit" in the Start
Menu (``.lnk`` files written through the Windows Script Host). Linux: desktop entries in the
applications menu (and "Datakrit" on the Desktop when that folder exists). A file with one of
these names that was not made by Datakrit is never changed or removed. Functions here never
print; the CLI reports the outcomes.

Migration: Datakrit was called CSV Tidy until 1.2.0, and that version made the shortcuts
"CSV Tidy" and "Update CSV Tidy". ``install`` and ``remove`` also remove those, in the places
where CSV Tidy put them, when they start ``csv-tidy-ui`` or run ``-m csv_tidy``; files with
those names that belong to another program are kept. CSV Tidy 1.2.0's update switches an
installation by running ``python -m datakrit shortcut install [--no-desktop]``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
from dataclasses import dataclass, replace
from pathlib import Path

from .errors import DatakritError

MARKER = "X-Datakrit=1"


@dataclass(frozen=True)
class Owner:
    """How a shortcut is recognized as made by a program: the program it starts, or the
    module that its Python runs, and on Linux the marker line in the desktop entry."""

    program: str
    module: str
    marker: str


OWNER = Owner("datakrit-ui", "-m datakrit", MARKER)
# Migration: the shortcuts that CSV Tidy (1.2.0 and earlier) made.
LEGACY_OWNER = Owner("csv-tidy-ui", "-m csv_tidy", "X-CSV-Tidy=1")


@dataclass(frozen=True)
class Shortcut:
    name: str
    target: Path
    arguments: str
    description: str
    place: str  # "desktop" or "menu"
    console: bool
    # Linux file name; Windows uses NAME.lnk.
    entry: str = ""
    # A legacy shortcut is only ever removed.
    legacy: bool = False

    @property
    def owner(self) -> Owner:
        return LEGACY_OWNER if self.legacy else OWNER


@dataclass(frozen=True)
class Outcome:
    path: str
    # created, updated, removed, absent, or skipped (belongs to another program)
    status: str


def ui_program() -> Path:
    """The ``datakrit-ui`` program that pip installed next to this Python."""
    name = "datakrit-ui.exe" if sys.platform == "win32" else "datakrit-ui"
    for folder in (Path(sysconfig.get_path("scripts")), Path(sys.executable).parent):
        if (folder / name).exists():
            return folder / name
    raise DatakritError(
        "the datakrit-ui program was not found next to this Python; reinstall Datakrit with "
        "pip, then run this command again"
    )


def console_python() -> Path:
    """A Python that opens a console window (the update shows pip's progress)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        return exe.with_name("python.exe")
    return exe


def planned(ui: Path, python: Path, desktop: bool = True) -> list[Shortcut]:
    start = Shortcut(
        "Datakrit",
        ui,
        "",
        "Check and clean table files on this computer",
        "menu",
        False,
        "datakrit.desktop",
    )
    items = [start]
    if desktop:
        items.insert(0, replace(start, place="desktop"))
    items.append(
        Shortcut(
            "Update Datakrit",
            python,
            "-m datakrit update --pause",
            "Install the latest Datakrit release from GitHub",
            "menu",
            True,
            "datakrit-update.desktop",
        )
    )
    return items


def legacy() -> list[Shortcut]:
    """Migration: the shortcuts that CSV Tidy made, where it made them (also on the Desktop
    when ``--no-desktop`` is given now, since their program is gone after the switch)."""
    placeholder = Path("csv-tidy")
    start = Shortcut("CSV Tidy", placeholder, "", "", "desktop", False, "csv-tidy.desktop", True)
    update = Shortcut(
        "Update CSV Tidy", placeholder, "", "", "menu", True, "csv-tidy-update.desktop", True
    )
    return [start, replace(start, place="menu"), update]


def _refuse_in_app() -> None:
    """The Windows app (a frozen program) is a folder that the user unzipped; the shortcuts
    point to programs that pip installs, so they are not offered there."""
    if getattr(sys, "frozen", False):
        raise DatakritError(
            "shortcuts are not offered in the Datakrit Windows app; to start it from the Start "
            "Menu, right-click Datakrit.exe and choose Pin to Start"
        )


def install(
    folder: str | Path | None = None,
    desktop: bool = True,
    platform: str = sys.platform,
    ui: Path | None = None,
    python: Path | None = None,
) -> list[Outcome]:
    """Create or refresh the shortcuts, and remove CSV Tidy's. With ``folder`` every
    shortcut goes there (and only CSV Tidy's shortcuts in that folder are removed). Refused
    in the Windows app."""
    _refuse_in_app()
    _supported(platform)
    items = planned(ui or ui_program(), python or console_python(), desktop)
    return _apply("install", items, folder, platform)


def remove(folder: str | Path | None = None, platform: str = sys.platform) -> list[Outcome]:
    """Remove the shortcuts that Datakrit (or CSV Tidy) made; others with the same name are
    kept."""
    _supported(platform)
    placeholder = Path("datakrit")
    items = planned(placeholder, placeholder, desktop=folder is None)
    return _apply("remove", items, folder, platform)


def _apply(
    action: str, items: list[Shortcut], folder: str | Path | None, platform: str
) -> list[Outcome]:
    old = legacy()
    if folder is not None:
        items = [item for item in items if item.place != "desktop"]
        old = [item for item in old if item.place != "desktop"]
    every = [*items, *old]
    if platform == "win32":
        outcomes = _windows(action, every, folder)
    else:
        outcomes = [
            _remove_entry(path, item.owner)
            if item.legacy or action == "remove"
            else _write_entry(item, path)
            for item, path in _linux_places(every, folder)
        ]
    # Old shortcuts are reported only when one was actually removed.
    done = []
    for outcome, item in zip(outcomes, _placed(every, folder, platform), strict=True):
        if not item.legacy or outcome.status == "removed":
            done.append(outcome)
    return done


def _placed(items: list[Shortcut], folder: str | Path | None, platform: str) -> list[Shortcut]:
    """The items in the order of their outcomes (Linux skips a missing Desktop folder)."""
    if platform == "win32":
        return items
    return [item for item, _ in _linux_places(items, folder)]


def _supported(platform: str) -> None:
    if platform != "win32" and not platform.startswith("linux"):
        raise DatakritError(
            "shortcuts are made on Windows and Linux; on this system start the interface "
            "with the datakrit-ui program (or datakrit ui)"
        )


# --------------------------------------------------------------------------- Linux


def _linux_places(items: list[Shortcut], folder: str | Path | None) -> list[tuple[Shortcut, Path]]:
    if folder is not None:
        base = Path(folder)
        return [(item, base / item.entry) for item in items]
    home = Path(os.environ.get("HOME") or Path.home())
    menu = Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share") / "applications"
    desktop = Path(os.environ.get("XDG_DESKTOP_DIR") or home / "Desktop")
    places = []
    for item in items:
        if item.place == "desktop":
            if desktop.is_dir():
                places.append((item, desktop / item.entry))
        else:
            places.append((item, menu / item.entry))
    return places


def _quote(value: str) -> str:
    """Quote one Exec argument as the Desktop Entry specification requires."""
    escaped = "".join("\\" + ch if ch in '"`$\\' else ch for ch in value)
    return f'"{escaped}"'


def _ours(path: Path, owner: Owner = OWNER) -> bool:
    """A desktop entry is ours when it has our marker line and starts our program or
    module."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    starts = any(
        line.startswith("Exec=") and (owner.program in line or owner.module in line)
        for line in lines
    )
    return owner.marker in lines and starts


def _write_entry(item: Shortcut, path: Path) -> Outcome:
    existed = path.exists()
    if existed and not _ours(path):
        return Outcome(str(path), "skipped")
    command = " ".join([_quote(item.target.as_posix()), *item.arguments.split()])
    text = "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={item.name}",
            f"Comment={item.description}",
            f"Exec={command}",
            f"Terminal={'true' if item.console else 'false'}",
            "Categories=Office;Utility;",
            MARKER,
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return Outcome(str(path), "updated" if existed else "created")


def _remove_entry(path: Path, owner: Owner = OWNER) -> Outcome:
    if not path.exists():
        return Outcome(str(path), "absent")
    if not _ours(path, owner):
        return Outcome(str(path), "skipped")
    path.unlink()
    return Outcome(str(path), "removed")


# --------------------------------------------------------------------------- Windows

# The shortcut data is passed as JSON in an environment variable, so no value is ever
# pasted into the script text. A shortcut counts as made by its owner when it starts the
# owner's program or runs its module ("-m datakrit"; for CSV Tidy's: csv-tidy-ui or
# "-m csv_tidy"). CSV Tidy's shortcuts are only ever removed.
_WINDOWS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$request = $env:DATAKRIT_SHORTCUTS | ConvertFrom-Json
$shell = New-Object -ComObject WScript.Shell
$results = @()
foreach ($item in $request.items) {
    $dir = $request.folder
    if (-not $dir) { $dir = $shell.SpecialFolders($item.special) }
    $path = Join-Path $dir ($item.name + '.lnk')
    $exists = Test-Path -LiteralPath $path
    $ours = $false
    if ($exists) {
        $old = $shell.CreateShortcut($path)
        $ours = ($old.TargetPath -like ('*' + $item.program + '*')) -or
                ($old.Arguments -like ('*' + $item.module + '*'))
    }
    $action = $request.action
    if ($item.legacy) { $action = 'remove' }
    if ($action -eq 'remove') {
        if (-not $exists) { $status = 'absent' }
        elseif (-not $ours) { $status = 'skipped' }
        else { Remove-Item -LiteralPath $path; $status = 'removed' }
    } else {
        if ($exists -and -not $ours) { $status = 'skipped' }
        else {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
            $link = $shell.CreateShortcut($path)
            $link.TargetPath = $item.target
            $link.Arguments = $item.arguments
            $link.Description = $item.description
            $link.WorkingDirectory = $request.workdir
            $link.Save()
            if ($exists) { $status = 'updated' } else { $status = 'created' }
        }
    }
    $results += [pscustomobject]@{ path = $path; status = $status }
}
ConvertTo-Json -InputObject @($results) -Compress
"""


def _windows(action: str, items: list[Shortcut], folder: str | Path | None) -> list[Outcome]:
    request = {
        "action": action,
        "folder": str(Path(folder).resolve()) if folder is not None else None,
        "workdir": str(Path.home()),
        "items": [
            {
                "name": item.name,
                "target": str(item.target),
                "arguments": item.arguments,
                "description": item.description,
                "special": "Desktop" if item.place == "desktop" else "Programs",
                "program": item.owner.program,
                "module": item.owner.module,
                "legacy": item.legacy,
            }
            for item in items
        ],
    }
    env = {**os.environ, "DATAKRIT_SHORTCUTS": json.dumps(request)}
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _WINDOWS_SCRIPT],
            capture_output=True,
            env=env,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DatakritError(f"could not run Windows PowerShell to make shortcuts: {exc}") from None
    output = proc.stdout.decode("utf-8", "replace").strip()
    if proc.returncode != 0 or not output:
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise DatakritError(
            "Windows could not make the shortcuts"
            + (f": {detail[0]}" if detail else "")
            + ". Nothing else was changed."
        )
    return [Outcome(entry["path"], entry["status"]) for entry in json.loads(output)]
