"""Explicit updates from the project's GitHub releases.

This is the only part of CSV Tidy that connects to the internet, and only when the user runs
``csv-tidy update`` (or the "Update CSV Tidy" shortcut). It reads the release information
from the GitHub API, picks the wheel attached to the release, and has pip install it with the
SHA-256 that GitHub publishes for that file, so pip refuses a download that does not match.
Functions here never print; the CLI reports what happened.
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from . import __version__
from .errors import CsvTidyError

REPOSITORY = "JudikaM/csv-tidy"
API = f"https://api.github.com/repos/{REPOSITORY}/releases"
DOWNLOADS = f"https://github.com/{REPOSITORY}/releases/download/"
OFFLINE_HINT = (
    "Check the internet connection and try again, or download the wheel from "
    f"https://github.com/{REPOSITORY}/releases and install it with "
    "`python -m pip install <path-to-wheel>`."
)


@dataclass(frozen=True)
class Release:
    version: str
    page_url: str
    wheel_name: str
    wheel_url: str
    sha256: str


def fetch_json(url: str) -> dict[str, Any]:
    """GET ``url`` from the GitHub API. Replaced by test doubles in the tests."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"csv-tidy/{__version__}",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    return data


def run_pip(command: Sequence[str]) -> int:
    """Run pip in this console so its progress is visible. Replaced in the tests."""
    return subprocess.run(list(command), check=False).returncode


def version_key(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise CsvTidyError(f"'{version}' is not a release version such as 0.4.0")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def find_release(version: str | None = None) -> Release:
    """The latest release, or the release of ``version``, with its wheel and SHA-256."""
    if version is not None:
        version_key(version)
        url = f"{API}/tags/v{version.removeprefix('v')}"
    else:
        url = f"{API}/latest"
    try:
        data = fetch_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            wanted = f"version {version}" if version else "a published release"
            raise CsvTidyError(f"GitHub has no {wanted} of CSV Tidy.") from None
        raise CsvTidyError(f"could not reach GitHub ({exc}). {OFFLINE_HINT}") from None
    except (OSError, ValueError) as exc:
        raise CsvTidyError(f"could not reach GitHub ({exc}). {OFFLINE_HINT}") from None
    tag = str(data.get("tag_name", ""))
    try:
        version_key(tag)
    except CsvTidyError:
        raise CsvTidyError(f"the release tag '{tag}' is not a version such as v0.4.0") from None
    found = tag.removeprefix("v")
    wheel_name = f"csv_tidy-{found}-py3-none-any.whl"
    asset = next((a for a in data.get("assets", []) if a.get("name") == wheel_name), None)
    if asset is None:
        raise CsvTidyError(f"release {tag} has no wheel named {wheel_name}. {OFFLINE_HINT}")
    wheel_url = str(asset.get("browser_download_url", ""))
    if not wheel_url.startswith(DOWNLOADS):
        raise CsvTidyError(
            f"release {tag} points its wheel to an unexpected address; nothing was installed."
        )
    digest = str(asset.get("digest") or "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise CsvTidyError(
            f"release {tag} publishes no SHA-256 for {wheel_name}, so the download cannot be "
            "verified; nothing was installed."
        )
    return Release(
        found,
        str(data.get("html_url", f"https://github.com/{REPOSITORY}/releases/tag/{tag}")),
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
