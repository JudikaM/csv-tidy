"""`csv-tidy update`: explicit, verified updates from the project's GitHub releases.

The network and pip are replaced by test doubles: these tests check which release is chosen,
which pip command is built, and what the user is told, without installing anything.
"""

import pytest
from conftest import run_cli

from csv_tidy import __version__, update
from csv_tidy.errors import CsvTidyError

DIGEST = "a" * 64


def release_json(version="9.9.9", digest=f"sha256:{DIGEST}", url=None, name=None):
    wheel = name or f"csv_tidy-{version}-py3-none-any.whl"
    return {
        "tag_name": f"v{version}",
        "html_url": f"https://github.com/JudikaM/csv-tidy/releases/tag/v{version}",
        "assets": [
            {
                "name": f"csv_tidy-{version}.tar.gz",
                "browser_download_url": "https://github.com/JudikaM/csv-tidy/releases/download/"
                f"v{version}/csv_tidy-{version}.tar.gz",
                "digest": "sha256:" + "b" * 64,
            },
            {
                "name": wheel,
                "browser_download_url": url
                or f"https://github.com/JudikaM/csv-tidy/releases/download/v{version}/{wheel}",
                "digest": digest,
            },
        ],
    }


@pytest.fixture
def github(monkeypatch):
    """Answer release lookups from a dict {url: json or exception}; record the URLs asked."""
    answers, asked = {}, []

    def fetch(url):
        asked.append(url)
        answer = answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(update, "fetch_json", fetch)
    return answers, asked


@pytest.fixture
def pip(monkeypatch):
    calls = []

    def run(command):
        calls.append(command)
        return run.returncode

    run.returncode = 0
    monkeypatch.setattr(update, "run_pip", run)
    return run, calls


LATEST = "https://api.github.com/repos/JudikaM/csv-tidy/releases/latest"


def test_find_release_reads_the_wheel_and_its_published_hash(github):
    answers, _ = github
    answers[LATEST] = release_json("9.9.9")
    found = update.find_release()
    assert found.version == "9.9.9"
    assert found.wheel_url.endswith("/v9.9.9/csv_tidy-9.9.9-py3-none-any.whl")
    assert found.sha256 == DIGEST
    assert update.pip_command(found, "python") == [
        "python",
        "-m",
        "pip",
        "install",
        "--upgrade",
        f"{found.wheel_url}#sha256={DIGEST}",
    ]


@pytest.mark.parametrize(
    "broken, message",
    [
        (release_json(digest=None), "no SHA-256"),
        (release_json(digest="md5:abc"), "no SHA-256"),
        (release_json(name="other.whl"), "no wheel"),
        (
            release_json(url="https://example.com/csv_tidy-9.9.9-py3-none-any.whl"),
            "unexpected address",
        ),
        ({"tag_name": "nightly", "assets": []}, "version"),
    ],
)
def test_unusable_releases_are_refused(github, broken, message):
    answers, _ = github
    answers[LATEST] = broken
    with pytest.raises(CsvTidyError, match=message):
        update.find_release()


def test_a_specific_version_is_looked_up_by_its_tag(github):
    answers, asked = github
    url = "https://api.github.com/repos/JudikaM/csv-tidy/releases/tags/v1.2.3"
    answers[url] = release_json("1.2.3")
    assert update.find_release("1.2.3").version == "1.2.3"
    assert update.find_release("v1.2.3").version == "1.2.3"
    assert asked == [url, url]


def test_update_installs_a_newer_release_with_hash_checking(github, pip):
    answers, _ = github
    answers[LATEST] = release_json("9.9.9")
    _, calls = pip
    result = run_cli("update")
    assert result.code == 0, result.err
    assert len(calls) == 1 and calls[0][-1].endswith(f"#sha256={DIGEST}")
    assert calls[0][1:5] == ["-m", "pip", "install", "--upgrade"]
    assert f"from {__version__} to 9.9.9" in result.out
    assert "Close CSV Tidy" in result.out and "Updated to 9.9.9" in result.out


def test_up_to_date_and_check_only_never_run_pip(github, pip):
    answers, _ = github
    _, calls = pip
    answers[LATEST] = release_json(__version__)
    current = run_cli("update")
    assert current.code == 0 and "up to date" in current.out
    answers[LATEST] = release_json("9.9.9")
    check = run_cli("update", "--check")
    assert check.code == 0 and "9.9.9 is available" in check.out
    assert calls == []


def test_older_releases_are_installed_only_when_asked_for(github, pip):
    answers, _ = github
    _, calls = pip
    answers[LATEST] = release_json("0.0.1")
    assert "up to date" in run_cli("update").out and calls == []
    answers["https://api.github.com/repos/JudikaM/csv-tidy/releases/tags/v0.0.1"] = release_json(
        "0.0.1"
    )
    assert run_cli("update", "--version", "0.0.1").code == 0 and len(calls) == 1


def test_network_and_pip_failures_are_explained(github, pip):
    answers, _ = github
    answers[LATEST] = OSError("no route to host")
    offline = run_cli("update")
    assert offline.code == 2
    assert "could not reach GitHub" in offline.err and "pip install" in offline.err
    run, calls = pip
    answers[LATEST] = release_json("9.9.9")
    run.returncode = 1
    failed = run_cli("update")
    assert failed.code == 2 and "pip could not install" in failed.err and len(calls) == 1


def test_pause_waits_for_enter_so_a_shortcut_window_stays_readable(github, pip, monkeypatch):
    answers, _ = github
    answers[LATEST] = release_json(__version__)
    seen = []
    monkeypatch.setattr("builtins.input", lambda prompt="": seen.append(prompt) or "")
    assert run_cli("update", "--pause").code == 0
    assert seen and "Enter" in seen[0]
    answers[LATEST] = OSError("offline")
    assert run_cli("update", "--pause").code == 2 and len(seen) == 2


def test_only_the_update_command_uses_the_network(monkeypatch, examples):
    def refuse(url):
        raise AssertionError(f"unexpected network access: {url}")

    monkeypatch.setattr(update, "fetch_json", refuse)
    profile = str(examples / "profiles" / "transactions-id.toml")
    assert run_cli("check", str(examples / "transactions_valid.csv"), "--schema", profile).code == 0
