"""`csv-tidy update`: explicit, verified updates from the project's GitHub releases.

The network, pip, and the shortcut functions are replaced by test doubles: these tests check
which repositories are asked, which release is chosen, which commands are built, and what the
user is told, without installing anything. The local pip checks at the end install a dummy
``datakrit`` wheel built here into a temporary folder; nothing is ever published.
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

from csv_tidy import __version__, shortcuts, update
from csv_tidy.errors import CsvTidyError

DIGEST = "a" * 64
NEW = "JudikaM/datakrit"
OLD = "JudikaM/csv-tidy"


def api(repo, path="latest"):
    return f"https://api.github.com/repos/{repo}/releases/{path}"


NEW_LATEST = api(NEW)
LATEST = api(OLD)


def release_json(
    version="9.9.9", digest=f"sha256:{DIGEST}", url=None, name=None, repo=OLD, switch=False
):
    wheel = name or (
        f"datakrit-{version}-py3-none-any.whl" if switch else f"csv_tidy-{version}-py3-none-any.whl"
    )
    sdist = f"{'datakrit' if switch else 'csv_tidy'}-{version}.tar.gz"
    return {
        "tag_name": f"v{version}",
        "html_url": f"https://github.com/{repo}/releases/tag/v{version}",
        "assets": [
            {
                "name": sdist,
                "browser_download_url": f"https://github.com/{repo}/releases/download/"
                f"v{version}/{sdist}",
                "digest": "sha256:" + "b" * 64,
            },
            {
                "name": wheel,
                "browser_download_url": url
                or f"https://github.com/{repo}/releases/download/v{version}/{wheel}",
                "digest": digest,
            },
        ],
    }


def not_found(url):
    return urllib.error.HTTPError(url, 404, "Not Found", email.message.Message(), None)


@pytest.fixture
def github(monkeypatch):
    """Answer release lookups from a dict {url: json, (final_url, json), or exception} and
    record the URLs asked. A URL without an answer is a 404, like a repository that does not
    exist (yet)."""
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
    """Record pip commands; ``returncodes`` maps a pip subcommand to its exit code."""
    calls = []

    def run(command):
        calls.append(command)
        return run.returncodes.get(command[3], 0)

    run.returncodes = {}
    monkeypatch.setattr(update, "run_pip", run)
    return run, calls


@pytest.fixture
def switch(monkeypatch, pip):
    """Doubles for the later switch steps: the shortcuts found, Datakrit's shortcut command,
    and the programs in use. Every call lands in one ordered list."""
    run_pip, calls = pip
    state = {"found": [], "shortcut_code": 0, "busy": [], "find_error": None}

    def existing(folder=None, platform=sys.platform):
        calls.append(["existing"])
        if state["find_error"]:
            raise state["find_error"]
        return state["found"]

    def program(command):
        calls.append(command)
        return state["shortcut_code"]

    monkeypatch.setattr(shortcuts, "existing", existing)
    monkeypatch.setattr(update, "run_program", program)
    monkeypatch.setattr(update, "programs_in_use", lambda: state["busy"])
    return state, run_pip, calls


def item(place):
    return shortcuts.Shortcut("CSV Tidy", Path("x"), "", "", place, False)


def kinds(calls):
    """Each call as a short word: install, existing, shortcut, uninstall."""
    names = []
    for call in calls:
        if call == ["existing"]:
            names.append("existing")
        elif call[1:3] == ["-m", "datakrit"]:
            names.append("shortcut")
        else:
            names.append(call[3])
    return names


# --------------------------------------------------------------------- finding a release


def test_find_release_reads_the_wheel_and_its_published_hash(github):
    answers, _ = github
    answers[LATEST] = release_json("9.9.9")
    found = update.find_release()
    assert found.version == "9.9.9" and not found.switch
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


def test_before_the_rename_the_new_name_answers_404_and_the_old_one_answers(github):
    answers, asked = github
    answers[LATEST] = release_json("9.9.9")
    found = update.find_release()
    assert asked == [NEW_LATEST, LATEST]
    assert found.repository == OLD and not found.switch
    assert found.page_url == "https://github.com/JudikaM/csv-tidy/releases/tag/v9.9.9"


def test_after_the_rename_the_new_name_answers_first(github):
    answers, asked = github
    answers[NEW_LATEST] = release_json("2.0.0", repo=NEW, switch=True)
    answers[LATEST] = release_json("9.9.9")  # never asked
    found = update.find_release()
    assert asked == [NEW_LATEST]
    assert found.switch and found.repository == NEW and found.version == "2.0.0"
    assert found.wheel_name == "datakrit-2.0.0-py3-none-any.whl"
    assert found.wheel_url.startswith("https://github.com/JudikaM/datakrit/releases/download/")
    assert found.page_url == "https://github.com/JudikaM/datakrit/releases/tag/v2.0.0"


def test_a_csv_tidy_release_of_the_renamed_repository_is_a_normal_update(github):
    answers, _ = github
    answers[api(NEW, "tags/v1.1.1")] = release_json("1.1.1", repo=NEW)
    found = update.find_release("1.1.1")
    assert not found.switch and found.repository == NEW


def test_the_datakrit_wheel_is_preferred_when_a_release_carries_both(github):
    answers, _ = github
    both = release_json("2.0.0", repo=NEW, switch=True)
    both["assets"].append(release_json("2.0.0", repo=NEW)["assets"][1])
    answers[NEW_LATEST] = both
    assert update.find_release().wheel_name == "datakrit-2.0.0-py3-none-any.whl"


def test_github_has_no_release_only_when_every_repository_answers_404(github):
    _, asked = github
    with pytest.raises(CsvTidyError, match="GitHub has no a published release"):
        update.find_release()
    assert asked == [NEW_LATEST, LATEST]
    with pytest.raises(CsvTidyError, match=r"GitHub has no version 1\.2\.3"):
        update.find_release("1.2.3")
    assert asked[2:] == [api(NEW, "tags/v1.2.3"), api(OLD, "tags/v1.2.3")]


@pytest.mark.parametrize(
    "failure",
    [
        OSError("no route to host"),
        urllib.error.HTTPError(NEW_LATEST, 403, "rate limited", email.message.Message(), None),
        ValueError("not JSON"),
    ],
)
def test_any_other_failure_stops_without_asking_the_next_repository(github, failure):
    answers, asked = github
    answers[NEW_LATEST] = failure
    answers[LATEST] = release_json("9.9.9")
    with pytest.raises(CsvTidyError, match="could not reach GitHub") as caught:
        update.find_release()
    assert asked == [NEW_LATEST]
    assert "https://github.com/JudikaM/csv-tidy/releases" in str(caught.value)


@pytest.mark.parametrize(
    "final",
    [
        "https://example.com/repos/JudikaM/csv-tidy/releases/latest",
        "http://api.github.com/repos/JudikaM/csv-tidy/releases/latest",
        "https://api.github.com.example.com/releases/latest",
        "https://github.com/JudikaM/csv-tidy/releases/latest",
    ],
)
def test_an_answer_from_a_redirect_off_the_github_api_is_refused(github, final):
    answers, asked = github
    answers[LATEST] = (final, release_json("9.9.9"))
    with pytest.raises(CsvTidyError, match="unexpected address; nothing was installed"):
        update.find_release()
    assert asked == [NEW_LATEST, LATEST]


def test_a_redirect_within_the_github_api_is_followed(github):
    # GitHub answers the old name of a renamed repository with a redirect like this one.
    answers, _ = github
    answers[LATEST] = (
        "https://api.github.com/repositories/123456/releases/latest",
        release_json("2.0.0", repo=NEW, switch=True),
    )
    found = update.find_release()
    assert found.switch and found.repository == OLD
    assert found.page_url == "https://github.com/JudikaM/csv-tidy/releases/tag/v2.0.0"


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
        return Response(b'{"tag_name": "v1.0.0"}')

    monkeypatch.setattr(update.urllib.request, "urlopen", urlopen)
    final, data = update.fetch_json(LATEST)
    assert final == "https://api.github.com/repositories/1/releases/latest"
    assert data == {"tag_name": "v1.0.0"}
    assert seen == [(LATEST, f"csv-tidy/{__version__}", 30)]


@pytest.mark.parametrize("switch_release", [False, True])
@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/csv_tidy-9.9.9-py3-none-any.whl",
        "https://github.com/someone/csv-tidy/releases/download/v9.9.9/x.whl",
        "https://github.com/JudikaM/csv-tidy-evil/releases/download/v9.9.9/x.whl",
        "https://github.com/JudikaM/datakrit2/releases/download/v9.9.9/x.whl",
        "http://github.com/JudikaM/csv-tidy/releases/download/v9.9.9/x.whl",
        "https://github.com/JudikaM/csv-tidy/archive/v9.9.9.whl",
        "github.com/JudikaM/csv-tidy/releases/download/v9.9.9/x.whl",
    ],
)
def test_untrusted_download_addresses_are_refused(github, url, switch_release):
    answers, _ = github
    answers[LATEST] = release_json(url=url, switch=switch_release)
    with pytest.raises(CsvTidyError, match="unexpected address"):
        update.find_release()


def test_both_trusted_repositories_are_accepted_as_download_addresses(github):
    answers, _ = github
    url = "https://github.com/JudikaM/datakrit/releases/download/v9.9.9/csv_tidy.whl"
    answers[LATEST] = release_json(url=url)
    assert update.find_release().wheel_url == url


@pytest.mark.parametrize("switch_release", [False, True])
@pytest.mark.parametrize(
    "digest",
    [None, "", "md5:abc", "sha256:" + "A" * 64, "sha256:" + "a" * 63, "sha256:" + "g" * 64],
)
def test_missing_or_malformed_digests_are_refused(github, digest, switch_release):
    answers, _ = github
    answers[LATEST] = release_json(digest=digest, switch=switch_release)
    with pytest.raises(CsvTidyError, match="no SHA-256"):
        update.find_release()


@pytest.mark.parametrize(
    "broken, message",
    [
        (release_json(name="other.whl"), "no wheel named csv_tidy-9.9.9-py3-none-any.whl or"),
        (release_json(name="datakrit-9.9.8-py3-none-any.whl"), "no wheel"),
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
    url = api(OLD, "tags/v1.2.3")
    answers[url] = release_json("1.2.3")
    assert update.find_release("1.2.3").version == "1.2.3"
    assert update.find_release("v1.2.3").version == "1.2.3"
    assert asked == [api(NEW, "tags/v1.2.3"), url, api(NEW, "tags/v1.2.3"), url]


# ------------------------------------------------------------------- a normal update


def test_update_installs_a_newer_release_with_hash_checking(github, pip):
    answers, _ = github
    answers[LATEST] = release_json("9.9.9")
    _, calls = pip
    result = run_cli("update")
    assert result.code == 0, result.err
    assert len(calls) == 1 and calls[0][-1].endswith(f"#sha256={DIGEST}")
    assert calls[0][1:5] == ["-m", "pip", "install", "--upgrade"]
    assert f"from {__version__} to 9.9.9" in result.out
    assert "https://github.com/JudikaM/csv-tidy/releases/tag/v9.9.9" in result.out
    assert "Close CSV Tidy" in result.out and "Updated to 9.9.9" in result.out
    assert "Datakrit" not in result.out


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
    answers[api(OLD, "tags/v0.0.1")] = release_json("0.0.1")
    assert run_cli("update", "--version", "0.0.1").code == 0 and len(calls) == 1


def test_network_and_pip_failures_are_explained(github, pip):
    answers, _ = github
    answers[NEW_LATEST] = OSError("no route to host")
    offline = run_cli("update")
    assert offline.code == 2
    assert "could not reach GitHub" in offline.err and "pip install" in offline.err
    run, calls = pip
    del answers[NEW_LATEST]
    answers[LATEST] = release_json("9.9.9")
    run.returncodes["install"] = 1
    failed = run_cli("update")
    assert failed.code == 2 and "pip could not install" in failed.err and len(calls) == 1


def test_pause_waits_for_enter_so_a_shortcut_window_stays_readable(github, pip, monkeypatch):
    answers, _ = github
    answers[LATEST] = release_json(__version__)
    seen = []
    monkeypatch.setattr("builtins.input", lambda prompt="": seen.append(prompt) or "")
    assert run_cli("update", "--pause").code == 0
    assert seen and "Enter" in seen[0]
    answers[NEW_LATEST] = OSError("offline")
    assert run_cli("update", "--pause").code == 2 and len(seen) == 2


def test_only_the_update_command_uses_the_network(monkeypatch, examples):
    def refuse(url):
        raise AssertionError(f"unexpected network access: {url}")

    monkeypatch.setattr(update, "fetch_json", refuse)
    profile = str(examples / "profiles" / "transactions-id.toml")
    valid = str(examples / "transactions_valid.csv")
    assert run_cli("check", valid, "--profile", profile).code == 0


# ------------------------------------------------------------------- update --check


CHECK_CASES = {
    "before the rename, newer": (
        {LATEST: release_json("9.9.9")},
        0,
        ["Latest release: CSV Tidy 9.9.9 (from JudikaM/csv-tidy)", "9.9.9 is available"],
    ),
    "before the rename, up to date": (
        {LATEST: release_json(__version__)},
        0,
        ["CSV Tidy is up to date", "renamed to Datakrit (command `datakrit`)"],
    ),
    "after the rename, switch release": (
        {NEW_LATEST: release_json("2.0.0", repo=NEW, switch=True)},
        0,
        [
            "Latest release: Datakrit 2.0.0 (from JudikaM/datakrit)",
            "CSV Tidy is now called Datakrit. Datakrit 2.0.0 is available "
            "(https://github.com/JudikaM/datakrit/releases/tag/v2.0.0)",
            "`csv-tidy update` switches this installation to Datakrit",
            "the command is `datakrit` instead of `csv-tidy`",
            "Profiles keep working",
        ],
    ),
    "switch release through the redirect of the old name": (
        {
            LATEST: (
                "https://api.github.com/repositories/1/releases/latest",
                release_json("2.0.0", repo=NEW, switch=True),
            )
        },
        0,
        ["CSV Tidy is now called Datakrit", "/JudikaM/csv-tidy/releases/tag/v2.0.0"],
    ),
    "both 404": ({}, 2, ["GitHub has no a published release of CSV Tidy"]),
    "offline": ({NEW_LATEST: OSError("offline")}, 2, ["could not reach GitHub"]),
    "redirect off the API": (
        {LATEST: ("https://example.com/x", release_json("9.9.9"))},
        2,
        ["unexpected address"],
    ),
    "untrusted download": (
        {NEW_LATEST: release_json("2.0.0", url="https://example.com/d.whl", switch=True)},
        2,
        ["points its wheel to an unexpected address"],
    ),
    "missing digest": (
        {NEW_LATEST: release_json("2.0.0", digest=None, repo=NEW, switch=True)},
        2,
        ["no SHA-256"],
    ),
    "malformed digest": ({LATEST: release_json(digest="sha256:xyz")}, 2, ["no SHA-256"]),
}


@pytest.mark.parametrize("case", CHECK_CASES)
def test_check_only_reports_in_every_case(github, switch, case):
    answers, _ = github
    given, code, expected = CHECK_CASES[case]
    answers.update(given)
    _, _, calls = switch
    result = run_cli("update", "--check")
    assert result.code == code, result.err
    for text in expected:
        assert text in result.out + result.err
    assert calls == []


# ------------------------------------------------------------- the switch to Datakrit


@pytest.fixture
def switch_release(github):
    answers, _ = github
    answers[NEW_LATEST] = release_json("2.0.0", repo=NEW, switch=True)
    return answers


def test_switch_with_desktop_and_menu_shortcuts(switch_release, switch):
    state, _, calls = switch
    state["found"] = [item("desktop"), item("menu")]
    result = run_cli("update")
    assert result.code == 0, result.err
    assert kinds(calls) == ["install", "existing", "shortcut", "uninstall"]
    install, _, shortcut, uninstall = calls
    assert install[1:5] == ["-m", "pip", "install", "--upgrade"]
    assert install[-1] == (
        "https://github.com/JudikaM/datakrit/releases/download/v2.0.0/"
        f"datakrit-2.0.0-py3-none-any.whl#sha256={DIGEST}"
    )
    assert shortcut == [sys.executable, "-m", "datakrit", "shortcut", "install"]
    assert uninstall == [sys.executable, "-m", "pip", "uninstall", "-y", "csv-tidy"]
    out = result.out
    for text in (
        "CSV Tidy is now called Datakrit",
        "https://github.com/JudikaM/datakrit/releases/tag/v2.0.0",
        "Step 1 of 3 done: Datakrit 2.0.0 is installed",
        "Step 2 of 3 done: the shortcuts now start Datakrit",
        f"Step 3 of 3 done: CSV Tidy {__version__} was removed",
        'Next: start Datakrit with the "Datakrit" icon or `datakrit ui`',
    ):
        assert text in out
    assert out.index("Step 1 of 3 done") < out.index("Step 2 of 3 done") < out.index("Next:")


def test_switch_without_a_desktop_shortcut_adds_no_desktop(switch_release, switch):
    state, _, calls = switch
    state["found"] = [item("menu")]
    assert run_cli("update").code == 0
    assert calls[2] == [sys.executable, "-m", "datakrit", "shortcut", "install", "--no-desktop"]


def test_switch_without_old_shortcuts_makes_none(switch_release, switch):
    _, _, calls = switch
    result = run_cli("update")
    assert result.code == 0, result.err
    assert kinds(calls) == ["install", "existing", "uninstall"]
    assert "has no CSV Tidy shortcuts, so none were replaced" in result.out
    assert "To add Datakrit icons: datakrit shortcut install" in result.out


def test_switch_failing_to_install_datakrit_changes_nothing_else(switch_release, switch):
    state, run_pip, calls = switch
    state["found"] = [item("desktop")]
    run_pip.returncodes["install"] = 1
    result = run_cli("update")
    assert result.code == 2
    assert kinds(calls) == ["install"]
    assert "pip could not install Datakrit 2.0.0" in result.err
    assert f"CSV Tidy {__version__} is still installed and nothing else was changed" in result.err
    assert "Step 2" not in result.out and "Next:" not in result.out


def test_switch_failing_to_make_shortcuts_keeps_csv_tidy(switch_release, switch):
    state, _, calls = switch
    state["found"] = [item("desktop"), item("menu")]
    state["shortcut_code"] = 3
    result = run_cli("update")
    assert result.code == 2
    assert kinds(calls) == ["install", "existing", "shortcut"]
    command = update.shown([sys.executable, "-m", "datakrit", "shortcut", "install"])
    assert (
        f"could not make its shortcuts (exit code 3). Run this command to finish it: {command}"
        in (result.err)
    )
    remove = update.shown([sys.executable, "-m", "pip", "uninstall", "-y", "csv-tidy"])
    assert "Step 3 of 3 skipped" in result.out and remove in result.out
    assert "Next: start Datakrit" in result.out


def test_switch_that_cannot_look_for_shortcuts_keeps_csv_tidy(switch_release, switch):
    state, _, calls = switch
    state["find_error"] = CsvTidyError("Windows could not make the shortcuts")
    result = run_cli("update")
    assert result.code == 2
    assert kinds(calls) == ["install", "existing"]
    assert "could not look for CSV Tidy shortcuts" in result.err
    assert update.shown([sys.executable, "-m", "datakrit", "shortcut", "install"]) in result.err
    assert "Step 3 of 3 skipped" in result.out


def test_switch_failing_to_remove_csv_tidy_prints_the_command(switch_release, switch):
    _, run_pip, calls = switch
    run_pip.returncodes["uninstall"] = 1
    result = run_cli("update")
    assert result.code == 2
    assert kinds(calls) == ["install", "existing", "uninstall"]
    remove = update.shown([sys.executable, "-m", "pip", "uninstall", "-y", "csv-tidy"])
    assert "pip could not remove CSV Tidy (exit code 1); Datakrit is installed" in result.err
    assert f"Run this command to finish it: {remove}" in result.err
    assert "Next: start Datakrit" in result.out


def test_switch_while_csv_tidy_runs_prints_the_remove_command(switch_release, switch):
    state, _, calls = switch
    state["busy"] = [Path("C:/venv/Scripts/csv-tidy.exe")]
    result = run_cli("update")
    assert result.code == 0, result.err
    assert kinds(calls) == ["install", "existing"]
    remove = update.shown([sys.executable, "-m", "pip", "uninstall", "-y", "csv-tidy"])
    assert "CSV Tidy cannot be removed while it runs (csv-tidy.exe)" in result.out
    assert f"close the interface if it is open), remove it with: {remove}" in result.out


def test_switch_to_a_chosen_version(github, switch):
    answers, _ = github
    answers[api(NEW, "tags/v2.0.0")] = release_json("2.0.0", repo=NEW, switch=True)
    _, _, calls = switch
    result = run_cli("update", "--version", "2.0.0")
    assert result.code == 0, result.err
    assert kinds(calls) == ["install", "existing", "uninstall"]


def test_commands_are_shown_as_they_can_be_pasted():
    spaced = ["C:\\Program Files\\Python\\python.exe", "-m", "pip", "uninstall", "-y", "csv-tidy"]
    assert update.shown(spaced, platform="win32") == (
        '& "C:\\Program Files\\Python\\python.exe" -m pip uninstall -y csv-tidy'
    )
    plain = ["D:\\venv\\Scripts\\python.exe", "-m", "datakrit", "shortcut", "install"]
    assert update.shown(plain, platform="win32") == (
        "D:\\venv\\Scripts\\python.exe -m datakrit shortcut install"
    )
    assert update.shown(["/opt/my env/bin/python", "-m", "pip"], platform="linux") == (
        "'/opt/my env/bin/python' -m pip"
    )


def test_no_program_counts_as_running_outside_windows(monkeypatch):
    monkeypatch.setattr(update.sys, "platform", "linux")
    assert update.programs_in_use() == []


def test_the_test_run_itself_uses_no_csv_tidy_program():
    # pytest runs under python, not under csv-tidy.exe, so nothing of CSV Tidy is busy.
    assert update.programs_in_use() == []


# ------------------------------------------------- local pip checks with a dummy wheel


DUMMY_MAIN = """\
import sys

def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    print("datakrit dummy:", " ".join(args))
    return 0 if args[:2] == ["shortcut", "install"] else 2

if __name__ == "__main__":
    sys.exit(main())
"""


def build_dummy_datakrit(folder: Path, version: str = "2.0.0") -> Path:
    """A minimal, valid ``datakrit`` wheel: a module with ``python -m datakrit``."""
    info = f"datakrit-{version}.dist-info"
    files = {
        "datakrit/__init__.py": f'__version__ = "{version}"\n',
        "datakrit/__main__.py": DUMMY_MAIN,
        f"{info}/METADATA": f"Metadata-Version: 2.1\nName: datakrit\nVersion: {version}\n",
        f"{info}/WHEEL": (
            "Wheel-Version: 1.0\nGenerator: csv-tidy-tests\nRoot-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ),
        f"{info}/entry_points.txt": "[console_scripts]\ndatakrit = datakrit.__main__:main\n",
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


def local_release(wheel: Path, sha256: str) -> update.Release:
    return update.Release("2.0.0", "", wheel.name, wheel.resolve().as_uri(), sha256, NEW)


def pip_into(command, target):
    """The update's pip command, kept offline and confined to ``target``."""
    full = [*command, "--no-index", "--no-deps", "--target", str(target), "--quiet"]
    env = {**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    return subprocess.run(full, capture_output=True, text=True, env=env, check=False)


def test_pip_installs_the_datakrit_wheel_only_with_its_hash(tmp_path):
    wheel = build_dummy_datakrit(tmp_path)
    good = hashlib.sha256(wheel.read_bytes()).hexdigest()
    refused = pip_into(
        update.pip_command(local_release(wheel, "0" * 64), sys.executable), tmp_path / "bad"
    )
    assert refused.returncode != 0
    assert "hash" in (refused.stdout + refused.stderr).lower()
    assert not (tmp_path / "bad" / "datakrit").exists()
    target = tmp_path / "good"
    done = pip_into(update.pip_command(local_release(wheel, good), sys.executable), target)
    assert done.returncode == 0, done.stderr
    assert (target / "datakrit" / "__main__.py").exists()
    # The switch's step 2 command reaches Datakrit's own shortcut command.
    for desktop, shown_args in (
        (True, "shortcut install"),
        (False, "shortcut install --no-desktop"),
    ):
        command = update.shortcut_command(sys.executable, desktop)
        env = {**os.environ, "PYTHONPATH": str(target)}
        ran = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
        assert ran.returncode == 0 and f"datakrit dummy: {shown_args}" in ran.stdout
