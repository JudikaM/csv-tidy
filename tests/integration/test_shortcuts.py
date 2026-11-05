"""`datakrit shortcut install|remove`: icons that start the interface or run the update,
without touching shortcuts that belong to other programs."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import run_cli

from datakrit import shortcuts
from datakrit.errors import DatakritError

UI = Path("/opt/datakrit/bin/datakrit-ui")
PY = Path("/opt/datakrit/bin/python")


def statuses(outcomes):
    return sorted((Path(o.path).name, o.status) for o in outcomes)


def test_linux_entries_are_created_updated_and_removed(tmp_path):
    made = shortcuts.install(folder=tmp_path, platform="linux", ui=UI, python=PY)
    assert statuses(made) == [
        ("datakrit-update.desktop", "created"),
        ("datakrit.desktop", "created"),
    ]
    main = (tmp_path / "datakrit.desktop").read_text(encoding="utf-8")
    assert 'Exec="/opt/datakrit/bin/datakrit-ui"' in main and "Terminal=false" in main
    assert "X-Datakrit=1" in main and "Name=Datakrit" in main
    upd = (tmp_path / "datakrit-update.desktop").read_text(encoding="utf-8")
    assert 'Exec="/opt/datakrit/bin/python" -m datakrit update --pause' in upd
    assert "Terminal=true" in upd
    again = shortcuts.install(folder=tmp_path, platform="linux", ui=UI, python=PY)
    assert {o.status for o in again} == {"updated"}
    gone = shortcuts.remove(folder=tmp_path, platform="linux")
    assert {o.status for o in gone} == {"removed"} and list(tmp_path.iterdir()) == []
    assert {o.status for o in shortcuts.remove(folder=tmp_path, platform="linux")} == {"absent"}


def test_entries_of_other_programs_are_never_touched(tmp_path):
    foreign = tmp_path / "datakrit.desktop"
    foreign.write_text("[Desktop Entry]\nName=Someone else\nExec=other\n", encoding="utf-8")
    made = shortcuts.install(folder=tmp_path, platform="linux", ui=UI, python=PY)
    assert ("datakrit.desktop", "skipped") in statuses(made)
    assert foreign.read_text(encoding="utf-8").startswith("[Desktop Entry]\nName=Someone else")
    removed = shortcuts.remove(folder=tmp_path, platform="linux")
    assert ("datakrit.desktop", "skipped") in statuses(removed)
    assert foreign.exists()


def test_linux_default_places_are_the_menu_and_an_existing_desktop(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("XDG_DESKTOP_DIR", raising=False)
    (tmp_path / "Desktop").mkdir()
    made = shortcuts.install(platform="linux", ui=UI, python=PY)
    paths = sorted(Path(o.path).relative_to(tmp_path).as_posix() for o in made)
    assert paths == [
        "Desktop/datakrit.desktop",
        "data/applications/datakrit-update.desktop",
        "data/applications/datakrit.desktop",
    ]
    no_desktop = shortcuts.install(platform="linux", ui=UI, python=PY, desktop=False)
    assert all("Desktop" not in o.path for o in no_desktop)


def test_macos_is_not_supported_yet():
    with pytest.raises(DatakritError, match="datakrit-ui"):
        shortcuts.install(platform="darwin", ui=UI, python=PY)


def test_the_interface_program_is_installed_without_a_console():
    program = shortcuts.ui_program()
    assert program.exists() and program.stem == "datakrit-ui"
    entry = [
        line
        for line in Path(shortcuts.__file__)
        .parent.parent.joinpath("..", "pyproject.toml")
        .resolve()
        .read_text(encoding="utf-8")
        .splitlines()
        if line.startswith("datakrit-ui")
    ]
    assert entry == ['datakrit-ui = "datakrit.ui:gui_main"']


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shortcuts (.lnk) need Windows")
def test_windows_shortcuts_point_to_the_programs(tmp_path):
    ui = Path(sys.executable).with_name("datakrit-ui.exe")
    made = shortcuts.install(folder=tmp_path, platform="win32", ui=ui, python=Path(sys.executable))
    assert statuses(made) == [("Datakrit.lnk", "created"), ("Update Datakrit.lnk", "created")]
    script = (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$a = $s.CreateShortcut('{tmp_path / 'Datakrit.lnk'}'); "
        f"$b = $s.CreateShortcut('{tmp_path / 'Update Datakrit.lnk'}'); "
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
    assert data["args"] == "-m datakrit update --pause"
    foreign = (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$f = $s.CreateShortcut('{tmp_path / 'other' / 'Datakrit.lnk'}'); "
        "$f.TargetPath = 'C:\\Windows\\notepad.exe'; $f.Save()"
    )
    (tmp_path / "other").mkdir()
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", foreign], check=True)
    skipped = shortcuts.install(folder=tmp_path / "other", platform="win32", ui=ui, python=ui)
    assert ("Datakrit.lnk", "skipped") in statuses(skipped)
    assert {o.status for o in shortcuts.remove(folder=tmp_path, platform="win32")} == {"removed"}
    assert not (tmp_path / "Datakrit.lnk").exists()


MADE_HERE = pytest.mark.skipif(
    sys.platform == "darwin", reason="shortcuts are made on Windows and Linux; macOS refuses"
)


@MADE_HERE
def test_cli_reports_each_shortcut(tmp_path):
    result = run_cli("shortcut", "install", "--folder", str(tmp_path))
    assert result.code == 0, result.err
    assert result.out.count("created: ") == 2 and "Datakrit" in result.out
    removed = run_cli("shortcut", "remove", "--folder", str(tmp_path))
    assert removed.code == 0 and removed.out.count("removed: ") == 2


@pytest.mark.skipif(sys.platform != "darwin", reason="the macOS refusal")
def test_cli_refuses_shortcuts_on_macos_and_writes_nothing(tmp_path):
    folder = tmp_path / "icons"
    result = run_cli("shortcut", "install", "--folder", str(folder))
    assert result.code == 2 and "datakrit-ui program" in result.err
    assert not folder.exists()


@MADE_HERE
def test_cli_explains_a_missing_interface_program(tmp_path, monkeypatch):
    def missing():
        raise DatakritError("the datakrit-ui program was not found next to this Python")

    monkeypatch.setattr(shortcuts, "ui_program", missing)
    result = run_cli("shortcut", "install", "--folder", str(tmp_path))
    assert result.code == 2 and "datakrit-ui program was not found" in result.err
    assert list(tmp_path.iterdir()) == []


# ----------------------------------------------------------------------------- migration
# Datakrit was called CSV Tidy until 1.2.0. Its shortcuts ("CSV Tidy", "Update CSV Tidy")
# start csv-tidy-ui or run "-m csv_tidy"; install and remove take them away, and keep files
# with those names that belong to other programs. CSV Tidy 1.2.0's update switches with
# `python -m datakrit shortcut install [--no-desktop]`.

OLD_MAIN = '[Desktop Entry]\nName=CSV Tidy\nExec="/opt/old/bin/csv-tidy-ui"\nX-CSV-Tidy=1\n'
OLD_UPDATE = (
    '[Desktop Entry]\nName=Update CSV Tidy\nExec="/opt/old/bin/python" -m csv_tidy update '
    "--pause\nTerminal=true\nX-CSV-Tidy=1\n"
)


def old_linux_entries(folder):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "csv-tidy.desktop").write_text(OLD_MAIN, encoding="utf-8")
    (folder / "csv-tidy-update.desktop").write_text(OLD_UPDATE, encoding="utf-8")


def test_install_replaces_the_old_linux_entries(tmp_path):
    old_linux_entries(tmp_path)
    made = shortcuts.install(folder=tmp_path, platform="linux", ui=UI, python=PY)
    assert statuses(made) == [
        ("csv-tidy-update.desktop", "removed"),
        ("csv-tidy.desktop", "removed"),
        ("datakrit-update.desktop", "created"),
        ("datakrit.desktop", "created"),
    ]
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "datakrit-update.desktop",
        "datakrit.desktop",
    ]
    # Without old entries nothing about them is reported.
    again = shortcuts.install(folder=tmp_path, platform="linux", ui=UI, python=PY)
    assert statuses(again) == [
        ("datakrit-update.desktop", "updated"),
        ("datakrit.desktop", "updated"),
    ]


@pytest.mark.parametrize(
    "text",
    [
        "[Desktop Entry]\nName=CSV Tidy\nExec=/usr/bin/someone-else\n",
        # The old marker alone is not enough: the entry must also start the old program.
        "[Desktop Entry]\nName=CSV Tidy\nExec=/usr/bin/someone-else\nX-CSV-Tidy=1\n",
        # Starting the old program without the old marker is not enough either.
        '[Desktop Entry]\nName=CSV Tidy\nExec="/opt/old/bin/csv-tidy-ui"\n',
    ],
)
def test_old_linux_names_of_other_programs_are_kept(tmp_path, text):
    foreign = tmp_path / "csv-tidy.desktop"
    foreign.write_text(text, encoding="utf-8")
    made = shortcuts.install(folder=tmp_path, platform="linux", ui=UI, python=PY)
    assert [name for name, _ in statuses(made)] == ["datakrit-update.desktop", "datakrit.desktop"]
    assert foreign.read_text(encoding="utf-8") == text
    shortcuts.remove(folder=tmp_path, platform="linux")
    assert foreign.read_text(encoding="utf-8") == text


def test_remove_also_takes_away_the_old_linux_entries(tmp_path):
    shortcuts.install(folder=tmp_path, platform="linux", ui=UI, python=PY)
    old_linux_entries(tmp_path)
    gone = shortcuts.remove(folder=tmp_path, platform="linux")
    assert {status for _, status in statuses(gone)} == {"removed"} and len(gone) == 4
    assert list(tmp_path.iterdir()) == []


def test_old_linux_entries_in_the_default_places_go_also_with_no_desktop(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("XDG_DESKTOP_DIR", raising=False)
    menu, desktop = tmp_path / "data" / "applications", tmp_path / "Desktop"
    old_linux_entries(menu)
    desktop.mkdir()
    (desktop / "csv-tidy.desktop").write_text(OLD_MAIN, encoding="utf-8")
    made = shortcuts.install(platform="linux", ui=UI, python=PY, desktop=False)
    paths = sorted((Path(o.path).relative_to(tmp_path).as_posix(), o.status) for o in made)
    assert paths == [
        ("Desktop/csv-tidy.desktop", "removed"),
        ("data/applications/csv-tidy-update.desktop", "removed"),
        ("data/applications/csv-tidy.desktop", "removed"),
        ("data/applications/datakrit-update.desktop", "created"),
        ("data/applications/datakrit.desktop", "created"),
    ]
    assert list(desktop.iterdir()) == []


@MADE_HERE
def test_the_command_that_csv_tidy_1_2_0_runs_replaces_its_shortcuts(tmp_path):
    if sys.platform == "win32":
        old_windows_shortcuts(tmp_path)
    else:
        old_linux_entries(tmp_path)
    result = run_cli("shortcut", "install", "--no-desktop", "--folder", str(tmp_path))
    assert result.code == 0, result.err
    assert result.out.count("removed: ") == 2 and result.out.count("created: ") == 2
    assert "Start Datakrit with the Datakrit icon" in result.out
    assert all("datakrit" in p.name.lower() for p in tmp_path.iterdir())


def windows_lnk(path, target, arguments=""):
    script = (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$f = $s.CreateShortcut('{path}'); "
        f"$f.TargetPath = '{target}'; $f.Arguments = '{arguments}'; $f.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=True)


def old_windows_shortcuts(folder):
    windows_lnk(folder / "CSV Tidy.lnk", Path(sys.executable).with_name("csv-tidy-ui.exe"))
    windows_lnk(folder / "Update CSV Tidy.lnk", Path(sys.executable), "-m csv_tidy update --pause")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shortcuts (.lnk) need Windows")
def test_install_and_remove_take_away_the_old_windows_shortcuts(tmp_path):
    ui = Path(sys.executable).with_name("datakrit-ui.exe")
    old_windows_shortcuts(tmp_path)
    made = shortcuts.install(folder=tmp_path, platform="win32", ui=ui, python=Path(sys.executable))
    assert statuses(made) == [
        ("CSV Tidy.lnk", "removed"),
        ("Datakrit.lnk", "created"),
        ("Update CSV Tidy.lnk", "removed"),
        ("Update Datakrit.lnk", "created"),
    ]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Datakrit.lnk", "Update Datakrit.lnk"]
    old_windows_shortcuts(tmp_path)
    gone = shortcuts.remove(folder=tmp_path, platform="win32")
    assert {status for _, status in statuses(gone)} == {"removed"} and len(gone) == 4
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shortcuts (.lnk) need Windows")
def test_old_windows_names_of_other_programs_are_kept(tmp_path):
    ui = Path(sys.executable).with_name("datakrit-ui.exe")
    windows_lnk(tmp_path / "CSV Tidy.lnk", "C:\\Windows\\notepad.exe")
    windows_lnk(tmp_path / "Update CSV Tidy.lnk", "C:\\Windows\\notepad.exe", "-m other")
    made = shortcuts.install(folder=tmp_path, platform="win32", ui=ui, python=Path(sys.executable))
    assert statuses(made) == [("Datakrit.lnk", "created"), ("Update Datakrit.lnk", "created")]
    shortcuts.remove(folder=tmp_path, platform="win32")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["CSV Tidy.lnk", "Update CSV Tidy.lnk"]


def test_windows_looks_for_the_old_shortcuts_where_csv_tidy_made_them(monkeypatch):
    """Without --folder the old shortcuts are looked for on the Desktop and in the Start Menu,
    also with --no-desktop (their program is gone after the switch)."""
    seen = {}

    def fake_run(command, capture_output, env, timeout, check):
        request = json.loads(env["DATAKRIT_SHORTCUTS"])
        seen.update(request)
        out = [{"path": item["name"], "status": "absent"} for item in request["items"]]
        return subprocess.CompletedProcess(command, 0, json.dumps(out).encode(), b"")

    monkeypatch.setattr(shortcuts.subprocess, "run", fake_run)
    shortcuts.install(platform="win32", ui=UI, python=PY, desktop=False)
    places = [(i["name"], i["special"], i["legacy"], i["program"]) for i in seen["items"]]
    assert places == [
        ("Datakrit", "Programs", False, "datakrit-ui"),
        ("Update Datakrit", "Programs", False, "datakrit-ui"),
        ("CSV Tidy", "Desktop", True, "csv-tidy-ui"),
        ("CSV Tidy", "Programs", True, "csv-tidy-ui"),
        ("Update CSV Tidy", "Programs", True, "csv-tidy-ui"),
    ]
    assert {i["module"] for i in seen["items"] if i["legacy"]} == {"-m csv_tidy"}
    assert {i["module"] for i in seen["items"] if not i["legacy"]} == {"-m datakrit"}
    assert seen["action"] == "install" and seen["folder"] is None
    shortcuts.remove(platform="win32")
    assert [i["name"] for i in seen["items"]] == [
        "Datakrit",
        "Datakrit",
        "Update Datakrit",
        "CSV Tidy",
        "CSV Tidy",
        "Update CSV Tidy",
    ]
    assert seen["action"] == "remove"
