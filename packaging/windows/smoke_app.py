"""Smoke test of the Datakrit Windows app (or of any ``datakrit-ui`` program).

    python packaging/windows/smoke_app.py PROGRAM [--sha256 HEX] [--timeout SECONDS]

PROGRAM is ``Datakrit.exe``, a ``Datakrit-<version>-windows-x64.zip`` (unzipped into a
temporary folder first; with ``--sha256`` its hash is checked before that, and a
``.sha256`` file next to it must be exactly ``<hash>  <zip name>`` and LF), or a
``datakrit-ui`` program installed by pip. The test

1. starts the program in smoke mode: ``DATAKRIT_UI_URL_FILE`` names a file, so no browser
   opens and the program writes its page address, with the session key, to that file;
2. fetches the page with the key and every file of the page;
3. checks that the page is refused without the key or with a wrong key, and that a request
   to the API without the key is refused;
4. presses Quit through the API, and checks that the program exits with code 0.

For ``Datakrit.exe`` and the zip it first checks the license notices in
``Datakrit/licenses/`` (``LICENSE_FILES``): each is there and holds its license, and the
Microsoft notice names every Microsoft runtime file of the app.

It prints the start-up time (from starting the program until the page was served) and exits
with code 0 when everything passed. Only the standard library is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# The files of the page (``STATIC`` in src/datakrit/ui.py), with their content types.
ASSETS = {
    "/app.css": "text/css; charset=utf-8",
    "/app.js": "text/javascript; charset=utf-8",
    "/theme.js": "text/javascript; charset=utf-8",
    "/logo-mark.png": "image/png",
}
TOKEN_HEADER = "X-Datakrit-Token"
# The notices in Datakrit/licenses/ (``LICENSE_FILES`` in build_app.py), each with a text
# that its file must contain.
LICENSE_FILES = {
    "LICENSE": "Permission is hereby granted, free of charge",
    "NOTICE.md": "Copyright (c) 2026 Lucide Icons and Contributors",
    "Python-LICENSE.txt": "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2",
    "tomli-w-LICENSE.txt": "Permission is hereby granted, free of charge",
    "Microsoft-runtime-NOTICE.txt": "Microsoft Distributable Code",
}
MICROSOFT_DLL = re.compile(
    r"(vcruntime\d+(_\d+)?|msvcp\d+(_\w+)?|concrt\d+|ucrtbase|api-ms-win-[\w.-]+)\.dll",
    re.IGNORECASE,
)
URL_FILE_VARIABLE = "DATAKRIT_UI_URL_FILE"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class SmokeError(Exception):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def fetch(url: str, data: bytes | None = None, headers: dict[str, str] | None = None):
    """(status, headers, body); an HTTP error status is returned, not raised."""
    request = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with OPENER.open(request, timeout=30) as answer:
            return answer.status, answer.headers, answer.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()


def check_sha256_file(path: Path, digest: str) -> None:
    """The checksum file next to the zip, if any, is one LF-terminated line that
    ``sha256sum --check`` reads on every system."""
    checksum = path.with_name(path.name + ".sha256")
    if checksum.exists():
        expected = f"{digest}  {path.name}\n".encode("ascii")
        check(checksum.read_bytes() == expected, f"{checksum.name} is not '<hash>  <name>' + LF")
        print("sha256_file=ok")


def program_from(path: Path, work: Path, expected_sha256: str | None) -> Path:
    if path.suffix.lower() != ".zip":
        check(expected_sha256 is None, "--sha256 is checked for a zip file only")
        return path
    if expected_sha256 is not None:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        check(digest == expected_sha256.lower(), f"{path.name}: SHA-256 {digest} differs")
        print(f"sha256=ok {digest}")
        check_sha256_file(path, digest)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        check(names and all(n.startswith("Datakrit/") for n in names), "unexpected zip layout")
        archive.extractall(work / "unzipped")
    return work / "unzipped" / "Datakrit" / "Datakrit.exe"


def check_licenses(folder: Path) -> int:
    """Check ``folder/licenses`` of the app folder ``folder``; return the number of files."""
    licenses = folder / "licenses"
    for name, needed in LICENSE_FILES.items():
        path = licenses / name
        check(path.is_file(), f"licenses/{name} is missing")
        check(needed in path.read_text(encoding="utf-8"), f"licenses/{name} lacks its license")
    notice = (licenses / "Microsoft-runtime-NOTICE.txt").read_text(encoding="utf-8")
    runtime = [
        p.relative_to(folder).as_posix()
        for p in folder.rglob("*.dll")
        if MICROSOFT_DLL.fullmatch(p.name)
    ]
    check(bool(runtime), "the app has no Microsoft runtime files to check")
    missing = [name for name in runtime if f"  {name}\n" not in notice]
    check(not missing, f"the Microsoft notice does not name {missing}")
    extra = sorted(p.name for p in licenses.iterdir()) != sorted(LICENSE_FILES)
    check(not extra, f"licenses/ holds other files: {sorted(p.name for p in licenses.iterdir())}")
    return len(LICENSE_FILES)


def run(program: Path, work: Path, timeout: float) -> dict[str, float]:
    url_file = work / "url.txt"
    temp = work / "temp"
    temp.mkdir()
    env = dict(os.environ, TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
    env[URL_FILE_VARIABLE] = str(url_file)
    started = time.perf_counter()
    process = subprocess.Popen([str(program)], env=env, cwd=work)
    try:
        while not url_file.exists():
            code = process.poll()
            if code is not None:
                error = temp / "datakrit-ui-error.txt"
                detail = error.read_text(encoding="utf-8") if error.exists() else "no error file"
                raise SmokeError(f"the program exited with code {code} before serving: {detail}")
            check(time.perf_counter() - started < timeout, "no page address within the timeout")
            time.sleep(0.05)
        ready = time.perf_counter() - started
        url = url_file.read_text(encoding="utf-8").strip()
        match = re.fullmatch(r"(http://127\.0\.0\.1:\d+)/\?token=([A-Za-z0-9_-]+)", url)
        check(match is not None, f"unexpected page address {url!r}")
        assert match is not None
        base, token = match.groups()

        status, headers, page = fetch(url)
        served = time.perf_counter() - started
        check(status == 200, f"the page answered {status}")
        check(headers.get("Content-Type") == "text/html; charset=utf-8", "page content type")
        text = page.decode("utf-8")
        title = re.search(r"<title>Datakrit (\d+\.\d+\.\d+)[^<]*</title>", text)
        check(title is not None, "the page has no Datakrit title with a version")
        assert title is not None
        check("{{" not in text, "the page still holds a template field")
        referenced = {"/" + n for n in re.findall(r'(?:href|src)="([^"#:?/][^"#:?]*)"', text)}
        check(referenced <= set(ASSETS), f"the page uses unknown files {referenced - set(ASSETS)}")
        for name, content_type in ASSETS.items():
            status, headers, body = fetch(base + name)
            check(status == 200 and len(body) > 0, f"{name} answered {status}")
            check(headers.get("Content-Type") == content_type, f"{name} content type")

        for refused in (base + "/", base + "/?token=wrong" + token[:4]):
            status, _, _ = fetch(refused)
            check(status == 403, f"{refused.replace(token, '<key>')} answered {status}, not 403")
        status, _, _ = fetch(base + "/api/ping", b"{}", {"Content-Type": "application/json"})
        check(status == 403, f"the API without the key answered {status}, not 403")

        quit_headers = {"Content-Type": "application/json", TOKEN_HEADER: token}
        status, _, body = fetch(base + "/api/quit", b"{}", quit_headers)
        check(status == 200 and json.loads(body) == {"stopped": True}, "Quit was not accepted")
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            raise SmokeError("the program did not exit after Quit") from None
        check(code == 0, f"the program exited with code {code}, not 0")
        return {
            "version": title.group(1),
            "ready_seconds": round(ready, 2),
            "startup_seconds": round(served, 2),
        }
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the Datakrit Windows app.")
    parser.add_argument("program", type=Path, help="Datakrit.exe, its zip, or datakrit-ui")
    parser.add_argument("--sha256", help="expected SHA-256 of the zip")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="datakrit-smoke-") as folder:
        work = Path(folder)
        try:
            program = program_from(args.program.resolve(), work, args.sha256)
            check(program.is_file(), f"{program} does not exist")
            notices = None
            if program.name.lower() == "datakrit.exe":
                notices = check_licenses(program.parent)
            result = run(program, work, args.timeout)
        except SmokeError as error:
            print(f"smoke test failed: {error}", file=sys.stderr)
            return 1
    if notices is not None:
        print(f"licenses=ok {notices} files")
    for key, value in result.items():
        print(f"{key}={value}")
    print("smoke test passed: page and files served with the key, refused without it, Quit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
