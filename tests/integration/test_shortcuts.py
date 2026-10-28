"""`csv-tidy shortcut install|remove`: icons that start the interface or run the update,
without touching shortcuts that belong to other programs."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import run_cli

from csv_tidy import shortcuts
from csv_tidy.errors import CsvTidyError

UI = Path("/opt/csv tidy/bin/csv-tidy-ui")
PY = Path("/opt/csv tidy/bin/python")


def statuses(outcomes):
    return sorted((Path(o.path).name, o.status) for o in outcomes)


def test_linux_entries_are_created_updated_and_removed(tmp_path):
    made = shortcuts.install(folder=tmp_path, platform="linux", ui=UI, python=PY)
    assert statuses(made) == [
        ("csv-tidy-update.desktop", "created"),
        ("csv-tidy.desktop", "created"),
    ]
    main = (tmp_path / "csv-tidy.desktop").read_text(encoding="utf-8")
    assert 'Exec="/opt/csv tidy/bin/csv-tidy-ui"' in main and "Terminal=false" in main
    assert "X-CSV-Tidy=1" in main and "Name=CSV Tidy" in main
    upd = (tmp_path / "csv-tidy-update.desktop").read_text(encoding="utf-8")
    assert 'Exec="/opt/csv tidy/bin/python" -m csv_tidy update --pause' in upd
    assert "Terminal=true" in upd
    again = shortcuts.install(folder=tmp_path, platform="linux", ui=UI, python=PY)
    assert {o.status for o in again} == {"updated"}
    gone = shortcuts.remove(folder=tmp_path, platform="linux")
    assert {o.status for o in gone} == {"removed"} and list(tmp_path.iterdir()) == []
    assert {o.status for o in shortcuts.remove(folder=tmp_path, platform="linux")} == {"absent"}


def test_entries_of_other_programs_are_never_touched(tmp_path):
    foreign = tmp_path / "csv-tidy.desktop"
    foreign.write_text("[Desktop Entry]\nName=Someone else\nExec=other\n", encoding="utf-8")
    made = shortcuts.install(folder=tmp_path, platform="linux", ui=UI, python=PY)
    assert ("csv-tidy.desktop", "skipped") in statuses(made)
    assert foreign.read_text(encoding="utf-8").startswith("[Desktop Entry]\nName=Someone else")
    removed = shortcuts.remove(folder=tmp_path, platform="linux")
    assert ("csv-tidy.desktop", "skipped") in statuses(removed)
    assert foreign.exists()


def test_linux_default_places_are_the_menu_and_an_existing_desktop(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("XDG_DESKTOP_DIR", raising=False)
    (tmp_path / "Desktop").mkdir()
    made = shortcuts.install(platform="linux", ui=UI, python=PY)
    paths = sorted(Path(o.path).relative_to(tmp_path).as_posix() for o in made)
    assert paths == [
        "Desktop/csv-tidy.desktop",
        "data/applications/csv-tidy-update.desktop",
        "data/applications/csv-tidy.desktop",
    ]
    no_desktop = shortcuts.install(platform="linux", ui=UI, python=PY, desktop=False)
    assert all("Desktop" not in o.path for o in no_desktop)


def test_macos_is_not_supported_yet():
    with pytest.raises(CsvTidyError, match="csv-tidy-ui"):
        shortcuts.install(platform="darwin", ui=UI, python=PY)


def test_the_interface_program_is_installed_without_a_console():
    program = shortcuts.ui_program()
    assert program.exists() and program.stem == "csv-tidy-ui"
    entry = [
        line
        for line in Path(shortcuts.__file__)
        .parent.parent.joinpath("..", "pyproject.toml")
        .resolve()
        .read_text(encoding="utf-8")
        .splitlines()
        if line.startswith("csv-tidy-ui")
    ]
    assert entry == ['csv-tidy-ui = "csv_tidy.ui:gui_main"']


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shortcuts (.lnk) need Windows")
def test_windows_shortcuts_point_to_the_programs(tmp_path):
    ui = Path(sys.executable).with_name("csv-tidy-ui.exe")
    made = shortcuts.install(folder=tmp_path, platform="win32", ui=ui, python=Path(sys.executable))
    assert statuses(made) == [("CSV Tidy.lnk", "created"), ("Update CSV Tidy.lnk", "created")]
    script = (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$a = $s.CreateShortcut('{tmp_path / 'CSV Tidy.lnk'}'); "
        f"$b = $s.CreateShortcut('{tmp_path / 'Update CSV Tidy.lnk'}'); "
        "@{ui=$a.TargetPath; update=$b.TargetPath; args=$b.Arguments} | ConvertTo-Json"
    )
    read = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(read.stdout)
    assert Path(data["ui"]) == ui and Path(data["update"]) == Path(sys.executable)
    assert data["args"] == "-m csv_tidy update --pause"
    foreign = (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$f = $s.CreateShortcut('{tmp_path / 'other' / 'CSV Tidy.lnk'}'); "
        "$f.TargetPath = 'C:\\Windows\\notepad.exe'; $f.Save()"
    )
    (tmp_path / "other").mkdir()
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", foreign], check=True)
    skipped = shortcuts.install(folder=tmp_path / "other", platform="win32", ui=ui, python=ui)
    assert ("CSV Tidy.lnk", "skipped") in statuses(skipped)
    assert {o.status for o in shortcuts.remove(folder=tmp_path, platform="win32")} == {"removed"}
    assert not (tmp_path / "CSV Tidy.lnk").exists()


MADE_HERE = pytest.mark.skipif(
    sys.platform == "darwin", reason="shortcuts are made on Windows and Linux; macOS refuses"
)


@MADE_HERE
def test_cli_reports_each_shortcut(tmp_path):
    result = run_cli("shortcut", "install", "--folder", str(tmp_path))
    assert result.code == 0, result.err
    assert result.out.count("created: ") == 2 and "CSV Tidy" in result.out
    removed = run_cli("shortcut", "remove", "--folder", str(tmp_path))
    assert removed.code == 0 and removed.out.count("removed: ") == 2


@pytest.mark.skipif(sys.platform != "darwin", reason="the macOS refusal")
def test_cli_refuses_shortcuts_on_macos_and_writes_nothing(tmp_path):
    folder = tmp_path / "icons"
    result = run_cli("shortcut", "install", "--folder", str(folder))
    assert result.code == 2 and "csv-tidy-ui program" in result.err
    assert not folder.exists()


@MADE_HERE
def test_cli_explains_a_missing_interface_program(tmp_path, monkeypatch):
    def missing():
        raise CsvTidyError("the csv-tidy-ui program was not found next to this Python")

    monkeypatch.setattr(shortcuts, "ui_program", missing)
    result = run_cli("shortcut", "install", "--folder", str(tmp_path))
    assert result.code == 2 and "csv-tidy-ui program was not found" in result.err
    assert list(tmp_path.iterdir()) == []
