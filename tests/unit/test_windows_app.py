"""The sources of the Windows app in packaging/windows/ and its build tools.

The app itself is built and smoke-tested by the windows-app workflow (and locally, see
CONTRIBUTING.md); these tests keep its sources consistent with the package."""

import importlib.util
import re
import runpy
import tomllib
import zipfile
from pathlib import Path

import pytest

import datakrit.ui as ui_module

ROOT = Path(__file__).resolve().parents[2]
WINDOWS = ROOT / "packaging" / "windows"


def load(name):
    spec = importlib.util.spec_from_file_location(f"windows_{name}", WINDOWS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_smoke_test_fetches_every_file_of_the_page():
    smoke = load("smoke_app")
    expected = {path: kind for path, (_, kind) in ui_module.STATIC.items()}
    fetched = smoke.ASSETS
    assert fetched == expected
    assert smoke.TOKEN_HEADER == ui_module.TOKEN_HEADER
    assert smoke.URL_FILE_VARIABLE == ui_module.URL_FILE_VARIABLE


def test_the_launcher_calls_the_entry_point_of_datakrit_ui(monkeypatch):
    calls = []
    monkeypatch.setattr(ui_module, "gui_main", lambda: calls.append("gui_main") or 0)
    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(WINDOWS / "launcher.py"), run_name="__main__")
    assert stopped.value.code == 0 and calls == ["gui_main"]
    entry = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert entry["project"]["gui-scripts"] == {"datakrit-ui": "datakrit.ui:gui_main"}


def test_the_spec_builds_one_folder_without_a_console_and_with_the_page():
    spec = (WINDOWS / "datakrit.spec").read_text(encoding="utf-8")
    assert 'collect_data_files("datakrit", includes=["ui_static/*"])' in spec
    assert 'collect_submodules("datakrit")' in spec
    assert "console=False" in spec and "exclude_binaries=True" in spec and "COLLECT(" in spec
    assert 'StringStruct("ProductName", "Datakrit")' in spec
    assert 'StringStruct("FileDescription", "Datakrit local interface")' in spec
    assert (WINDOWS / "datakrit.ico").read_bytes()[:4] == b"\x00\x00\x01\x00"
    build = load("build_app")
    assert build.source_version() == ui_module.__version__
    assert build.ZIP.format(version="2.1.0") == "Datakrit-2.1.0-windows-x64.zip"


def test_the_zip_holds_the_datakrit_folder(tmp_path):
    build = load("build_app")
    folder = tmp_path / "Datakrit"
    (folder / "_internal").mkdir(parents=True)
    (folder / "Datakrit.exe").write_bytes(b"MZ")
    (folder / "_internal" / "base.dll").write_bytes(b"MZ")
    target = tmp_path / "app.zip"
    build.make_zip(folder, target)
    with zipfile.ZipFile(target) as archive:
        names = sorted(archive.namelist())
    assert names == ["Datakrit/Datakrit.exe", "Datakrit/_internal/base.dll"]


def test_build_tools_are_pinned_with_hashes_and_are_never_dependencies():
    text = (ROOT / "constraints-exe.txt").read_text(encoding="utf-8")
    requirements = re.split(r"\n(?=[A-Za-z])", re.sub(r"(?m)^#.*\n", "", text).strip())
    names = []
    for requirement in requirements:
        pin = re.match(r"([A-Za-z0-9_.-]+)==(\S+) \\\n", requirement)
        assert pin, requirement
        names.append(pin.group(1).lower())
        hashes = re.findall(r"--hash=sha256:([0-9a-f]{64})", requirement)
        assert hashes and len(hashes) == len(set(hashes)), requirement
    assert "pyinstaller" in names and "tomli_w" in names
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    declared = " ".join(project["dependencies"])
    for extra in project["optional-dependencies"].values():
        declared += " " + " ".join(extra)
    assert "pyinstaller" not in declared.lower()
