"""Shortcuts that start the local interface or run the update, without a command line.

Windows: "CSV Tidy" on the Desktop and in the Start Menu, and "Update CSV Tidy" in the Start
Menu (``.lnk`` files written through the Windows Script Host). Linux: desktop entries in the
applications menu (and "CSV Tidy" on the Desktop when that folder exists). A file with one of
these names that was not made by CSV Tidy is never changed or removed. Functions here never
print; the CLI reports the outcomes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path

from .errors import CsvTidyError

MARKER = "X-CSV-Tidy=1"


@dataclass(frozen=True)
class Shortcut:
    name: str
    target: Path
    arguments: str
    description: str
    place: str  # "desktop" or "menu"
    console: bool


@dataclass(frozen=True)
class Outcome:
    path: str
    status: str  # created, updated, removed, absent, or skipped (belongs to another program)


def ui_program() -> Path:
    """The ``csv-tidy-ui`` program that pip installed next to this Python."""
    name = "csv-tidy-ui.exe" if sys.platform == "win32" else "csv-tidy-ui"
    for folder in (Path(sysconfig.get_path("scripts")), Path(sys.executable).parent):
        if (folder / name).exists():
            return folder / name
    raise CsvTidyError(
        "the csv-tidy-ui program was not found next to this Python; reinstall CSV Tidy 0.4.0 "
        "or newer with pip, then run this command again"
    )


def console_python() -> Path:
    """A Python that opens a console window (the update shows pip's progress)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        return exe.with_name("python.exe")
    return exe


def planned(ui: Path, python: Path, desktop: bool = True) -> list[Shortcut]:
    start = Shortcut(
        "CSV Tidy", ui, "", "Check and clean CSV files on this computer", "menu", False
    )
    items = [start]
    if desktop:
        items.insert(0, Shortcut(start.name, ui, "", start.description, "desktop", False))
    items.append(
        Shortcut(
            "Update CSV Tidy",
            python,
            "-m csv_tidy update --pause",
            "Install the latest CSV Tidy release from GitHub",
            "menu",
            True,
        )
    )
    return items


def install(
    folder: str | Path | None = None,
    desktop: bool = True,
    platform: str = sys.platform,
    ui: Path | None = None,
    python: Path | None = None,
) -> list[Outcome]:
    """Create or refresh the shortcuts. With ``folder`` every shortcut goes there."""
    _supported(platform)
    items = planned(ui or ui_program(), python or console_python(), desktop)
    if folder is not None:
        items = [item for item in items if item.place != "desktop"]
    if platform == "win32":
        return _windows("install", items, folder)
    return [_write_entry(item, path) for item, path in _linux_places(items, folder)]


def remove(folder: str | Path | None = None, platform: str = sys.platform) -> list[Outcome]:
    """Remove the shortcuts that CSV Tidy made; others with the same name are kept."""
    _supported(platform)
    placeholder = Path("csv-tidy")
    items = planned(placeholder, placeholder, desktop=folder is None)
    if folder is not None:
        items = [item for item in items if item.place != "desktop"]
    if platform == "win32":
        return _windows("remove", items, folder)
    return [_remove_entry(path) for _, path in _linux_places(items, folder)]


def _supported(platform: str) -> None:
    if platform != "win32" and not platform.startswith("linux"):
        raise CsvTidyError(
            "shortcuts are made on Windows and Linux; on this system start the interface "
            "with the csv-tidy-ui program (or csv-tidy ui)"
        )


# --------------------------------------------------------------------------- Linux


def _linux_places(items: list[Shortcut], folder: str | Path | None) -> list[tuple[Shortcut, Path]]:
    if folder is not None:
        base = Path(folder)
        return [(item, base / _entry_name(item)) for item in items]
    home = Path(os.environ.get("HOME") or Path.home())
    menu = Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share") / "applications"
    desktop = Path(os.environ.get("XDG_DESKTOP_DIR") or home / "Desktop")
    places = []
    for item in items:
        if item.place == "desktop":
            if desktop.is_dir():
                places.append((item, desktop / _entry_name(item)))
        else:
            places.append((item, menu / _entry_name(item)))
    return places


def _entry_name(item: Shortcut) -> str:
    return "csv-tidy-update.desktop" if item.console else "csv-tidy.desktop"


def _quote(value: str) -> str:
    """Quote one Exec argument as the Desktop Entry specification requires."""
    escaped = "".join("\\" + ch if ch in '"`$\\' else ch for ch in value)
    return f'"{escaped}"'


def _ours(path: Path) -> bool:
    try:
        return MARKER in path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False


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


def _remove_entry(path: Path) -> Outcome:
    if not path.exists():
        return Outcome(str(path), "absent")
    if not _ours(path):
        return Outcome(str(path), "skipped")
    path.unlink()
    return Outcome(str(path), "removed")


# --------------------------------------------------------------------------- Windows

# The shortcut data is passed as JSON in an environment variable, so no value is ever
# pasted into the script text. A shortcut counts as CSV Tidy's when it starts csv-tidy-ui or
# runs "-m csv_tidy".
_WINDOWS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$request = $env:CSV_TIDY_SHORTCUTS | ConvertFrom-Json
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
        $ours = ($old.TargetPath -like '*csv-tidy-ui*') -or ($old.Arguments -like '*-m csv_tidy*')
    }
    if ($request.action -eq 'remove') {
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
            }
            for item in items
        ],
    }
    env = {**os.environ, "CSV_TIDY_SHORTCUTS": json.dumps(request)}
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _WINDOWS_SCRIPT],
            capture_output=True,
            env=env,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CsvTidyError(f"could not run Windows PowerShell to make shortcuts: {exc}") from None
    output = proc.stdout.decode("utf-8", "replace").strip()
    if proc.returncode != 0 or not output:
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise CsvTidyError(
            "Windows could not make the shortcuts"
            + (f": {detail[0]}" if detail else "")
            + ". Nothing else was changed."
        )
    return [Outcome(entry["path"], entry["status"]) for entry in json.loads(output)]
