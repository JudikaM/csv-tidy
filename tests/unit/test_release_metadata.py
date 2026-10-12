"""Release consistency: the package version, the changelog, the documented sample output,
and the interface assets that must ship inside the package."""

import re
from importlib import resources
from pathlib import Path

from csv_tidy import __version__

ROOT = Path(__file__).resolve().parents[2]


def test_version_is_a_plain_semantic_version():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_changelog_latest_release_is_the_package_version():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## \[([^\]]+)\](?: - (\d{4}-\d{2}-\d{2}))?$", text, flags=re.M)
    assert headings[0] == ("Unreleased", "")
    latest, date = headings[1]
    assert latest == __version__, "move the Unreleased entries under the new version"
    assert date, "a released version needs its date"
    versions = [name for name, _ in headings[1:]]
    assert versions == sorted(versions, key=lambda v: tuple(map(int, v.split("."))), reverse=True)


def test_readme_sample_output_shows_the_package_version():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    shown = set(re.findall(r"^CSV Tidy (\d+\.\d+\.\d+) - ", text, flags=re.M))
    assert shown == {__version__}


def test_interface_assets_are_package_data():
    static = resources.files("csv_tidy").joinpath("ui_static")
    page = static.joinpath("index.html").read_text(encoding="utf-8")
    for name in ("app.css", "app.js"):
        assert f'"{name}"' in page
        assert len(static.joinpath(name).read_bytes()) > 1000
    assert "{{token}}" in page and "{{version}}" in page
