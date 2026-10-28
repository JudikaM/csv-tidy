"""Local browser interface (``csv-tidy ui``) for people who prefer forms to a command line.

A small HTTP server bound to the loopback address serves one page and a JSON API. Every
operation calls the same functions as the CLI (``check_file``, ``clean_file``,
``export_clean``, the profile loader and serializer); there is no second validation engine.

The browser sends the chosen file to this local process, which keeps it in a private
temporary directory until another file is chosen or the server stops. Results are handed
back as downloads, so the chosen file is never written to. Nothing leaves the computer: the
page loads no external resources and the server makes no outgoing connections.

Requests are accepted only when they carry the session token created at start-up, name the
loopback host, and (when the browser sends one) a same-origin ``Origin`` header.
"""

from __future__ import annotations

import contextlib
import hmac
import io
import json
import os
import secrets
import shutil
import socket
import sys
import tempfile
import threading
import time
import tomllib
import webbrowser
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any, TypeVar, cast
from urllib.parse import parse_qs, quote, unquote, urlsplit

from . import __version__
from .api import CheckResult, CleanResult, check_file, clean_file, export_clean
from .batch import BatchInput, BatchResult, batch_report, render_batch_text, run_batch
from .errors import CsvTidyError, ProfileError
from .reporting import (
    check_report,
    clean_report,
    render_check_text,
    render_clean_text,
    to_json,
)
from .schema import (
    Overrides,
    Profile,
    canonical_profile,
    profile_from_dict,
    profile_to_dict,
    profile_to_toml,
)

LOOPBACK = "127.0.0.1"
TOKEN_HEADER = "X-CSV-Tidy-Token"
PREVIEW_ROWS = 50
DETAIL_LIMIT = 200
MAX_JSON_BYTES = 5 * 1024 * 1024
# A refused request's unread body is read and dropped up to this size before the connection
# is closed (see Handler._discard_body).
DISCARD_BYTES = 1024 * 1024
DEFAULT_MAX_FILE_MB = 200
# Without a console window nobody can press Ctrl+C, so the server stops by itself this
# long after the page last contacted it. The page checks in every minute while open.
GUI_IDLE_MINUTES = 10
MAX_LIST_LIMIT = 10_000
MAX_PREVIEW_ROWS = 1_000
STATIC = {
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/theme.js": ("theme.js", "text/javascript; charset=utf-8"),
}
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
        "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class ApiError(Exception):
    """A request that cannot be served; ``status`` and the message go back to the page."""

    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class LoadedFile:
    id: int
    name: str
    path: Path
    size: int


@dataclass(frozen=True)
class Limits:
    """How much detail a result shows. Totals in reports are always complete."""

    max_details: int = DETAIL_LIMIT
    max_examples: int = DETAIL_LIMIT
    preview_rows: int = PREVIEW_ROWS

    def key(self) -> dict[str, int]:
        return {
            "max_details": self.max_details,
            "max_examples": self.max_examples,
            "preview_rows": self.preview_rows,
        }


LIMIT_RANGES = {
    "max_details": (0, MAX_LIST_LIMIT),
    "max_examples": (0, MAX_LIST_LIMIT),
    "preview_rows": (1, MAX_PREVIEW_ROWS),
}


@dataclass
class StoredResult:
    id: int
    file_id: int
    settings_key: str
    result: CheckResult | CleanResult
    limits: Limits = Limits()


@dataclass
class StoredBatch:
    id: int
    action: str
    files: tuple[LoadedFile, ...]
    settings_key: str
    result: BatchResult
    profile: Profile
    profile_name: str | None
    limits: Limits


def _static(name: str) -> bytes:
    return resources.files("csv_tidy").joinpath("ui_static", name).read_bytes()


def _safe_name(name: str) -> str:
    """A file name without directories or characters that are unsafe on some systems."""
    name = name.replace("\\", "/").rsplit("/", 1)[-1].strip().strip(".")
    cleaned = "".join(ch if ch.isalnum() or ch in "-_. ()" else "_" for ch in name)
    return cleaned[:120] or "data.csv"


def _settings_key(profile: Any, limits: Limits) -> str:
    return json.dumps(
        {"profile": profile, "limits": limits.key()}, sort_keys=True, ensure_ascii=True
    )


def _limits(body: dict[str, Any]) -> Limits:
    given = body.get("limits") or {}
    if not isinstance(given, dict):
        raise ApiError(HTTPStatus.BAD_REQUEST, "limits must be an object.")
    values = Limits().key()
    for name, (low, high) in LIMIT_RANGES.items():
        if name not in given:
            continue
        value = given[name]
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise ApiError(
                HTTPStatus.BAD_REQUEST, f"{name} must be a whole number from {low} to {high}."
            )
        values[name] = value
    return Limits(**values)


class Session:
    """State of the one person using the page: the chosen files and the latest results.

    One-file mode keeps a single file (choosing another replaces it). Several-files mode adds
    files to the selection; a batch result belongs to exactly the files it was made with.
    """

    def __init__(self, max_file_bytes: int) -> None:
        self.token = secrets.token_urlsafe(32)
        self.max_file_bytes = max_file_bytes
        self._dir = Path(tempfile.mkdtemp(prefix="csv-tidy-ui-"))
        self._lock = threading.Lock()
        self._counter = 0
        self._files: dict[int, LoadedFile] = {}
        self._check: StoredResult | None = None
        self._clean: StoredResult | None = None
        self._batch: StoredBatch | None = None
        self.last_contact = time.monotonic()

    def touch(self) -> None:
        """Record that the page (with the session key) contacted the server."""
        self.last_contact = time.monotonic()

    def close(self) -> None:
        shutil.rmtree(self._dir, ignore_errors=True)

    def _next(self) -> int:
        self._counter += 1
        return self._counter

    # ----------------------------------------------------------------- files

    def store_file(self, name: str, data: bytes, append: bool = False) -> dict[str, Any]:
        with self._lock:
            if (
                append
                and sum(f.size for f in self._files.values()) + len(data) > self.max_file_bytes
            ):
                raise ApiError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "The chosen files together are larger than the limit of "
                    f"{self.max_file_bytes // (1024 * 1024)} MB. Process them in smaller groups.",
                )
            number = self._next()
            folder = self._dir / f"file-{number}"
            folder.mkdir()
            path = folder / _safe_name(name)
            path.write_bytes(data)
            dropped = [] if append else list(self._files.values())
            if not append:
                self._files = {}
            self._files[number] = LoadedFile(number, path.name, path, len(data))
            self._check = self._clean = self._batch = None
        for old in dropped:
            shutil.rmtree(old.path.parent, ignore_errors=True)
        return {"file_id": number, "name": path.name, "size": len(data)}

    def remove_file(self, body: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            file_id = body.get("file_id")
            loaded = self._files.pop(file_id, None) if isinstance(file_id, int) else None
            if loaded is not None:
                self._check = self._clean = self._batch = None
        if loaded is not None:
            shutil.rmtree(loaded.path.parent, ignore_errors=True)
        return {"removed": loaded is not None}

    def _loaded(self, file_id: Any) -> LoadedFile:
        with self._lock:
            loaded = self._files.get(file_id) if isinstance(file_id, int) else None
        if loaded is None:
            raise ApiError(
                HTTPStatus.CONFLICT,
                "That file is no longer loaded here. Choose the file again.",
            )
        return loaded

    # ----------------------------------------------------------------- one file

    def preview(self, body: dict[str, Any]) -> dict[str, Any]:
        loaded = self._loaded(body.get("file_id"))
        limits = _limits(body)
        overrides = Overrides(delimiter=body.get("delimiter"), encoding=body.get("encoding"))
        reading = None
        if body.get("max_field_chars") is not None:
            data = {"schema_version": 1, "source": {"max_field_chars": body["max_field_chars"]}}
            reading = profile_from_dict(data, source="settings")
        # Without column rules nothing is transformed, so the rows are the source rows and the
        # source issues are exactly what ``check_file`` reports for the structure.
        clean = clean_file(loaded.path, reading, overrides=overrides)
        result = CheckResult(
            loaded.name,
            None,
            clean.settings,
            clean.scan,
            tuple(replace(issue, status=None) for issue in clean.source_issues),
            header=clean.header,
        )
        return {
            "report": check_report(result, limits.max_details),
            "header": list(result.header) if result.header is not None else None,
            "rows": _rows(clean, set(), limits.preview_rows),
            "rows_total": len(clean.rows),
        }

    def check(self, body: dict[str, Any]) -> dict[str, Any]:
        loaded = self._loaded(body.get("file_id"))
        limits = _limits(body)
        profile = _profile(body.get("profile"))
        result = _named(check_file(loaded.path, profile), loaded.name, body.get("profile_name"))
        with self._lock:
            self._check = StoredResult(
                self._next(), loaded.id, _settings_key(body["profile"], limits), result, limits
            )
            stored = self._check.id
        return {"result_id": stored, "report": check_report(result, limits.max_details)}

    def clean(self, body: dict[str, Any]) -> dict[str, Any]:
        loaded = self._loaded(body.get("file_id"))
        limits = _limits(body)
        profile = _profile(body.get("profile"))
        result = _named(clean_file(loaded.path, profile), loaded.name, body.get("profile_name"))
        with self._lock:
            self._clean = StoredResult(
                self._next(), loaded.id, _settings_key(body["profile"], limits), result, limits
            )
            stored = self._clean.id
        return {"result_id": stored, **_clean_view(result, limits)}

    def download(self, body: dict[str, Any]) -> tuple[str, str, bytes]:
        """Return (file name, content type, bytes) for one artifact of a stored result."""
        kind = body.get("kind")
        if isinstance(kind, str) and kind.startswith("batch-"):
            return self._batch_download(kind, body)
        which = "check" if kind in ("check-report-text", "check-report-json") else "clean"
        limits = _limits(body)
        with self._lock:
            stored = self._check if which == "check" else self._clean
            loaded = self._files.get(stored.file_id) if stored is not None else None
        if stored is None or loaded is None or stored.id != body.get("result_id"):
            raise ApiError(
                HTTPStatus.CONFLICT,
                "That result is no longer current. Run the check or the preview again.",
            )
        if stored.settings_key != _settings_key(body.get("profile"), limits):
            raise ApiError(
                HTTPStatus.CONFLICT,
                "The settings changed after this result was made. Run it again before saving.",
            )
        stem = Path(loaded.name).stem
        result = stored.result
        details, examples = limits.max_details, limits.max_examples
        if isinstance(result, CheckResult):  # the check-report kinds read the latest check
            if kind == "check-report-text":
                text = render_check_text(check_report(result, details))
                return (
                    f"{stem}.check-report.txt",
                    "text/plain; charset=utf-8",
                    text.encode("utf-8"),
                )
            text = to_json(check_report(result, details))
            return f"{stem}.check-report.json", "application/json", text.encode("utf-8")
        if kind == "report-text":
            text = render_clean_text(clean_report(result, "dry-run", details, examples))
            return f"{stem}.clean-report.txt", "text/plain; charset=utf-8", text.encode("utf-8")
        if kind == "report-json":
            text = to_json(clean_report(result, "dry-run", details, examples))
            return f"{stem}.clean-report.json", "application/json", text.encode("utf-8")
        if kind not in ("csv", "output-profile"):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Unknown download.")
        csv_bytes, profile_bytes = self._export(result, stem, stored.id)
        if kind == "csv":
            return f"{stem}.clean.csv", "text/csv", csv_bytes
        return f"{stem}.output.toml", "application/toml", profile_bytes

    def _export(self, result: CleanResult, stem: str, number: int) -> tuple[bytes, bytes]:
        """The cleaned CSV and its output profile, written by ``export_clean`` (the same
        function and export gate as the CLI) into the private session directory."""
        if not result.export_ready:
            raise ApiError(
                HTTPStatus.CONFLICT, f"Saving is blocked: {_sentence(result.export_blocked_reason)}"
            )
        folder = self._dir / f"export-{number}-{secrets.token_hex(4)}"
        csv_path, profile_path = folder / f"{stem}.clean.csv", folder / f"{stem}.output.toml"
        try:
            export_clean(result, csv_path, output_schema=profile_path, overwrite=True)
            return csv_path.read_bytes(), profile_path.read_bytes()
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    # ----------------------------------------------------------------- several files

    def batch(self, body: dict[str, Any]) -> dict[str, Any]:
        action = body.get("action")
        if action not in ("check", "clean"):
            raise ApiError(HTTPStatus.BAD_REQUEST, "action must be check or clean.")
        ids = body.get("file_ids")
        if not isinstance(ids, list) or not ids:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Choose at least one file.")
        files = tuple(self._loaded(file_id) for file_id in ids)
        if len({f.id for f in files}) != len(files):
            raise ApiError(HTTPStatus.BAD_REQUEST, "A file is listed more than once.")
        stems: dict[str, str] = {}
        for loaded in files:
            stem = Path(loaded.name).stem.casefold()
            if stem in stems:
                raise ApiError(
                    HTTPStatus.BAD_REQUEST,
                    f"Two chosen files have the same name ({stems[stem]} and {loaded.name}), so "
                    "their results would overwrite each other. Rename one, or process it alone.",
                )
            stems[stem] = loaded.name
        limits = _limits(body)
        profile = _profile(body.get("profile"))
        profile_name = _shown_profile(body.get("profile_name"))
        inputs = [BatchInput(f.path, Path(f.name), label=f.name) for f in files]
        result = replace(run_batch(action, inputs, profile), profile_path=profile_name)
        with self._lock:
            if any(self._files.get(f.id) is not f for f in files):
                raise ApiError(HTTPStatus.CONFLICT, "The chosen files changed; run it again.")
            self._batch = StoredBatch(
                self._next(),
                action,
                files,
                _settings_key(body["profile"], limits),
                result,
                profile,
                profile_name,
                limits,
            )
            stored = self._batch.id
        report = batch_report(result)
        listed = [
            {"file_id": loaded.id, "name": loaded.name, "size": loaded.size} for loaded in files
        ]
        return {"batch_id": stored, "report": report, "files": listed}

    def _stored_batch(self, body: dict[str, Any]) -> StoredBatch:
        limits = _limits(body)
        with self._lock:
            stored = self._batch
            current = stored is not None and all(self._files.get(f.id) is f for f in stored.files)
        if stored is None or not current or stored.id != body.get("batch_id"):
            raise ApiError(
                HTTPStatus.CONFLICT,
                "That result is no longer current. Run the check or the preview again.",
            )
        if stored.settings_key != _settings_key(body.get("profile"), limits):
            raise ApiError(
                HTTPStatus.CONFLICT,
                "The settings changed after this result was made. Run it again before saving.",
            )
        return stored

    @staticmethod
    def _batch_member(stored: StoredBatch, file_id: Any) -> LoadedFile:
        loaded = next((f for f in stored.files if f.id == file_id), None)
        if loaded is None:
            raise ApiError(HTTPStatus.BAD_REQUEST, "That file is not part of this result.")
        return loaded

    def _batch_check(self, stored: StoredBatch, file_id: Any) -> tuple[LoadedFile, CheckResult]:
        loaded = self._batch_member(stored, file_id)
        result = check_file(loaded.path, stored.profile)
        return loaded, _named(result, loaded.name, stored.profile_name)

    def _batch_clean(self, stored: StoredBatch, file_id: Any) -> tuple[LoadedFile, CleanResult]:
        loaded = self._batch_member(stored, file_id)
        result = clean_file(loaded.path, stored.profile)
        return loaded, _named(result, loaded.name, stored.profile_name)

    def batch_file(self, body: dict[str, Any]) -> dict[str, Any]:
        """Full details of one file of the latest batch, computed by the single-file functions."""
        stored = self._stored_batch(body)
        if stored.action == "check":
            _, checked = self._batch_check(stored, body.get("file_id"))
            return {"action": "check", "report": check_report(checked, stored.limits.max_details)}
        _, cleaned = self._batch_clean(stored, body.get("file_id"))
        return {"action": "clean", **_clean_view(cleaned, stored.limits)}

    def _batch_download(self, kind: str, body: dict[str, Any]) -> tuple[str, str, bytes]:
        stored = self._stored_batch(body)
        limits = stored.limits
        if kind == "batch-summary-json":
            text = to_json(batch_report(stored.result))
            return "batch-summary.json", "application/json", text.encode("utf-8")
        if kind == "batch-summary-text":
            text = render_batch_text(batch_report(stored.result))
            return "batch-summary.txt", "text/plain; charset=utf-8", text.encode("utf-8")
        if kind == "batch-csv":
            if stored.action != "clean":
                raise ApiError(HTTPStatus.BAD_REQUEST, "Run Preview cleaning first.")
            loaded, cleaned = self._batch_clean(stored, body.get("file_id"))
            stem = Path(loaded.name).stem
            return f"{stem}.clean.csv", "text/csv", self._export(cleaned, stem, stored.id)[0]
        if kind != "batch-zip":
            raise ApiError(HTTPStatus.BAD_REQUEST, "Unknown download.")
        entries: list[tuple[str, bytes]] = []
        for loaded, outcome in zip(stored.files, stored.result.files, strict=True):
            stem = Path(loaded.name).stem
            if stored.action == "check":
                _, checked = self._batch_check(stored, loaded.id)
                report = check_report(checked, limits.max_details)
            else:
                _, cleaned = self._batch_clean(stored, loaded.id)
                ready = cleaned.export_ready
                if ready != (outcome.status == "ready"):
                    raise ApiError(HTTPStatus.CONFLICT, "A file changed; run the preview again.")
                if ready:
                    csv_bytes, profile_bytes = self._export(cleaned, stem, stored.id)
                    entries.append((f"{stem}.clean.csv", csv_bytes))
                    entries.append((f"{stem}.output.toml", profile_bytes))
                report = clean_report(cleaned, "dry-run", limits.max_details, limits.max_examples)
            entries.append((f"{stem}.report.json", to_json(report).encode("utf-8")))
        summary = batch_report(stored.result)
        entries.append(("batch-summary.json", to_json(summary).encode("utf-8")))
        entries.append(("batch-summary.txt", render_batch_text(summary).encode("utf-8")))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in entries:
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
        return "csv-tidy-batch.zip", "application/zip", buffer.getvalue()

    # ----------------------------------------------------------------- profiles

    @staticmethod
    def parse_profile(body: dict[str, Any]) -> dict[str, Any]:
        text = body.get("text")
        if not isinstance(text, str):
            raise ApiError(HTTPStatus.BAD_REQUEST, "No profile text was sent.")
        name = _safe_name(str(body.get("name") or "profile.toml"))
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise ProfileError(f"{name} is not a valid profile file (TOML): {exc}") from None
        profile = canonical_profile(profile_from_dict(data, source=name))
        return {"profile": profile_to_dict(profile), "name": name}

    @staticmethod
    def profile_toml(body: dict[str, Any]) -> tuple[str, str, bytes]:
        profile = _profile(body.get("profile"))
        stem = Path(_safe_name(str(body.get("file_name") or "data.csv"))).stem
        header = (
            f"CSV Tidy profile saved from the local interface (csv-tidy {__version__}).\n"
            "Reuse it with: csv-tidy check FILE --schema THIS_FILE"
        )
        text = profile_to_toml(profile, header)
        return f"{stem}.profile.toml", "application/toml", text.encode("utf-8")


def _profile(data: Any) -> Profile:
    if not isinstance(data, dict):
        raise ApiError(HTTPStatus.BAD_REQUEST, "No settings were sent.")
    return profile_from_dict(data, source="settings")


def _shown_profile(profile_name: Any) -> str | None:
    return _safe_name(profile_name) if isinstance(profile_name, str) and profile_name else None


_Result = TypeVar("_Result", CheckResult, CleanResult)


def _named(result: _Result, name: str, profile_name: Any) -> _Result:
    """Show the file's own name in reports instead of the private temporary path."""
    return replace(result, source_path=name, profile_path=_shown_profile(profile_name))


def _sentence(reason: str | None) -> str | None:
    return None if reason is None else reason[:1].upper() + reason[1:] + "."


def _clean_view(result: CleanResult, limits: Limits) -> dict[str, Any]:
    changed = {(c.record, c.column) for c in result.changes}
    return {
        "report": clean_report(result, "dry-run", limits.max_details, limits.max_examples),
        "header": list(result.header) if result.header is not None else None,
        "rows": _rows(result, changed, limits.preview_rows),
        "rows_total": len(result.rows),
        "blocked_reason": _sentence(result.export_blocked_reason),
    }


def _rows(
    result: CleanResult, changed: set[tuple[int, str]], limit: int = PREVIEW_ROWS
) -> list[dict[str, Any]]:
    """The first cleaned records with their source record numbers and changed cells."""
    header = result.header or ()
    removed = {r.record for r in result.removed}
    numbers = (n for n in range(1, result.scan.data_records + 1) if n not in removed)
    rows = []
    for number, fields in zip(numbers, result.rows[:limit], strict=False):
        marks = [
            position
            for position, name in enumerate(header[: len(fields)])
            if (number, name) in changed and header.index(name) == position
        ]
        rows.append({"record": number, "fields": list(fields), "changed": marks})
    return rows


# --------------------------------------------------------------------------- HTTP


class Handler(BaseHTTPRequestHandler):
    server_version = "csv-tidy-ui"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    session: Session  # set on the subclass made by ``create_server``
    _body_read = False  # whether the current request's body was read

    def log_message(self, format: str, *args: Any) -> None:
        return  # request lines would include file names; keep the console quiet

    # ----------------------------------------------------------------- helpers

    def _send(
        self,
        status: HTTPStatus,
        content_type: str,
        body: bytes,
        extra: Iterable[tuple[str, str]] = (),
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (*SECURITY_HEADERS.items(), *extra):
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, data: dict[str, Any]) -> None:
        self._send(status, "application/json", json.dumps(data, ensure_ascii=True).encode())

    def _refuse(self, status: HTTPStatus, message: str) -> None:
        self.close_connection = True
        self._discard_body()
        self._json(status, {"error": message})

    def _discard_body(self) -> None:
        """Read and drop the unread body of a refused request (up to ``DISCARD_BYTES``).

        Closing a connection that still holds unread data makes the operating system reset
        it, and on Windows the reset can reach the client before the answer does.
        """
        if self._body_read:
            return
        self._body_read = True
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return
        if 0 < length <= DISCARD_BYTES:
            self.rfile.read(length)

    def _origins(self) -> tuple[str, ...]:
        # The server listens on an IPv4 loopback address, so its address is (host, port).
        port = cast("tuple[str, int]", self.server.server_address)[1]
        return (f"{LOOPBACK}:{port}", f"localhost:{port}")

    def _local(self) -> bool:
        """Only requests addressed to this loopback server by name are served (this also
        stops DNS-rebinding pages, whose requests carry another host name)."""
        if self.headers.get("Host") not in self._origins():
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin in tuple(f"http://{o}" for o in self._origins())

    def _token_ok(self, given: str | None) -> bool:
        return given is not None and hmac.compare_digest(given, self.session.token)

    def _body(self, limit: int) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise ApiError(HTTPStatus.LENGTH_REQUIRED, "The request has no length.") from None
        if length < 0 or length > limit:
            raise ApiError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                f"This is larger than the limit of {limit // (1024 * 1024)} MB.",
            )
        self._body_read = True
        return self.rfile.read(length)

    # ----------------------------------------------------------------- routes

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if not self._local():
            self._refuse(HTTPStatus.FORBIDDEN, "This address is not served.")
        elif url.path in STATIC:
            name, content_type = STATIC[url.path]
            self._send(HTTPStatus.OK, content_type, _static(name))
        elif url.path != "/":
            self._refuse(HTTPStatus.NOT_FOUND, "Not found.")
        elif not self._token_ok(parse_qs(url.query).get("token", [None])[0]):
            self._send(
                HTTPStatus.FORBIDDEN,
                "text/plain; charset=utf-8",
                b"This page needs the address printed by `csv-tidy ui` (it contains a "
                b"one-time key). Start `csv-tidy ui` again and use the address it shows.\n",
            )
        else:
            self.session.touch()
            page = _static("index.html").replace(b"{{token}}", self.session.token.encode())
            page = page.replace(b"{{version}}", __version__.encode())
            limit = str(self.session.max_file_bytes // (1024 * 1024)).encode()
            page = page.replace(b"{{max_file_mb}}", limit)
            self._send(HTTPStatus.OK, "text/html; charset=utf-8", page)

    def do_POST(self) -> None:
        self._body_read = False
        url = urlsplit(self.path)
        if not self._local() or not self._token_ok(self.headers.get(TOKEN_HEADER)):
            self._refuse(HTTPStatus.FORBIDDEN, "This request was not sent by the CSV Tidy page.")
            return
        session = self.session
        session.touch()
        try:
            if url.path == "/api/file":
                name = unquote(self.headers.get("X-File-Name", "data.csv"))
                append = parse_qs(url.query).get("mode", [""])[0] == "append"
                data = self._body(session.max_file_bytes)
                self._json(HTTPStatus.OK, session.store_file(name, data, append))
                return
            if self.headers.get_content_type() != "application/json":
                raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Send JSON.")
            try:
                body = json.loads(self._body(MAX_JSON_BYTES) or b"{}")
            except ValueError:
                raise ApiError(HTTPStatus.BAD_REQUEST, "The request is not valid JSON.") from None
            if not isinstance(body, dict):
                raise ApiError(HTTPStatus.BAD_REQUEST, "The request is not valid JSON.")
            if url.path == "/api/preview":
                self._json(HTTPStatus.OK, session.preview(body))
            elif url.path == "/api/check":
                self._json(HTTPStatus.OK, session.check(body))
            elif url.path == "/api/clean":
                self._json(HTTPStatus.OK, session.clean(body))
            elif url.path == "/api/batch":
                self._json(HTTPStatus.OK, session.batch(body))
            elif url.path == "/api/batch/file":
                self._json(HTTPStatus.OK, session.batch_file(body))
            elif url.path == "/api/file/remove":
                self._json(HTTPStatus.OK, session.remove_file(body))
            elif url.path == "/api/profile/parse":
                self._json(HTTPStatus.OK, session.parse_profile(body))
            elif url.path in ("/api/download", "/api/profile/toml"):
                make = session.download if url.path == "/api/download" else session.profile_toml
                name, content_type, data = make(body)
                self._send(
                    HTTPStatus.OK,
                    content_type,
                    data,
                    (
                        ("Content-Disposition", f"attachment; filename*=UTF-8''{quote(name)}"),
                        ("X-File-Name", quote(name)),
                    ),
                )
            elif url.path == "/api/ping":
                self._json(HTTPStatus.OK, {"ok": True})
            elif url.path == "/api/quit":
                self._json(HTTPStatus.OK, {"stopped": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                raise ApiError(HTTPStatus.NOT_FOUND, "Not found.")
        except ApiError as exc:
            self._refuse(exc.status, str(exc))
        except CsvTidyError as exc:
            self._refuse(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # the page must get an answer instead of a dropped socket
            print(f"csv-tidy ui: unexpected error: {exc!r}", file=sys.stderr)
            self._refuse(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Something unexpected went wrong. Nothing was saved. Details are in the "
                "window where csv-tidy ui is running.",
            )


class LocalServer(ThreadingHTTPServer):
    """The loopback server. Its port is never shared: on Windows ``SO_REUSEADDR`` would let a
    second server bind a port that a running one uses (and requests would keep going to the
    first), so the port is claimed exclusively there and address reuse is off."""

    allow_reuse_address = os.name != "nt"
    daemon_threads = True

    def server_bind(self) -> None:
        exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
        if exclusive is not None:
            self.socket.setsockopt(socket.SOL_SOCKET, exclusive, 1)
        super().server_bind()


def create_server(
    port: int = 0, max_file_mb: int = DEFAULT_MAX_FILE_MB
) -> tuple[ThreadingHTTPServer, Session, str]:
    """Create the loopback server (not yet serving). Returns (server, session, page URL)."""
    session = Session(max_file_mb * 1024 * 1024)
    handler = type("SessionHandler", (Handler,), {"session": session})
    try:
        server = LocalServer((LOOPBACK, port), handler)
    except OSError as exc:
        session.close()
        raise CsvTidyError(
            f"cannot start the local interface on port {port}: {exc.strerror or exc}. "
            "Choose another port with --port, or omit --port to pick a free one."
        ) from None
    url = f"http://{LOOPBACK}:{server.server_address[1]}/?token={session.token}"
    return server, session, url


def start_idle_watch(
    server: ThreadingHTTPServer, session: Session, seconds: float
) -> threading.Thread:
    """Stop ``server`` once the page has not contacted it for ``seconds``."""

    def watch() -> None:
        poll = max(0.05, min(15.0, seconds / 4))
        while True:
            time.sleep(poll)
            if time.monotonic() - session.last_contact > seconds:
                server.shutdown()
                return

    thread = threading.Thread(target=watch, name="csv-tidy-idle", daemon=True)
    thread.start()
    return thread


def _say(text: str, quiet: bool) -> None:
    # Started without a console (pythonw), sys.stdout is None.
    if not quiet and sys.stdout is not None:
        print(text)
        sys.stdout.flush()


def run_ui(
    port: int = 0,
    open_browser: bool = True,
    max_file_mb: int = DEFAULT_MAX_FILE_MB,
    idle_minutes: float = 0,
    quiet: bool = False,
) -> int:
    """Serve the interface until the page's Quit button or Ctrl+C stops it, or, with
    ``idle_minutes``, until the page has not been in contact for that long."""
    server, session, url = create_server(port, max_file_mb)
    _say("CSV Tidy is running on this computer only (nothing is sent to the internet).", quiet)
    _say(f"Open this address in your browser:\n\n  {url}\n", quiet)
    _say("Keep this window open while you work. To stop: use Quit on the page, or Ctrl+C.", quiet)
    if idle_minutes > 0:
        start_idle_watch(server, session, idle_minutes * 60)
        _say(f"It also stops by itself after {idle_minutes:g} minutes without an open page.", quiet)
    if open_browser:
        with contextlib.suppress(Exception):
            webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        session.close()
    _say("CSV Tidy stopped. Temporary copies were removed.", quiet)
    return 0


def gui_main() -> int:
    """Entry point of the ``csv-tidy-ui`` program: no console window, the browser opens, and
    the server stops by itself when the page is no longer open. A start-up problem is written
    to ``csv-tidy-ui-error.txt`` in the temporary folder, as there is no window to show it."""
    try:
        return run_ui(0, True, DEFAULT_MAX_FILE_MB, idle_minutes=GUI_IDLE_MINUTES, quiet=True)
    except Exception as exc:
        with contextlib.suppress(OSError):
            Path(tempfile.gettempdir(), "csv-tidy-ui-error.txt").write_text(
                f"CSV Tidy could not start its local interface: {exc}\n", encoding="utf-8"
            )
        return 2
