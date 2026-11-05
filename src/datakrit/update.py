"""Explicit updates from the project's GitHub releases.

This is the only part of Datakrit that connects to the internet, and only when the user runs
``datakrit update`` (or the "Update Datakrit" shortcut). It reads the release information
from the GitHub API, picks the wheel attached to the release, and has pip install it with the
SHA-256 that GitHub publishes for that file, so pip refuses a download that does not match.
Functions here never print; the CLI reports what happened.

Only Datakrit releases (2.0.0 and newer) can be installed this way; earlier versions were
published under another name and are installed by hand from the Releases page.

The Windows app (a frozen program, ``sys.frozen``) contains no pip and cannot replace its own
folder, so there ``update`` only reports the release and the page with the app's zip file.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from . import __version__
from .errors import DatakritError

REPOSITORY = "JudikaM/datakrit"
API_ROOT = "https://api.github.com/"
API = f"{API_ROOT}repos/{REPOSITORY}/releases"
DOWNLOADS = f"https://github.com/{REPOSITORY}/releases/download/"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases"
WHEEL = "datakrit-{version}-py3-none-any.whl"
APP_ZIP = "Datakrit-{version}-windows-x64.zip"
# The first Datakrit release; `update --version` refuses anything older.
FIRST_VERSION = "2.0.0"
OFFLINE_HINT = (
    "Check the internet connection and try again, or download the wheel from "
    f"{RELEASES_PAGE} and install it with `python -m pip install <path-to-wheel>`."
)


@dataclass(frozen=True)
class Release:
    version: str
    page_url: str
    wheel_name: str
    wheel_url: str
    sha256: str


def fetch_json(url: str) -> tuple[str, dict[str, Any]]:
    """GET ``url`` from the GitHub API and return the final address (after any redirect
    that urllib followed) with the decoded answer. Replaced by test doubles in the tests."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"datakrit/{__version__}",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        final = str(response.geturl())
        data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    return final, data


def frozen() -> bool:
    """Whether this is the Windows app (a program made by PyInstaller), not a pip install."""
    return bool(getattr(sys, "frozen", False))


def app_zip(release: Release) -> str:
    """The name of the Windows app's zip file on the page of ``release``."""
    return APP_ZIP.format(version=release.version)


def run_pip(command: Sequence[str]) -> int:
    """Run pip in this console so its progress is visible. Replaced in the tests."""
    return subprocess.run(list(command), check=False).returncode


def version_key(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise DatakritError(f"'{version}' is not a release version such as 2.0.0")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def find_release(version: str | None = None) -> Release:
    """The latest release, or the release of ``version``, with its wheel and SHA-256.

    An answer is accepted only from ``https://api.github.com/``, also after a redirect.
    Versions before 2.0.0 are refused before anything is downloaded.
    """
    if version is not None:
        if version_key(version) < version_key(FIRST_VERSION):
            raise DatakritError(
                f"`update` installs Datakrit {FIRST_VERSION} or newer, not {version}. To use an "
                f"earlier version, download its wheel from {RELEASES_PAGE} and install it with "
                "`python -m pip install <path-to-wheel>`."
            )
        url = f"{API}/tags/v{version.removeprefix('v')}"
    else:
        url = f"{API}/latest"
    try:
        final, data = fetch_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            wanted = f"version {version}" if version else "a published release"
            raise DatakritError(f"GitHub has no {wanted} of Datakrit.") from None
        raise DatakritError(f"could not reach GitHub ({exc}). {OFFLINE_HINT}") from None
    except (OSError, ValueError) as exc:
        raise DatakritError(f"could not reach GitHub ({exc}). {OFFLINE_HINT}") from None
    if not final.startswith(API_ROOT) or not isinstance(data, dict):
        raise DatakritError(
            f"GitHub sent the request for {url} on to an unexpected address; nothing was "
            f"installed. {OFFLINE_HINT}"
        )
    return _release(data)


def _release(data: dict[str, Any]) -> Release:
    tag = str(data.get("tag_name", ""))
    try:
        version_key(tag)
    except DatakritError:
        raise DatakritError(f"the release tag '{tag}' is not a version such as v2.0.0") from None
    found = tag.removeprefix("v")
    wheel_name = WHEEL.format(version=found)
    assets = [a for a in data.get("assets", []) if isinstance(a, dict)]
    asset = next((a for a in assets if a.get("name") == wheel_name), None)
    if asset is None:
        raise DatakritError(f"release {tag} has no wheel named {wheel_name}. {OFFLINE_HINT}")
    wheel_url = str(asset.get("browser_download_url", ""))
    if not wheel_url.startswith(DOWNLOADS):
        raise DatakritError(
            f"release {tag} points its wheel to an unexpected address; nothing was installed."
        )
    digest = str(asset.get("digest") or "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise DatakritError(
            f"release {tag} publishes no SHA-256 for {wheel_name}, so the download cannot be "
            "verified; nothing was installed."
        )
    return Release(
        found,
        f"https://github.com/{REPOSITORY}/releases/tag/{tag}",
        wheel_name,
        wheel_url,
        digest.removeprefix("sha256:"),
    )


def pip_command(release: Release, python: str) -> list[str]:
    """pip checks the ``#sha256=`` fragment and refuses a file with a different hash."""
    return [
        python,
        "-m",
        "pip",
        "install",
        "--upgrade",
        f"{release.wheel_url}#sha256={release.sha256}",
    ]
