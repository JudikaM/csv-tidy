"""The local interface server: same pipeline as the CLI, loopback only, token protected."""

import json
import re
import threading
import urllib.error
import urllib.request
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

    def upload(self, path: Path, name=None):
        headers = {
            TOKEN_HEADER: self.token,
            "Content-Type": "application/octet-stream",
            "X-File-Name": quote(name or path.name),
        }
        status, _, data = self.request("/api/file", path.read_bytes(), headers)
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
    assets = [ui.request(path)[2].decode("utf-8") for path in ("/app.css", "/app.js")]
    for text in (page, *assets):
        assert not re.search(r"(https?:)?//(?!127\.0\.0\.1)[\w.-]+\.\w+", text), "external URL"
    assert "innerHTML" not in assets[1] and "eval(" not in assets[1]
    assert re.findall(r'<(?:script|link)[^>]+(?:src|href)="([^"]+)"', page) == [
        "data:,",
        "app.css",
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
