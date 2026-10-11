from __future__ import annotations

import hashlib
import io
import shutil
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path

import pytest

from csv_tidy.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


@dataclass
class CliResult:
    code: int
    out: str
    err: str


def run_cli(*args: str) -> CliResult:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = main(list(args))
        except SystemExit as exc:  # argparse usage errors
            code = exc.code
    return CliResult(code, out.getvalue(), err.getvalue())


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def examples(tmp_path: Path) -> Path:
    """A private copy of examples/ so tests never write next to the real fixtures."""
    target = tmp_path / "examples"
    shutil.copytree(EXAMPLES, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


@pytest.fixture
def write(tmp_path: Path):
    def _write(name: str, text: str | bytes, encoding: str = "utf-8") -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text if isinstance(text, bytes) else text.encode(encoding))
        return path

    return _write
