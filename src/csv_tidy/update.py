"""Explicit updates from the project's GitHub releases.

This is the only part of CSV Tidy that connects to the internet, and only when the user runs
``csv-tidy update`` (or the "Update CSV Tidy" shortcut). It reads the release information
from the GitHub API, picks the wheel attached to the release, and has pip install it with the
SHA-256 that GitHub publishes for that file, so pip refuses a download that does not match.
Functions here never print; the CLI reports what happened.

CSV Tidy is renamed to Datakrit in 2.0.0, and the repository ``JudikaM/csv-tidy`` becomes
``JudikaM/datakrit``. The trusted repositories are therefore asked in a fixed order: the new
name first, then the old one (GitHub redirects the old name after the rename). A release that
carries a ``datakrit`` wheel is a *switch release*: installing it switches this installation
from CSV Tidy to Datakrit (see ``cli._switch``).
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from . import __version__
from .errors import CsvTidyError

# Asked in this order; "GitHub has no ... release" only when every one answers 404.
REPOSITORIES = ("JudikaM/datakrit", "JudikaM/csv-tidy")
# Before and after the rename this address works (GitHub redirects the old name), so it is
# the one named when no repository answered at all.
LEGACY_REPOSITORY = "JudikaM/csv-tidy"
API_ROOT = "https://api.github.com/"
# The wheel names, in the order they are looked for. A datakrit wheel marks a switch release.
SWITCH_WHEEL = "datakrit-{version}-py3-none-any.whl"
WHEEL = "csv_tidy-{version}-py3-none-any.whl"
NEW_NAME = "Datakrit"
NEW_MODULE = "datakrit"
DISTRIBUTION = "csv-tidy"


def releases_api(repository: str) -> str:
    return f"{API_ROOT}repos/{repository}/releases"


def downloads(repository: str) -> str:
    return f"https://github.com/{repository}/releases/download/"


def offline_hint(repository: str = LEGACY_REPOSITORY) -> str:
    return (
        "Check the internet connection and try again, or download the wheel from "
        f"https://github.com/{repository}/releases and install it with "
        "`python -m pip install <path-to-wheel>`."
    )


@dataclass(frozen=True)
class Release:
    version: str
    page_url: str
    wheel_name: str
    wheel_url: str
    sha256: str
    repository: str = LEGACY_REPOSITORY

    @property
    def switch(self) -> bool:
        """True when this release installs Datakrit instead of CSV Tidy."""
        return self.wheel_name.startswith(f"{NEW_MODULE}-")


def fetch_json(url: str) -> tuple[str, dict[str, Any]]:
    """GET ``url`` from the GitHub API and return the final address (after any redirect
    that urllib followed) with the decoded answer. Replaced by test doubles in the tests."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"csv-tidy/{__version__}",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        final = str(response.geturl())
        data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    return final, data


def run_pip(command: Sequence[str]) -> int:
    """Run pip in this console so its progress is visible. Replaced in the tests."""
    return subprocess.run(list(command), check=False).returncode


def run_program(command: Sequence[str]) -> int:
    """Run another program in this console (Datakrit's shortcut command). Replaced in the
    tests."""
    return subprocess.run(list(command), check=False).returncode


def version_key(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise CsvTidyError(f"'{version}' is not a release version such as 0.4.0")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def find_release(version: str | None = None) -> Release:
    """The latest release, or the release of ``version``, with its wheel and SHA-256.

    The trusted repositories are asked in order; a 404 moves on to the next one, any other
    failure stops. An answer is accepted only from ``https://api.github.com/``, also after a
    redirect.
    """
    if version is not None:
        version_key(version)
        path = f"tags/v{version.removeprefix('v')}"
    else:
        path = "latest"
    for repository in REPOSITORIES:
        url = f"{releases_api(repository)}/{path}"
        try:
            final, data = fetch_json(url)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            raise CsvTidyError(f"could not reach GitHub ({exc}). {offline_hint()}") from None
        except (OSError, ValueError) as exc:
            raise CsvTidyError(f"could not reach GitHub ({exc}). {offline_hint()}") from None
        if not final.startswith(API_ROOT) or not isinstance(data, dict):
            raise CsvTidyError(
                f"GitHub sent the request for {url} on to an unexpected address; nothing was "
                f"installed. {offline_hint()}"
            )
        return _release(data, repository)
    wanted = f"version {version}" if version else "a published release"
    raise CsvTidyError(f"GitHub has no {wanted} of CSV Tidy.")


def _release(data: dict[str, Any], repository: str) -> Release:
    hint = offline_hint(repository)
    tag = str(data.get("tag_name", ""))
    try:
        version_key(tag)
    except CsvTidyError:
        raise CsvTidyError(f"the release tag '{tag}' is not a version such as v0.4.0") from None
    found = tag.removeprefix("v")
    assets = [a for a in data.get("assets", []) if isinstance(a, dict)]
    asset = None
    for pattern in (SWITCH_WHEEL, WHEEL):
        wheel_name = pattern.format(version=found)
        asset = next((a for a in assets if a.get("name") == wheel_name), None)
        if asset is not None:
            break
    if asset is None:
        raise CsvTidyError(
            f"release {tag} has no wheel named {WHEEL.format(version=found)} or "
            f"{SWITCH_WHEEL.format(version=found)}. {hint}"
        )
    wheel_url = str(asset.get("browser_download_url", ""))
    if not any(wheel_url.startswith(downloads(trusted)) for trusted in REPOSITORIES):
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
        f"https://github.com/{repository}/releases/tag/{tag}",
        wheel_name,
        wheel_url,
        digest.removeprefix("sha256:"),
        repository,
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


def shortcut_command(python: str, desktop: bool) -> list[str]:
    """Datakrit's own command that makes its shortcuts (and removes CSV Tidy's)."""
    command = [python, "-m", NEW_MODULE, "shortcut", "install"]
    return command if desktop else [*command, "--no-desktop"]


def uninstall_command(python: str) -> list[str]:
    return [python, "-m", "pip", "uninstall", "-y", DISTRIBUTION]


def programs_in_use() -> list[Path]:
    """CSV Tidy's programs (``csv-tidy.exe``, ``csv-tidy-ui.exe``) that are running now.

    Windows cannot remove or move a running program, and pip's uninstall then stops halfway,
    so CSV Tidy is removed only when none of them runs. A running program cannot be opened
    for writing; the file is opened and closed again without a change. Elsewhere running
    programs can be removed, so the list is empty.
    """
    if sys.platform != "win32":
        return []
    try:
        files = metadata.distribution(DISTRIBUTION).files or []
    except metadata.PackageNotFoundError:
        return []
    busy = []
    for item in files:
        if item.suffix.lower() != ".exe":
            continue
        path = Path(str(item.locate())).resolve()
        if not path.is_file():
            continue
        try:
            with open(path, "r+b"):
                pass
        except OSError:
            busy.append(path)
    return busy


def shown(command: Sequence[str], platform: str = sys.platform) -> str:
    """A command as it can be pasted into this system's usual shell (PowerShell on Windows,
    which needs ``&`` before a quoted program path)."""
    if platform == "win32":
        text = subprocess.list2cmdline(list(command))
        return f"& {text}" if text.startswith('"') else text
    return shlex.join(command)
