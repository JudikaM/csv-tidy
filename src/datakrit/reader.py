"""Strict CSV reading that keeps every field as text and tracks source line ranges."""

from __future__ import annotations

import codecs
import contextlib
import csv
import io
import re
import threading
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .errors import InputError


@dataclass(frozen=True)
class Record:
    """One data record. ``index`` counts data records (1-based, header excluded);
    ``line_start``/``line_end`` are physical source lines (they differ for multiline fields)."""

    index: int
    line_start: int
    line_end: int
    fields: tuple[str, ...]


@dataclass(frozen=True)
class FatalError:
    """A failure that stops scanning: decoding, malformed quoting, or an oversized field."""

    code: str
    message: str
    line: int | None


@dataclass
class Table:
    header: tuple[str, ...] | None = None
    header_line: int | None = None
    records: list[Record] = field(default_factory=list)
    blank_lines: list[int] = field(default_factory=list)
    physical_lines: int = 0
    bom: bool = False
    fatal: FatalError | None = None

    @property
    def complete(self) -> bool:
        return self.fatal is None


def read_csv(path: str | Path, delimiter: str, encoding: str, max_field_chars: int) -> Table:
    """Read ``path`` strictly. Raises ``InputError`` if the file cannot be opened.

    Parsing failures do not raise: they are recorded in ``Table.fatal`` together with the
    records read before the failure, so reports can state that the scan is incomplete.
    """
    path = Path(path)
    codec = codecs.lookup(encoding).name
    if path.is_dir():
        raise InputError(f"input is a directory, not a file: {path}")
    try:
        with path.open("rb") as raw:
            bom = raw.read(3) == codecs.BOM_UTF8
    except FileNotFoundError:
        raise InputError(f"input file not found: {path}") from None
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}") from None
    read_encoding = "utf-8-sig" if codec == "utf-8" else encoding

    with _field_limit(max_field_chars):
        try:
            with path.open(encoding=read_encoding, errors="strict", newline="") as handle:
                try:
                    return _parse(handle, Table(bom=bom), delimiter, max_field_chars)
                except UnicodeDecodeError as exc:
                    reason = exc.reason
            # Text decoding works in buffered chunks, so the stream fails before the lines
            # in front of the bad bytes are parsed. Parse the valid prefix again to report
            # exactly what was readable and where it stopped.
            prefix = _valid_prefix(path, read_encoding)
        except OSError as exc:
            raise InputError(f"cannot read {path}: {exc.strerror or exc}") from None
        line = len(_NEWLINE.findall(prefix)) + 1
        lines = list(io.StringIO(prefix, newline=""))
        if lines and not lines[-1].endswith(("\r", "\n")):
            lines.pop()  # the line that contains the undecodable bytes
        table = _parse(lines, Table(bom=bom), delimiter, max_field_chars, truncated=True)
        if table.fatal is None:
            table.fatal = FatalError(
                "decode_error",
                f"the file is not valid {encoding} near line {line}: {reason}; "
                "no characters were replaced or skipped",
                line,
            )
        return table


# Line breaks as the csv module counts them for files opened with newline="".
_NEWLINE = re.compile(r"\r\n|\r|\n")


def _parse(
    lines: Iterable[str],
    table: Table,
    delimiter: str,
    max_field_chars: int,
    truncated: bool = False,
) -> Table:
    """Parse ``lines`` into ``table`` and record a fatal CSV problem instead of raising.

    ``truncated`` means ``lines`` stop in front of undecodable bytes: a quoted field that is
    still open at the end is then left to the caller, which reports the decoding error.
    """
    source = _Lines(lines)
    reader = csv.reader(
        source,
        delimiter=delimiter,
        quotechar='"',
        doublequote=True,
        strict=True,
        skipinitialspace=False,
    )
    previous = 0
    try:
        for row in reader:
            start, end = previous + 1, reader.line_num
            # The csv module's own limit is process-wide and may have been raised by
            # another read running at the same time, so the limit is enforced here too.
            if any(len(value) > max_field_chars for value in row):
                raise csv.Error("field larger than field limit")
            previous = end
            if not row:
                table.blank_lines.append(start)
            elif table.header is None:
                table.header, table.header_line = tuple(row), start
            else:
                table.records.append(Record(len(table.records) + 1, start, end, tuple(row)))
    except csv.Error as exc:
        text = str(exc)
        if "field larger than field limit" in text:
            table.fatal = FatalError(
                "field_too_large",
                f"a field in the record starting at line {previous + 1} "
                "exceeds the limit of "
                f"{max_field_chars} characters (source max_field_chars)",
                previous + 1,
            )
        elif not (truncated and source.exhausted):
            table.fatal = FatalError(
                "malformed_csv",
                f"malformed CSV in the record starting at line {previous + 1} "
                f"(detected at line {reader.line_num}): {text}",
                previous + 1,
            )
    table.physical_lines = reader.line_num
    return table


class _Lines:
    """Iterate lines and remember whether the end was reached."""

    def __init__(self, lines: Iterable[str]) -> None:
        self._lines = iter(lines)
        self.exhausted = False

    def __iter__(self) -> Iterator[str]:
        return self

    def __next__(self) -> str:
        try:
            return next(self._lines)
        except StopIteration:
            self.exhausted = True
            raise


def _valid_prefix(path: Path, encoding: str) -> str:
    """The text in front of the first undecodable bytes."""
    data = path.read_bytes()
    try:
        return data.decode(encoding)
    except UnicodeDecodeError as exc:
        return data[: exc.start].decode(encoding, errors="ignore")


# ``csv.field_size_limit`` is one value for the whole process. While reads overlap it is held
# at the largest limit any of them needs (each read enforces its own limit on the parsed
# fields), and the value found before the first read is restored after the last one.
_limit_lock = threading.Lock()
_active_limits: list[int] = []
_limit_before_reads = 0


@contextlib.contextmanager
def _field_limit(limit: int) -> Iterator[None]:
    global _limit_before_reads
    with _limit_lock:
        if not _active_limits:
            _limit_before_reads = csv.field_size_limit()
        _active_limits.append(limit)
        csv.field_size_limit(max(_active_limits))
    try:
        yield
    finally:
        with _limit_lock:
            _active_limits.remove(limit)
            csv.field_size_limit(max(_active_limits) if _active_limits else _limit_before_reads)
