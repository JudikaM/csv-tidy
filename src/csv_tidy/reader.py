"""Strict CSV reading that keeps every field as text and tracks source line ranges."""

from __future__ import annotations

import codecs
import csv
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

    table = Table(bom=bom)
    previous_limit = csv.field_size_limit(max_field_chars)
    try:
        with path.open(encoding=read_encoding, errors="strict", newline="") as handle:
            reader = csv.reader(
                handle,
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
                    previous = end
                    if not row:
                        table.blank_lines.append(start)
                    elif table.header is None:
                        table.header, table.header_line = tuple(row), start
                    else:
                        table.records.append(Record(len(table.records) + 1, start, end, tuple(row)))
                table.physical_lines = reader.line_num
            except csv.Error as exc:
                table.physical_lines = reader.line_num
                text = str(exc)
                if "field larger than field limit" in text:
                    table.fatal = FatalError(
                        "field_too_large",
                        f"a field in the record starting at line {previous + 1} "
                        "exceeds the limit of "
                        f"{max_field_chars} characters (source max_field_chars)",
                        previous + 1,
                    )
                else:
                    table.fatal = FatalError(
                        "malformed_csv",
                        f"malformed CSV in the record starting at line {previous + 1} "
                        f"(detected at line {reader.line_num}): {text}",
                        previous + 1,
                    )
            except UnicodeDecodeError as exc:
                line = _decode_error_line(path, read_encoding)
                table.fatal = FatalError(
                    "decode_error",
                    f"the file is not valid {encoding} near line {line}: {exc.reason}; "
                    "no characters were replaced or skipped",
                    line,
                )
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}") from None
    finally:
        csv.field_size_limit(previous_limit)
    return table


def _decode_error_line(path: Path, encoding: str) -> int | None:
    data = path.read_bytes()
    try:
        data.decode(encoding)
    except UnicodeDecodeError as exc:
        return data[: exc.start].count(b"\n") + 1
    return None
