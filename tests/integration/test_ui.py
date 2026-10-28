"""The local interface server: same pipeline as the CLI, loopback only, token protected."""

import io
import json
import re
import shutil
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import quote, urlsplit

import pytest
from conftest import EXAMPLES, run_cli, sha256

from csv_tidy import check_file, clean_file, load_profile
from csv_tidy.reporting import check_report, clean_report
from csv_tidy.schema import profile_to_dict
from csv_tidy.ui import TOKEN_HEADER, create_server

ID_PROFILE = EXAMPLES / "profiles" / "transactions-id.toml"
FIXABLE = EXAMPLES / "transactions_fixable.csv"
UNFIXABLE = EXAMPLES / "transactions_unfixable.csv"


class Client:
    def __init__(self, url: str):
        parts = urlsplit(url)
        self.base = f"http://{parts.netloc}"
        self.page_url = url
        self.token = parts.query.removeprefix("token=")

    def request(self, path, data=None, headers=None, method=None):
        request = urllib.request.Request(self.base + path, data=data, method=method)
        for name, value in (headers or {}).items():
            request.add_header(name, value)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def post(self, path, body, token=True, headers=None):
        send = {"Content-Type": "application/json", **(headers or {})}
        if token:
            send[TOKEN_HEADER] = self.token
        status, _, data = self.request(path, json.dumps(body).encode(), send)
        return status, json.loads(data)

    def upload(self, path: Path, name=None, append=False):
        headers = {
            TOKEN_HEADER: self.token,
            "Content-Type": "application/octet-stream",
            "X-File-Name": quote(name or path.name),
        }
        target = "/api/file?mode=append" if append else "/api/file"
        status, _, data = self.request(target, path.read_bytes(), headers)
        assert status == 200, data
        return json.loads(data)

    def download(self, body):
        headers = {"Content-Type": "application/json", TOKEN_HEADER: self.token}
        return self.request("/api/download", json.dumps(body).encode(), headers)


@pytest.fixture
def ui():
    server, session, url = create_server(0, max_file_mb=1)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield Client(url)
    server.shutdown()
    server.server_close()
    session.close()
    thread.join(5)


def profile_dict(path=ID_PROFILE):
    return profile_to_dict(load_profile(path))


def test_page_is_self_contained_and_needs_the_key(ui):
    status, headers, body = ui.request(ui.page_url.removeprefix(ui.base))
    page = body.decode("utf-8")
    assert status == 200 and ui.token in page
    assert "default-src 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Frame-Options"] == "DENY" and headers["Cache-Control"] == "no-store"
    paths = ("/app.css", "/app.js", "/theme.js")
    assets = [ui.request(path)[2].decode("utf-8") for path in paths]
    for text in (page, *assets):
        assert not re.search(r"(https?:)?//(?!127\.0\.0\.1)[\w.-]+\.\w+", text), "external URL"
    for script in assets[1:]:
        assert "innerHTML" not in script and "eval(" not in script
    # The content security policy allows no inline styles or event handlers.
    assert not re.search(r'\sstyle="|\son[a-z]+="', page)
    assert "<script>" not in page and "<style" not in page
    assert re.findall(r'<(?:script|link)[^>]+(?:src|href)="([^"]+)"', page) == [
        "data:,",
        "app.css",
        "theme.js",
        "app.js",
    ]
    assert ui.request("/")[0] == 403 and ui.request("/?token=wrong")[0] == 403
    assert ui.request("/../pyproject.toml")[0] == 404


def test_server_listens_on_loopback_only(ui):
    assert urlsplit(ui.base).hostname == "127.0.0.1"


def test_requests_without_the_key_or_from_other_origins_are_refused(ui):
    loaded = ui.upload(FIXABLE)
    body = {"file_id": loaded["file_id"], "delimiter": ";", "encoding": "utf-8"}
    assert ui.post("/api/preview", body, token=False)[0] == 403
    status, _, _ = ui.request("/api/preview", json.dumps(body).encode(), {TOKEN_HEADER: "x" * 43})
    assert status == 403
    assert ui.post("/api/preview", body, headers={"Origin": "http://evil.example"})[0] == 403
    assert ui.post("/api/preview", body, headers={"Host": "evil.example"})[0] == 403
    status, _, _ = ui.request(
        "/api/preview",
        json.dumps(body).encode(),
        {TOKEN_HEADER: ui.token, "Content-Type": "text/plain"},
    )
    assert status == 415  # a cross-site form cannot send JSON
    assert ui.request("/api/preview", headers={TOKEN_HEADER: ui.token})[0] == 404  # GET
    assert ui.post("/api/preview", body)[0] == 200


def test_refused_requests_with_a_body_still_get_their_answer(ui):
    """Regression for #23: a refusal closed the connection with the request body unread, and
    the reset that this causes could reach the client before the answer."""
    body = json.dumps({"padding": "x" * 200_000}).encode()
    cases = [
        ({"Content-Type": "application/json"}, 403),  # no session key
        (
            {"Content-Type": "application/json", TOKEN_HEADER: ui.token, "Origin": "http://x.test"},
            403,
        ),
        ({"Content-Type": "text/plain", TOKEN_HEADER: ui.token}, 415),
    ]
    for _ in range(30):  # the reset is a race; repeat so that it would show
        for headers, expected in cases:
            status, _, data = ui.request("/api/preview", body, headers)
            assert status == expected and "error" in json.loads(data)


def test_preview_shows_rows_and_never_guesses_the_delimiter(ui):
    loaded = ui.upload(FIXABLE)
    status, wrong = ui.post("/api/preview", {"file_id": loaded["file_id"], "delimiter": ","})
    assert status == 200 and len(wrong["header"]) == 1
    assert wrong["report"]["issues"][0]["code"] == "possible_wrong_delimiter"
    status, data = ui.post("/api/preview", {"file_id": loaded["file_id"], "delimiter": ";"})
    assert data["header"] == ["transaction_id", "customer_id", "amount", "date", "note"]
    assert data["rows"][1] == {
        "record": 2,
        "fields": ["TX-002", "00456", " 980,00 ", "15/02/2026", "Paid in  two parts"],
        "changed": [],
    }
    assert data["report"]["coverage"]["scope"] == "structure_only"
    assert data["report"]["source"]["path"] == "transactions_fixable.csv"


def test_preview_reads_tab_separated_files(ui, tmp_path):
    tsv = tmp_path / "people.tsv"
    tsv.write_text("id\tname\n1\tAda\n", encoding="utf-8")
    loaded = ui.upload(tsv)
    status, data = ui.post("/api/preview", {"file_id": loaded["file_id"], "delimiter": "\t"})
    assert status == 200 and data["header"] == ["id", "name"]
    assert data["rows"][0]["fields"] == ["1", "Ada"]


def test_check_and_clean_match_the_library_results(ui):
    loaded = ui.upload(FIXABLE)
    body = {"file_id": loaded["file_id"], "profile": profile_dict()}
    status, checked = ui.post("/api/check", body)
    assert status == 200
    profile = load_profile(ID_PROFILE)
    expected = check_report(check_file(FIXABLE, profile), 200)
    for key in ("scan", "summary", "issues", "coverage", "details"):
        assert checked["report"][key] == expected[key]
    status, cleaned = ui.post("/api/clean", body)
    expected = clean_report(clean_file(FIXABLE, profile), "dry-run", 200, 200)
    for key in ("scan", "summary", "changes", "source_issues", "output_issues", "transformations"):
        assert cleaned["report"][key] == expected[key]
    assert cleaned["blocked_reason"] is None
    assert cleaned["rows"][1]["fields"][2] == "980.00" and cleaned["rows"][1]["changed"] == [2, 3]


def test_interface_profiles_can_neutralize_formulas(ui, tmp_path):
    source = tmp_path / "notes.csv"
    source.write_text("id,note\n1,=HYPERLINK(1)\n2,plain\n", encoding="utf-8")
    loaded = ui.upload(source)
    profile = {
        "schema_version": 1,
        "source": {"delimiter": ","},
        "transform": {"neutralize_formulas": ["note"]},
    }
    status, cleaned = ui.post("/api/clean", {"file_id": loaded["file_id"], "profile": profile})
    assert status == 200, cleaned
    assert cleaned["rows"][0]["fields"] == ["1", "'=HYPERLINK(1)"]
    assert cleaned["rows"][0]["changed"] == [1]
    assert cleaned["report"]["transformations"]["neutralize_formulas"] == ["note"]


def test_downloads_equal_the_cli_export(ui, tmp_path):
    loaded = ui.upload(FIXABLE)
    profile = profile_dict()
    _, cleaned = ui.post("/api/clean", {"file_id": loaded["file_id"], "profile": profile})
    out, schema = tmp_path / "cli.csv", tmp_path / "cli.toml"
    cli = run_cli(
        "clean",
        str(FIXABLE),
        "--schema",
        str(ID_PROFILE),
        "--apply",
        "--output",
        str(out),
        "--output-schema",
        str(schema),
    )
    assert cli.code == 0
    base = {"result_id": cleaned["result_id"], "profile": profile}
    status, headers, data = ui.download({**base, "kind": "csv"})
    assert status == 200 and data == out.read_bytes()
    assert headers["X-File-Name"] == "transactions_fixable.clean.csv"
    status, _, data = ui.download({**base, "kind": "output-profile"})
    assert status == 200
    saved = tmp_path / "ui.toml"
    saved.write_bytes(data)
    assert load_profile(saved) == load_profile(schema)
    status, _, data = ui.download({**base, "kind": "report-json"})
    report = json.loads(data)
    assert report["command"] == "clean" and report["summary"]["status"] == "ready"
    status, _, data = ui.download({**base, "kind": "report-text"})
    assert data.decode("utf-8").splitlines()[1].startswith("Verdict: READY TO EXPORT")


def test_blocked_and_incomplete_results_cannot_be_downloaded_as_csv(ui, write):
    loaded = ui.upload(UNFIXABLE)
    profile = profile_dict()
    _, cleaned = ui.post("/api/clean", {"file_id": loaded["file_id"], "profile": profile})
    assert cleaned["report"]["summary"]["status"] == "blocked"
    assert "3 output error(s) remain" in cleaned["blocked_reason"]
    base = {"result_id": cleaned["result_id"], "profile": profile}
    for kind in ("csv", "output-profile"):
        status, _, data = ui.download({**base, "kind": kind})
        assert status == 409 and "Saving is blocked" in json.loads(data)["error"]
    assert ui.download({**base, "kind": "report-text"})[0] == 200  # reports stay available

    loaded = ui.upload(write("bad.csv", b"a,b\n1,2\n3,\xff\n"))
    plain = {"schema_version": 1}
    _, cleaned = ui.post("/api/clean", {"file_id": loaded["file_id"], "profile": plain})
    assert cleaned["report"]["summary"]["status"] == "incomplete"
    assert "scan is incomplete" in cleaned["blocked_reason"]
    status, _, data = ui.download(
        {"result_id": cleaned["result_id"], "profile": plain, "kind": "csv"}
    )
    assert status == 409 and "scan is incomplete" in json.loads(data)["error"]


def test_results_go_stale_when_the_file_or_settings_change(ui):
    first = ui.upload(FIXABLE)
    profile = profile_dict()
    _, cleaned = ui.post("/api/clean", {"file_id": first["file_id"], "profile": profile})
    changed = {**profile, "transform": {**profile["transform"], "trim": []}}
    status, _, data = ui.download(
        {"result_id": cleaned["result_id"], "profile": changed, "kind": "csv"}
    )
    assert status == 409 and "settings changed" in json.loads(data)["error"]
    ui.upload(FIXABLE)  # choosing a file again replaces the earlier one and its results
    status, _, _ = ui.download(
        {"result_id": cleaned["result_id"], "profile": profile, "kind": "csv"}
    )
    assert status == 409
    status, data = ui.post("/api/check", {"file_id": first["file_id"], "profile": profile})
    assert status == 409 and "Choose the file again" in data["error"]


def test_invalid_settings_and_profiles_are_explained(ui):
    loaded = ui.upload(FIXABLE)
    bad = {"schema_version": 1, "source": {"delimiter": ";", "date_format": "dd/mm"}}
    status, data = ui.post("/api/check", {"file_id": loaded["file_id"], "profile": bad})
    assert status == 400 and "date_format" in data["error"]
    status, data = ui.post("/api/preview", {"file_id": loaded["file_id"], "encoding": "nope"})
    assert status == 400 and "unknown encoding" in data["error"]
    status, data = ui.post("/api/profile/parse", {"text": "schema_version = ", "name": "p.toml"})
    assert status == 400 and "not a valid profile file" in data["error"]
    status, data = ui.post(
        "/api/profile/parse", {"text": "schema_version = 1\n[source]\ndelimter = ';'\n"}
    )
    assert status == 400 and "did you mean 'delimiter'" in data["error"]
    status, data = ui.post("/api/profile/parse", {"text": ID_PROFILE.read_text(encoding="utf-8")})
    assert status == 200 and data["profile"] == profile_dict()


def test_rules_saved_from_the_page_work_with_the_cli(ui, tmp_path):
    headers = {"Content-Type": "application/json", TOKEN_HEADER: ui.token}
    body = {"profile": profile_dict(), "file_name": "transactions_fixable.csv"}
    status, response, data = ui.request("/api/profile/toml", json.dumps(body).encode(), headers)
    assert status == 200 and response["X-File-Name"] == "transactions_fixable.profile.toml"
    saved = tmp_path / "saved.toml"
    saved.write_bytes(data)
    result = run_cli("check", str(FIXABLE), "--schema", str(saved), "--format", "json")
    assert result.code == 1 and json.loads(result.out)["summary"]["errors"] == 2


def test_uploads_are_private_copies_with_safe_names_and_a_size_limit(ui, write):
    digest = sha256(FIXABLE)
    loaded = ui.upload(FIXABLE, name="..\\..\\evil/../<b>x.csv")
    assert loaded["name"] == "_b_x.csv"
    ui.post("/api/clean", {"file_id": loaded["file_id"], "profile": profile_dict()})
    assert sha256(FIXABLE) == digest
    big = write("big.csv", b"a\n" + b"x" * (1024 * 1024 + 1))
    headers = {TOKEN_HEADER: ui.token, "Content-Type": "application/octet-stream"}
    try:
        status, _, data = ui.request("/api/file", big.read_bytes(), headers)
    except (urllib.error.URLError, ConnectionError):
        return  # the server closed the connection without reading the oversized body
    assert status == 413 and "limit of 1 MB" in json.loads(data)["error"]


def test_html_in_data_is_returned_as_plain_json_text(ui, write):
    loaded = ui.upload(write("x.csv", 'name\n"<img src=x onerror=alert(1)>"\n'))
    _, headers, data = ui.request(
        "/api/preview",
        json.dumps({"file_id": loaded["file_id"]}).encode(),
        {"Content-Type": "application/json", TOKEN_HEADER: ui.token},
    )
    assert headers["Content-Type"] == "application/json"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert json.loads(data)["rows"][0]["fields"] == ["<img src=x onerror=alert(1)>"]


def test_quit_stops_the_server_and_removes_the_temporary_copies():
    server, session, url = create_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = Client(url)
    client.upload(FIXABLE)
    folder = session._dir
    assert any(folder.iterdir())
    assert client.post("/api/quit", {}) == (200, {"stopped": True})
    thread.join(5)
    assert not thread.is_alive()
    server.server_close()
    session.close()
    assert not folder.exists()


def test_ui_command_is_documented_and_rejects_a_bad_port():
    text = run_cli("ui", "--help").out
    assert "127.0.0.1" in text and "--no-browser" in text
    assert run_cli("ui", "--port", "70000").code == 2


# --------------------------------------------------------------------------- 0.3.0: batch


@pytest.fixture
def batch_files(ui, write):
    """Four uploads in this order: ready, blocked, ready, unreadable."""
    bad = write("bad.csv", b"transaction_id;customer_id;amount;date;note\nTX-1;0;1,00;\xff\n")
    loaded = [ui.upload(FIXABLE)]
    loaded.append(ui.upload(UNFIXABLE, append=True))
    loaded.append(ui.upload(EXAMPLES / "transactions_valid.csv", append=True))
    loaded.append(ui.upload(bad, append=True))
    return [item["file_id"] for item in loaded]


def run_ui_batch(ui, ids, action="clean", profile=None, limits=None):
    body = {"action": action, "file_ids": ids, "profile": profile or profile_dict()}
    if limits is not None:
        body["limits"] = limits
    return ui.post("/api/batch", body)


def test_batch_gives_each_file_its_own_status_like_the_cli(ui, batch_files, tmp_path):
    status, data = run_ui_batch(ui, batch_files)
    assert status == 200, data
    report = data["report"]
    assert report["command"] == "batch" and report["action"] == "clean"
    assert [(f["path"], f["status"], f["exit_code"]) for f in report["files"]] == [
        ("transactions_fixable.csv", "ready", 0),
        ("transactions_unfixable.csv", "blocked", 1),
        ("transactions_valid.csv", "ready", 0),
        ("bad.csv", "incomplete", 2),
    ]
    assert "decode_error" in report["files"][3]["error"]
    assert report["summary"]["exit_code"] == 2
    assert report["totals"]["files"] == 4 and report["totals"]["failed"] == 1
    assert [f["file_id"] for f in data["files"]] == batch_files

    folder = tmp_path / "same"
    folder.mkdir()
    for name in (
        "transactions_fixable.csv",
        "transactions_unfixable.csv",
        "transactions_valid.csv",
    ):
        shutil.copy(EXAMPLES / name, folder / name)
    cli = json.loads(
        run_cli("batch", "clean", str(folder), "--schema", str(ID_PROFILE), "--format", "json").out
    )
    pick = ("status", "exit_code", "data_records", "errors", "output_errors", "changed_fields")
    by_name = {Path(f["path"]).name: {k: f[k] for k in pick} for f in cli["files"]}
    for entry in report["files"][:3]:
        assert {k: entry[k] for k in pick} == by_name[entry["path"]]


def test_batch_file_details_equal_the_single_file_result(ui, batch_files):
    _, data = run_ui_batch(ui, batch_files)
    body = {"batch_id": data["batch_id"], "file_id": batch_files[1], "profile": profile_dict()}
    status, detail = ui.post("/api/batch/file", body)
    assert status == 200, detail
    expected = clean_report(clean_file(UNFIXABLE, load_profile(ID_PROFILE)), "dry-run", 200, 200)
    for key in ("summary", "output_issues", "changes"):
        assert detail["report"][key] == expected[key]
    assert detail["report"]["source"]["path"] == "transactions_unfixable.csv"
    assert "3 output error(s) remain" in detail["blocked_reason"]


def test_batch_zip_holds_only_exportable_files_and_matches_the_cli(ui, batch_files, tmp_path):
    _, data = run_ui_batch(ui, batch_files)
    base = {"batch_id": data["batch_id"], "profile": profile_dict()}
    status, headers, payload = ui.download({**base, "kind": "batch-zip"})
    assert status == 200 and headers["X-File-Name"] == "csv-tidy-batch.zip"
    archive = zipfile.ZipFile(io.BytesIO(payload))
    assert sorted(archive.namelist()) == [
        "bad.report.json",
        "batch-summary.json",
        "batch-summary.txt",
        "transactions_fixable.clean.csv",
        "transactions_fixable.output.toml",
        "transactions_fixable.report.json",
        "transactions_unfixable.report.json",
        "transactions_valid.clean.csv",
        "transactions_valid.output.toml",
        "transactions_valid.report.json",
    ]
    out = tmp_path / "cli.csv"
    assert (
        run_cli(
            "clean", str(FIXABLE), "--schema", str(ID_PROFILE), "--apply", "--output", str(out)
        ).code
        == 0
    )
    assert archive.read("transactions_fixable.clean.csv") == out.read_bytes()
    summary = json.loads(archive.read("batch-summary.json"))
    assert [f["status"] for f in summary["files"]] == ["ready", "blocked", "ready", "incomplete"]
    blocked = json.loads(archive.read("transactions_unfixable.report.json"))
    assert blocked["summary"]["status"] == "blocked"
    assert "Verdict: 2 of 4 files need attention" in archive.read("batch-summary.txt").decode()


def test_batch_single_downloads_respect_the_export_gate(ui, batch_files):
    _, data = run_ui_batch(ui, batch_files)
    base = {"batch_id": data["batch_id"], "profile": profile_dict(), "kind": "batch-csv"}
    status, headers, payload = ui.download({**base, "file_id": batch_files[0]})
    assert status == 200 and headers["X-File-Name"] == "transactions_fixable.clean.csv"
    for blocked in batch_files[1], batch_files[3]:
        status, _, payload = ui.download({**base, "file_id": blocked})
        assert status == 409 and "Saving is blocked" in json.loads(payload)["error"]
    status, _, payload = ui.download({**base, "kind": "batch-summary-text"})
    assert status == 200 and payload.decode().splitlines()[1].startswith("Verdict:")


def test_batch_check_mode_and_rules_missing_columns(ui, batch_files):
    _, data = run_ui_batch(ui, batch_files[:3], action="check")
    assert [f["status"] for f in data["report"]["files"]] == ["invalid", "invalid", "valid"]
    status, _, payload = ui.download(
        {"batch_id": data["batch_id"], "profile": profile_dict(), "kind": "batch-zip"}
    )
    assert status == 200
    names = sorted(zipfile.ZipFile(io.BytesIO(payload)).namelist())
    assert not any(name.endswith(".clean.csv") for name in names)


def test_batch_refuses_duplicate_names_and_goes_stale(ui, batch_files, write):
    twin = write("other/transactions_fixable.csv", FIXABLE.read_bytes())
    extra = ui.upload(twin, append=True)["file_id"]
    status, data = run_ui_batch(ui, [*batch_files, extra])
    assert status == 400 and "same name" in data["error"]

    _, data = run_ui_batch(ui, batch_files)
    changed = profile_dict()
    changed["transform"]["trim"] = []
    status, _, payload = ui.download(
        {"batch_id": data["batch_id"], "profile": changed, "kind": "batch-zip"}
    )
    assert status == 409 and "settings changed" in json.loads(payload)["error"]
    assert ui.post("/api/file/remove", {"file_id": batch_files[2]}) == (200, {"removed": True})
    status, _, _ = ui.download(
        {"batch_id": data["batch_id"], "profile": profile_dict(), "kind": "batch-zip"}
    )
    assert status == 409
    status, data = run_ui_batch(ui, batch_files)
    assert status == 409 and "no longer loaded" in data["error"]
    ui.upload(FIXABLE)  # one-file mode replaces the whole selection
    status, data = run_ui_batch(ui, batch_files[:1])
    assert status == 409


def test_batch_request_validation(ui, batch_files):
    assert run_ui_batch(ui, [])[0] == 400
    assert run_ui_batch(ui, batch_files, action="delete")[0] == 400
    assert run_ui_batch(ui, ["x"])[0] == 409


# --------------------------------------------------------------------------- 0.3.0: limits


def test_report_and_preview_limits_are_honored_and_validated(ui):
    loaded = ui.upload(UNFIXABLE)
    limits = {"max_details": 1, "max_examples": 1, "preview_rows": 2}
    status, data = ui.post(
        "/api/preview", {"file_id": loaded["file_id"], "delimiter": ";", "limits": limits}
    )
    assert status == 200 and len(data["rows"]) == 2 and data["rows_total"] == 4
    body = {"file_id": loaded["file_id"], "profile": profile_dict(), "limits": limits}
    _, checked = ui.post("/api/check", body)
    assert len(checked["report"]["issues"]) == 1
    assert checked["report"]["details"] == {"limit": 1, "total": 3, "shown": 1, "truncated": True}
    _, cleaned = ui.post("/api/clean", body)
    assert len(cleaned["report"]["changes"]["examples"]) == 1
    assert cleaned["report"]["changes"]["changed_fields"] == 6
    assert len(cleaned["rows"]) == 2
    status, _, payload = ui.download(
        {
            "result_id": checked["result_id"],
            "profile": profile_dict(),
            "limits": limits,
            "kind": "check-report-json",
        }
    )
    assert status == 200 and len(json.loads(payload)["issues"]) == 1
    status, _, payload = ui.download(
        {"result_id": checked["result_id"], "profile": profile_dict(), "kind": "check-report-json"}
    )
    assert status == 409  # different limits than the result was made with
    for bad in (
        {"max_details": -1},
        {"max_examples": "many"},
        {"preview_rows": 0},
        {"preview_rows": 5000},
    ):
        status, data = ui.post("/api/check", {**body, "limits": bad})
        assert status == 400 and next(iter(bad)) in data["error"]


def test_default_limits_are_unchanged(ui):
    loaded = ui.upload(FIXABLE)
    _, data = ui.post("/api/preview", {"file_id": loaded["file_id"], "delimiter": ";"})
    assert data["report"]["details"]["limit"] == 200


# --------------------------------------------------------------------------- 0.3.0: field limit


def test_max_field_chars_applies_to_preview_check_and_saved_profiles(ui, write, tmp_path):
    loaded = ui.upload(write("long.csv", "id,note\n1," + "x" * 12 + "\n"))
    status, data = ui.post("/api/preview", {"file_id": loaded["file_id"], "max_field_chars": 10})
    assert status == 200
    assert data["report"]["scan"]["fatal_error"]["code"] == "field_too_large"
    assert ui.post("/api/preview", {"file_id": loaded["file_id"], "max_field_chars": 12})[1][
        "report"
    ]["scan"]["complete"]
    status, data = ui.post("/api/preview", {"file_id": loaded["file_id"], "max_field_chars": 0})
    assert status == 400 and "max_field_chars" in data["error"]
    profile = {"schema_version": 1, "source": {"max_field_chars": 10}}
    _, checked = ui.post("/api/check", {"file_id": loaded["file_id"], "profile": profile})
    assert checked["report"]["scan"]["complete"] is False
    headers = {"Content-Type": "application/json", TOKEN_HEADER: ui.token}
    body = json.dumps({"profile": profile, "file_name": "long.csv"}).encode()
    _, _, saved = ui.request("/api/profile/toml", body, headers)
    target = tmp_path / "saved.toml"
    target.write_bytes(saved)
    assert load_profile(target).max_field_chars == 10


# --------------------------------------------------------------------------- 0.4.0: no console


def serve(max_file_mb=1):
    server, session, url = create_server(0, max_file_mb=max_file_mb)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, session, Client(url), thread


def test_idle_server_stops_by_itself_and_contact_keeps_it_running():
    from csv_tidy.ui import start_idle_watch

    server, session, client, thread = serve()
    start_idle_watch(server, session, 0.8)
    for _ in range(8):  # the page checks in regularly: the server stays up
        assert client.post("/api/ping", {}) == (200, {"ok": True})
        thread.join(0.2)
    assert thread.is_alive()
    thread.join(5)  # no contact any more: it stops
    assert not thread.is_alive()
    server.server_close()
    session.close()


def test_requests_without_the_key_do_not_keep_the_server_alive():
    server, session, client, thread = serve()
    before = session.last_contact
    thread.join(0.05)
    assert client.post("/api/ping", {}, token=False)[0] == 403
    assert client.request("/?token=wrong")[0] == 403
    assert client.request("/app.js")[0] == 200  # static files need no key and are no contact
    assert session.last_contact == before
    assert client.post("/api/ping", {})[0] == 200
    assert session.last_contact > before
    server.shutdown()
    server.server_close()
    session.close()


def test_run_ui_with_idle_minutes_returns_and_cleans_up(monkeypatch):
    import csv_tidy.ui as ui_module

    made = []
    real = ui_module.create_server

    def spy(*args, **kwargs):
        made.append(real(*args, **kwargs))
        return made[-1]

    monkeypatch.setattr(ui_module, "create_server", spy)
    assert ui_module.run_ui(0, open_browser=False, idle_minutes=0.01, quiet=True) == 0
    assert not made[0][1]._dir.exists()


def test_gui_entry_point_opens_the_browser_without_a_console(monkeypatch, tmp_path):
    import csv_tidy.ui as ui_module

    calls = []
    monkeypatch.setattr(ui_module, "run_ui", lambda *a, **k: calls.append((a, k)) or 0)
    assert ui_module.gui_main() == 0
    assert calls == [
        ((0, True, ui_module.DEFAULT_MAX_FILE_MB), {"idle_minutes": 10, "quiet": True})
    ]

    def broken(*a, **k):
        raise OSError("port in use")

    monkeypatch.setattr(ui_module, "run_ui", broken)
    monkeypatch.setattr(ui_module.tempfile, "gettempdir", lambda: str(tmp_path))
    assert ui_module.gui_main() == 2
    assert "port in use" in (tmp_path / "csv-tidy-ui-error.txt").read_text(encoding="utf-8")


def test_quiet_mode_survives_a_missing_console(monkeypatch):
    import csv_tidy.ui as ui_module

    monkeypatch.setattr("sys.stdout", None)
    ui_module._say("hello", quiet=False)  # pythonw has no stdout; nothing may fail


def test_ui_command_accepts_idle_minutes(monkeypatch):
    import csv_tidy.ui as ui_module

    seen = []
    monkeypatch.setattr(ui_module, "run_ui", lambda *a: seen.append(a) or 0)
    assert run_cli("ui", "--no-browser", "--idle-minutes", "5").code == 0
    assert seen == [(0, False, 200, 5)]


def test_a_second_server_cannot_share_the_port_of_a_running_one():
    from csv_tidy.errors import CsvTidyError

    server, session, client, _ = serve()
    port = server.server_address[1]
    try:
        with pytest.raises(CsvTidyError, match=f"port {port}"):
            create_server(port)
        assert client.post("/api/ping", {})[0] == 200  # the first server still answers
    finally:
        server.shutdown()
        server.server_close()
        session.close()
