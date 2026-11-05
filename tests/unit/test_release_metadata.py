"""Release consistency: the package version, the changelog, the documented sample output,
and the interface assets that must ship inside the package."""

import re
from importlib import resources
from pathlib import Path

from datakrit import __version__

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
    shown = set(re.findall(r"^Datakrit (\d+\.\d+\.\d+) - ", text, flags=re.M))
    assert shown == {__version__}


def test_interface_assets_are_package_data():
    static = resources.files("datakrit").joinpath("ui_static")
    page = static.joinpath("index.html").read_text(encoding="utf-8")
    for name in ("app.css", "app.js"):
        assert f'"{name}"' in page
        assert len(static.joinpath(name).read_bytes()) > 1000
    assert "{{token}}" in page and "{{version}}" in page


def test_readme_links_and_images_work_on_the_pypi_page():
    """README.md is the PyPI project page, where relative links and images do not work."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    blob = "https://github.com/JudikaM/datakrit/blob/main/"
    raw = "https://raw.githubusercontent.com/JudikaM/datakrit/main/"
    targets = re.findall(r"\]\(([^)\s]+)\)", text)
    targets += re.findall(r'\b(?:src|srcset)="([^"]+)"', text)
    assert targets
    relative = [t for t in targets if not t.startswith(("https://", "http://"))]
    assert relative == []
    anchors = {
        re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        for heading in re.findall(r"^#+ (.+)$", text, flags=re.M)
    }
    for target in targets:
        for prefix in (blob, raw):
            if target.startswith(prefix):
                path, _, anchor = target.removeprefix(prefix).partition("#")
                assert (ROOT / path).exists(), target
                if path == "README.md":
                    assert anchor in anchors, target
    images = re.findall(r'\b(?:src|srcset)="([^"]+)"', text)
    assert images and all(i.startswith(raw) for i in images)


def test_notices_of_the_interface_icons_ship_with_the_package():
    """The ISC License of Lucide and the MIT License of Feather ask for their notices in
    every copy: NOTICE.md holds them in full, and the wheel and sdist include it."""
    import tomllib

    notice = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
    assert "Copyright (c) 2026 Lucide Icons and Contributors" in notice
    assert "ISC License" in notice and "appear in all copies." in notice
    assert notice.count("Cole Bemis") == 2 and notice.count("The MIT License (MIT)") == 2
    assert notice.count("shall be included in all\ncopies or substantial portions") == 2
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["license-files"] == ["LICENSE", "NOTICE.md"]
    sdist = project["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    assert "/LICENSE" in sdist and "/NOTICE.md" in sdist
