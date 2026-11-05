"""`datakrit update`: explicit, verified updates from the project's GitHub releases.

The network and pip are replaced by test doubles: these tests check which address is asked,
which release is chosen, which commands are built, and what the user is told, without
installing anything. The local pip check at the end installs a dummy ``datakrit`` wheel built
here into a temporary folder; nothing is ever published.
"""

import base64
import email.message
import hashlib
import io
import os
import subprocess
import sys
import urllib.error
import zipfile
from pathlib import Path

import pytest
from conftest import run_cli

from datakrit import __version__, update
from datakrit.errors import DatakritError

DIGEST = "a" * 64
REPO = "JudikaM/datakrit"


def api(path="latest"):
    return f"https://api.github.com/repos/{REPO}/releases/{path}"


LATEST = api()


def release_json(version="9.9.9", digest=f"sha256:{DIGEST}", url=None, name=None):
    wheel = name or f"datakrit-{version}-py3-none-any.whl"
    sdist = f"datakrit-{version}.tar.gz"
    return {
        "tag_name": f"v{version}",
        "html_url": f"https://github.com/{REPO}/releases/tag/v{version}",
        "assets": [
            {
                "name": sdist,
                "browser_download_url": f"https://github.com/{REPO}/releases/download/"
                f"v{version}/{sdist}",
                "digest": "sha256:" + "b" * 64,
            },
            {
                "name": wheel,
                "browser_download_url": url
                or f"https://github.com/{REPO}/releases/download/v{version}/{wheel}",
                "digest": digest,
            },
        ],
    }


def not_found(url):
    return urllib.error.HTTPError(url, 404, "Not Found", email.message.Message(), None)


@pytest.fixture
def github(monkeypatch):
    """Answer release lookups from a dict {url: json, (final_url, json), or exception} and
    record the URLs asked. A URL without an answer is a 404."""
    answers, asked = {}, []

    def fetch(url):
        asked.append(url)
        answer = answers.get(url, not_found(url))
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, tuple):
            return answer
        return url, answer

    monkeypatch.setattr(update, "fetch_json", fetch)
    return answers, asked


@pytest.fixture
def pip(monkeypatch):
    """Record pip commands; ``returncode`` is what each pip run returns."""
    calls = []

    def run(command):
        calls.append(command)
        return run.returncode

    run.returncode = 0
    monkeypatch.setattr(update, "run_pip", run)
    return run, calls


# --------------------------------------------------------------------- finding a release


def test_find_release_reads_the_wheel_and_its_published_hash(github):
    answers, asked = github
    answers[LATEST] = release_json("9.9.9")
    found = update.find_release()
    assert asked == [LATEST]
    assert found.version == "9.9.9"
    assert found.wheel_name == "datakrit-9.9.9-py3-none-any.whl"
    assert found.wheel_url == (
        "https://github.com/JudikaM/datakrit/releases/download/v9.9.9/"
        "datakrit-9.9.9-py3-none-any.whl"
    )
    assert found.page_url == "https://github.com/JudikaM/datakrit/releases/tag/v9.9.9"
    assert found.sha256 == DIGEST
    assert update.pip_command(found, "python") == [
        "python",
        "-m",
        "pip",
        "install",
        "--upgrade",
        f"{found.wheel_url}#sha256={DIGEST}",
    ]


def test_github_has_no_release(github):
    _, asked = github
    with pytest.raises(DatakritError, match="GitHub has no a published release of Datakrit"):
        update.find_release()
    with pytest.raises(DatakritError, match=r"GitHub has no version 2\.0\.9 of Datakrit"):
        update.find_release("2.0.9")
    assert asked == [LATEST, api("tags/v2.0.9")]


@pytest.mark.parametrize(
    "failure",
    [
        OSError("no route to host"),
        urllib.error.HTTPError(LATEST, 403, "rate limited", email.message.Message(), None),
        ValueError("not JSON"),
    ],
)
def test_network_failures_name_the_releases_page(github, failure):
    answers, _ = github
    answers[LATEST] = failure
    with pytest.raises(DatakritError, match="could not reach GitHub") as caught:
        update.find_release()
    assert "https://github.com/JudikaM/datakrit/releases" in str(caught.value)


@pytest.mark.parametrize(
    "final",
    [
        "https://example.com/repos/JudikaM/datakrit/releases/latest",
        "http://api.github.com/repos/JudikaM/datakrit/releases/latest",
        "https://api.github.com.example.com/releases/latest",
        "https://github.com/JudikaM/datakrit/releases/latest",
    ],
)
def test_an_answer_from_a_redirect_off_the_github_api_is_refused(github, final):
    answers, _ = github
    answers[LATEST] = (final, release_json("9.9.9"))
    with pytest.raises(DatakritError, match="unexpected address; nothing was installed"):
        update.find_release()


def test_a_redirect_within_the_github_api_is_followed(github):
    answers, _ = github
    answers[LATEST] = (
        "https://api.github.com/repositories/123456/releases/latest",
        release_json("9.9.9"),
    )
    found = update.find_release()
    assert found.page_url == "https://github.com/JudikaM/datakrit/releases/tag/v9.9.9"


def test_fetch_json_reports_the_address_after_redirects(monkeypatch):
    class Response(io.BytesIO):
        def geturl(self):
            return "https://api.github.com/repositories/1/releases/latest"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    seen = []

    def urlopen(request, timeout):
        seen.append((request.full_url, request.get_header("User-agent"), timeout))
        return Response(b'{"tag_name": "v2.0.0"}')

    monkeypatch.setattr(update.urllib.request, "urlopen", urlopen)
    final, data = update.fetch_json(LATEST)
    assert final == "https://api.github.com/repositories/1/releases/latest"
    assert data == {"tag_name": "v2.0.0"}
    assert seen == [(LATEST, f"datakrit/{__version__}", 30)]
    assert __version__ == "2.1.1"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/datakrit-9.9.9-py3-none-any.whl",
        "https://github.com/someone/datakrit/releases/download/v9.9.9/x.whl",
        "https://github.com/JudikaM/datakrit-evil/releases/download/v9.9.9/x.whl",
        "https://github.com/JudikaM/datakrit2/releases/download/v9.9.9/x.whl",
        "https://github.com/JudikaM/other/releases/download/v9.9.9/x.whl",
        "http://github.com/JudikaM/datakrit/releases/download/v9.9.9/x.whl",
        "https://github.com/JudikaM/datakrit/archive/v9.9.9.whl",
        "github.com/JudikaM/datakrit/releases/download/v9.9.9/x.whl",
    ],
)
def test_untrusted_download_addresses_are_refused(github, url):
    answers, _ = github
    answers[LATEST] = release_json(url=url)
    with pytest.raises(DatakritError, match="unexpected address"):
        update.find_release()


@pytest.mark.parametrize(
    "digest",
    [None, "", "md5:abc", "sha256:" + "A" * 64, "sha256:" + "a" * 63, "sha256:" + "g" * 64],
)
def test_missing_or_malformed_digests_are_refused(github, digest):
    answers, _ = github
    answers[LATEST] = release_json(digest=digest)
    with pytest.raises(DatakritError, match="no SHA-256"):
        update.find_release()


@pytest.mark.parametrize(
    "broken, message",
    [
        (release_json(name="other.whl"), "no wheel named datakrit-9.9.9-py3-none-any.whl"),
        (release_json(name="datakrit-9.9.8-py3-none-any.whl"), "no wheel"),
        (release_json(name="datakrit-9.9.9-py3-none-win_amd64.whl"), "no wheel"),
        ({"tag_name": "nightly", "assets": []}, "version"),
    ],
)
def test_unusable_releases_are_refused(github, broken, message):
    answers, _ = github
    answers[LATEST] = broken
    with pytest.raises(DatakritError, match=message):
        update.find_release()


def test_a_specific_version_is_looked_up_by_its_tag(github):
    answers, asked = github
    url = api("tags/v2.0.3")
    answers[url] = release_json("2.0.3")
    assert update.find_release("2.0.3").version == "2.0.3"
    assert update.find_release("v2.0.3").version == "2.0.3"
    assert asked == [url, url]


@pytest.mark.parametrize("version", ["1.2.0", "v1.1.1", "0.4.0", "1.99.99"])
def test_versions_before_2_0_0_are_refused_without_going_online(github, version):
    _, asked = github
    with pytest.raises(DatakritError) as caught:
        update.find_release(version)
    message = str(caught.value)
    assert "2.0.0 or newer" in message and version in message
    assert "https://github.com/JudikaM/datakrit/releases" in message
    assert "python -m pip install <path-to-wheel>" in message
    assert asked == []


def test_malformed_versions_are_refused(github):
    with pytest.raises(DatakritError, match=r"not a release version such as 2.0.0"):
        update.find_release("latest")


# ------------------------------------------------------------------- the update command


def test_update_installs_a_newer_release_with_hash_checking(github, pip):
    answers, _ = github
    answers[LATEST] = release_json("9.9.9")
    _, calls = pip
    result = run_cli("update")
    assert result.code == 0, result.err
    assert len(calls) == 1 and calls[0][-1].endswith(f"#sha256={DIGEST}")
    assert calls[0][1:5] == ["-m", "pip", "install", "--upgrade"]
    assert f"from {__version__} to 9.9.9" in result.out
    assert "https://github.com/JudikaM/datakrit/releases/tag/v9.9.9" in result.out
    assert "Close Datakrit" in result.out and "Updated to 9.9.9" in result.out


def test_up_to_date_and_check_only_never_run_pip(github, pip):
    answers, _ = github
    _, calls = pip
    answers[LATEST] = release_json(__version__)
    current = run_cli("update")
    assert current.code == 0 and f"Datakrit {__version__} is up to date" in current.out
    same = run_cli("update", "--check")
    assert same.code == 0
    assert same.out.splitlines() == [
        f"Installed: Datakrit {__version__}. Latest release: {__version__}.",
        "Datakrit is up to date.",
    ]
    answers[LATEST] = release_json("9.9.9")
    check = run_cli("update", "--check")
    assert check.code == 0
    assert check.out.splitlines() == [
        f"Installed: Datakrit {__version__}. Latest release: 9.9.9.",
        "Datakrit 9.9.9 is available (https://github.com/JudikaM/datakrit/releases/tag/v9.9.9).",
        "Install it with: datakrit update",
    ]
    assert calls == []


def test_older_releases_are_installed_only_when_asked_for(github, pip):
    answers, _ = github
    _, calls = pip
    answers[LATEST] = release_json(__version__)
    answers[api(f"tags/v{__version__}")] = release_json(__version__)
    assert "up to date" in run_cli("update").out and calls == []
    # The installed version is asked for explicitly: nothing to do either.
    assert "up to date" in run_cli("update", "--version", __version__).out and calls == []


def test_update_version_before_2_0_0_is_a_usage_hint(github, pip):
    _, asked = github
    _, calls = pip
    result = run_cli("update", "--version", "1.2.0")
    assert result.code == 2
    assert result.err.startswith("datakrit: error: `update` installs Datakrit 2.0.0 or newer")
    assert "download its wheel from https://github.com/JudikaM/datakrit/releases" in result.err
    assert asked == [] and calls == []


def test_network_and_pip_failures_are_explained(github, pip):
    answers, _ = github
    answers[LATEST] = OSError("no route to host")
    offline = run_cli("update")
    assert offline.code == 2
    assert offline.err.startswith("datakrit: error: could not reach GitHub")
    assert "pip install" in offline.err
    run, calls = pip
    answers[LATEST] = release_json("9.9.9")
    run.returncode = 1
    failed = run_cli("update")
    assert failed.code == 2 and "pip could not install Datakrit 9.9.9" in failed.err
    assert f"Datakrit {__version__} is still installed" in failed.err and len(calls) == 1


def test_pause_waits_for_enter_so_a_shortcut_window_stays_readable(github, pip, monkeypatch):
    answers, _ = github
    answers[LATEST] = release_json(__version__)
    seen = []
    monkeypatch.setattr("builtins.input", lambda prompt="": seen.append(prompt) or "")
    assert run_cli("update", "--pause").code == 0
    assert seen and "Enter" in seen[0]
    answers[LATEST] = OSError("offline")
    assert run_cli("update", "--pause").code == 2 and len(seen) == 2


# ------------------------------------------------------------------ the Windows app (frozen)


@pytest.fixture
def frozen(monkeypatch):
    """Run as the Windows app does: PyInstaller sets ``sys.frozen``."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert update.frozen()


def test_a_pip_install_is_not_frozen():
    assert not getattr(sys, "frozen", False) and not update.frozen()


def test_the_windows_app_reports_the_zip_and_never_runs_pip(github, pip, frozen):
    answers, asked = github
    _, calls = pip
    answers[LATEST] = release_json("9.9.9")
    page = "https://github.com/JudikaM/datakrit/releases/tag/v9.9.9"
    for args in (("update",), ("update", "--check")):
        result = run_cli(*args)
        assert result.code == 0, result.err
        assert result.out.splitlines() == [
            f"Installed: Datakrit {__version__} (Windows app). Latest release: 9.9.9.",
            f"Download Datakrit-9.9.9-windows-x64.zip from {page}, check its SHA-256 against "
            "the release notes, and replace the Datakrit folder with the one in the zip. The "
            "Windows app does not update itself; nothing was installed.",
        ]
    assert asked == [LATEST, LATEST] and calls == []


def test_the_windows_app_up_to_date_and_chosen_versions(github, pip, frozen):
    answers, _ = github
    _, calls = pip
    answers[LATEST] = release_json(__version__)
    current = run_cli("update")
    assert current.code == 0 and current.out.splitlines()[-1] == "Datakrit is up to date."
    answers[api("tags/v2.0.0")] = release_json("2.0.0")
    if __version__ != "2.0.0":
        chosen = run_cli("update", "--version", "2.0.0")
        assert chosen.code == 0 and "Download Datakrit-2.0.0-windows-x64.zip" in chosen.out
    answers[LATEST] = OSError("offline")
    offline = run_cli("update")
    assert offline.code == 2 and "could not reach GitHub" in offline.err
    assert calls == []


def test_only_the_update_command_uses_the_network(monkeypatch, examples):
    def refuse(url):
        raise AssertionError(f"unexpected network access: {url}")

    monkeypatch.setattr(update, "fetch_json", refuse)
    profile = str(examples / "profiles" / "transactions-id.toml")
    valid = str(examples / "transactions_valid.csv")
    assert run_cli("check", valid, "--profile", profile).code == 0


# ------------------------------------------------- local pip check with a dummy wheel


def build_dummy_datakrit(folder: Path, version: str = "9.9.9") -> Path:
    """A minimal, valid ``datakrit`` wheel."""
    info = f"datakrit-{version}.dist-info"
    files = {
        "datakrit/__init__.py": f'__version__ = "{version}"\n',
        f"{info}/METADATA": f"Metadata-Version: 2.1\nName: datakrit\nVersion: {version}\n",
        f"{info}/WHEEL": (
            "Wheel-Version: 1.0\nGenerator: datakrit-tests\nRoot-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ),
    }
    record = []
    for name, text in files.items():
        data = text.encode()
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        record.append(f"{name},sha256={digest},{len(data)}")
    record.append(f"{info}/RECORD,,")
    wheel = folder / f"datakrit-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
        archive.writestr(f"{info}/RECORD", "\n".join(record) + "\n")
    return wheel


def pip_into(command, target):
    """The update's pip command, kept offline and confined to ``target``."""
    full = [*command, "--no-index", "--no-deps", "--target", str(target), "--quiet"]
    env = {**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    return subprocess.run(full, capture_output=True, text=True, env=env, check=False)


def test_pip_installs_the_wheel_only_with_its_hash(tmp_path):
    wheel = build_dummy_datakrit(tmp_path)
    good = hashlib.sha256(wheel.read_bytes()).hexdigest()

    def release(sha256):
        return update.Release("9.9.9", "", wheel.name, wheel.resolve().as_uri(), sha256)

    refused = pip_into(update.pip_command(release("0" * 64), sys.executable), tmp_path / "bad")
    assert refused.returncode != 0
    assert "hash" in (refused.stdout + refused.stderr).lower()
    assert not (tmp_path / "bad" / "datakrit").exists()
    target = tmp_path / "good"
    done = pip_into(update.pip_command(release(good), sys.executable), target)
    assert done.returncode == 0, done.stderr
    assert (target / "datakrit" / "__init__.py").exists()
