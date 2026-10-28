"""Validation rules that turn a table into a deterministic list of issues.

The same function validates the source (``stage="source"``, source formats) and the cleaned
result (``stage="output"``, output formats). Checks never modify field values.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypedDict

from .formats import (
    NUMBER_EXAMPLES,
    DateFormat,
    compile_date_format,
    explain_invalid_date,
    explain_invalid_number,
    parse_number,
)
from .reader import Record, Table
from .schema import DELIMITERS, ColumnSpec, Settings

ERROR = "error"
WARNING = "warning"
FATAL = "fatal"


@dataclass(frozen=True)
class Issue:
    """One finding. ``record`` is the 1-based data record index; lines are physical source lines.

    For ``clean`` results, source issues carry ``status`` ("resolved", "unresolved" or
    "removed") and output issues carry ``introduced`` (true when transformations created them).

    ``remedy`` names the kind of repair the suggestion describes, so that an interface can
    explain it with its own controls: ``trim``, ``number_format``, ``date_format``,
    ``deduplicate_rows``, ``deduplicate_keys``, ``delimiter``, ``encoding``, ``quoting``, or
    ``max_field_chars``. ``None`` means the value can only be corrected in the source.
    """

    code: str
    severity: str
    message: str
    suggestion: str
    stage: str
    record: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    column: str | None = None
    value: str | None = None
    related_record: int | None = None
    related_line: int | None = None
    status: str | None = None
    introduced: bool | None = None
    remedy: str | None = None


class _Where(TypedDict):
    """Location fields shared by every issue about one record."""

    stage: str
    record: int
    line_start: int
    line_end: int


def _quote(value: str, limit: int = 60) -> str:
    shown = value if len(value) <= limit else value[:limit] + "..."
    return repr(shown)


def validate_table(
    table: Table,
    settings: Settings,
    stage: str,
    include_blank_lines: bool = True,
    unconverted: frozenset[tuple[int, str]] = frozenset(),
) -> list[Issue]:
    """Return all issues for ``table`` in deterministic order.

    ``unconverted`` lists (record, column) values selected for normalization that could not
    be parsed in their source format; at the output stage they are always reported.
    """
    issues: list[Issue] = []
    if include_blank_lines:
        for line in table.blank_lines:
            issues.append(
                Issue(
                    "blank_line",
                    WARNING,
                    f"Line {line} is blank and is not a data record.",
                    "Remove blank lines if they are not intended; they are not exported.",
                    stage,
                    line_start=line,
                    line_end=line,
                )
            )
    if table.header is None:
        if table.complete:
            issues.append(
                Issue(
                    "empty_file",
                    ERROR,
                    "The file contains no header row.",
                    "Provide a CSV file whose first row contains the column names.",
                    stage,
                )
            )
        return _sorted(issues, ())
    issues.extend(_header_issues(table, settings, stage))
    if table.complete and not table.records:
        issues.append(
            Issue(
                "no_records",
                WARNING,
                "The file has a header row but no data records.",
                "Check that the export contains data.",
                stage,
            )
        )
    issues.extend(_record_issues(table.header, table.records, settings, stage, unconverted))
    return _sorted(issues, table.header)


def _header_issues(table: Table, settings: Settings, stage: str) -> list[Issue]:
    header = table.header or ()
    line = table.header_line
    issues: list[Issue] = []
    first_seen: dict[str, int] = {}
    for position, name in enumerate(header, start=1):
        if not name.strip():
            issues.append(
                Issue(
                    "empty_header",
                    ERROR,
                    f"Header column {position} is empty.",
                    "Give every column a unique, non-empty name.",
                    stage,
                    line_start=line,
                    line_end=line,
                    column=name,
                    value=name,
                )
            )
            continue
        if name in first_seen:
            issues.append(
                Issue(
                    "duplicate_header",
                    ERROR,
                    f"Header {_quote(name)} appears in columns {first_seen[name]} and {position}.",
                    "Rename one of the columns; duplicate headers make values ambiguous.",
                    stage,
                    line_start=line,
                    line_end=line,
                    column=name,
                    value=name,
                )
            )
        else:
            first_seen[name] = position
        if name != name.strip():
            issues.append(
                Issue(
                    "header_whitespace",
                    WARNING,
                    f"Header {_quote(name)} has leading or trailing whitespace; "
                    "names are matched exactly.",
                    "Remove the whitespace in the source header "
                    "or use the exact name in the profile.",
                    stage,
                    line_start=line,
                    line_end=line,
                    column=name,
                    value=name,
                )
            )
    if len(header) == 1 and settings.source.delimiter not in header[0]:
        found = [d for d in DELIMITERS if d != settings.source.delimiter and d in header[0]]
        if found:
            other = found[0]
            option = "--delimiter tab" if other == "\t" else "--delimiter"
            issues.append(
                Issue(
                    "possible_wrong_delimiter",
                    WARNING,
                    f"The header is a single column containing {other!r}; "
                    f"the file may use {other!r} as delimiter "
                    f"instead of {settings.source.delimiter!r}.",
                    f"Set the delimiter to {other!r} with {option} "
                    "or in the profile [source] table.",
                    stage,
                    line_start=line,
                    line_end=line,
                    remedy="delimiter",
                )
            )
    present = set(header)
    for name in settings.referenced_columns():
        if name not in present:
            issues.append(
                Issue(
                    "missing_column",
                    ERROR,
                    f"Column {_quote(name)} is referenced by the profile or options "
                    "but is not in the header.",
                    "Check the column name and header spelling (names are case-sensitive).",
                    stage,
                    line_start=line,
                    line_end=line,
                    column=name,
                )
            )
    return issues


def _record_issues(
    header: Sequence[str],
    records: Sequence[Record],
    settings: Settings,
    stage: str,
    unconverted: frozenset[tuple[int, str]],
) -> list[Issue]:
    index: dict[str, int] = {}
    for position, name in enumerate(header):
        index.setdefault(name, position)
    # The format is the number grammar (str) for decimal columns, the compiled date format
    # for date columns, and None for text columns.
    rules: list[tuple[ColumnSpec, int, str | DateFormat | None]] = []
    for column in settings.columns:
        if column.name not in index:
            continue
        if column.type == "text":
            fmt = None
        else:
            text = (
                settings.source_format(column)
                if stage == "source"
                else settings.output_format(column)
            )
            fmt = text if column.type == "decimal" else compile_date_format(text)
        rules.append((column, index[column.name], fmt))
    keys = [
        (key, [index[n] for n in key])
        for key in settings.duplicate_keys
        if all(n in index for n in key)
    ]

    issues: list[Issue] = []
    seen_rows: dict[tuple[str, ...], Record] = {}
    seen_keys: list[dict[tuple[str, ...], Record]] = [{} for _ in keys]
    width = len(header)
    for rec in records:
        where: _Where = {
            "stage": stage,
            "record": rec.index,
            "line_start": rec.line_start,
            "line_end": rec.line_end,
        }
        if len(rec.fields) != width:
            issues.append(
                Issue(
                    "inconsistent_columns",
                    ERROR,
                    f"Record {rec.index} has {len(rec.fields)} fields; the header has {width}.",
                    "Check for a missing or extra delimiter, or an unquoted delimiter "
                    "inside a value. This record is not checked further "
                    "and is never transformed.",
                    **where,
                )
            )
            continue
        if stage == "output":
            issues.extend(_oversized_fields(header, rec, settings, where))
        for column, position, fmt in rules:
            value = rec.fields[position]
            if not value.strip():
                if column.required:
                    issues.append(
                        Issue(
                            "missing_required",
                            ERROR,
                            f"Required column {_quote(column.name)} is empty.",
                            "Provide a value in the source; CSV Tidy never invents missing values.",
                            column=column.name,
                            value=value,
                            **where,
                        )
                    )
                continue
            # A value selected for normalization that could not be parsed in its source
            # format was left unchanged. It stays invalid even if it happens to match the
            # output format, and it is explained in source terms.
            failed = (rec.index, column.name) in unconverted
            normalized = stage == "output" and column.name in settings.normalize
            if isinstance(fmt, str) and (failed or parse_number(value, fmt) is None):
                why_fmt = settings.source_format(column) if normalized else fmt
                why = explain_invalid_number(value, why_fmt)
                if normalized:
                    why = f"it could not be normalized because {why} (source format '{why_fmt}')"
                issues.append(
                    Issue(
                        "invalid_number",
                        ERROR,
                        f"{_quote(value)} is not a valid number: {why}.",
                        _number_suggestion(value, why_fmt, column.name, settings, stage),
                        column=column.name,
                        value=value,
                        remedy=_number_remedy(value, why_fmt),
                        **where,
                    )
                )
            elif isinstance(fmt, DateFormat) and (failed or fmt.parse(value) is None):
                why_date = (
                    compile_date_format(settings.source_format(column)) if normalized else fmt
                )
                why = explain_invalid_date(value, why_date)
                if normalized:
                    why = f"it could not be normalized because {why}"
                issues.append(
                    Issue(
                        "invalid_date",
                        ERROR,
                        f"{_quote(value)} is not a valid date: {why}.",
                        _date_suggestion(value, why_date.text, column.name, settings, stage),
                        column=column.name,
                        value=value,
                        remedy=_date_remedy(value, why_date.text),
                        **where,
                    )
                )
        if settings.duplicate_rows == "warn":
            earlier = seen_rows.get(rec.fields)
            if earlier is None:
                seen_rows[rec.fields] = rec
            else:
                issues.append(
                    Issue(
                        "duplicate_record",
                        WARNING,
                        f"Record {rec.index} is identical to record {earlier.index} "
                        f"(line {earlier.line_start}).",
                        "Remove it in the source or enable "
                        'deduplicate = "rows" to keep the first copy.',
                        related_record=earlier.index,
                        related_line=earlier.line_start,
                        remedy="deduplicate_rows",
                        **where,
                    )
                )
        for (key, positions), seen in zip(keys, seen_keys, strict=True):
            values = tuple(rec.fields[p] for p in positions)
            if any(not v.strip() for v in values):
                continue
            earlier = seen.get(values)
            if earlier is None:
                seen[values] = rec
            else:
                issues.append(
                    Issue(
                        "duplicate_key",
                        ERROR,
                        f"Key ({', '.join(key)}) = {_quote(' | '.join(values))} "
                        f"already appears in record {earlier.index} (line {earlier.line_start}).",
                        "Fix the duplicated identifier, or enable "
                        'deduplicate = "keys" to keep the first record.',
                        column=", ".join(key),
                        value=" | ".join(values),
                        related_record=earlier.index,
                        related_line=earlier.line_start,
                        remedy="deduplicate_keys",
                        **where,
                    )
                )
    return issues


def _oversized_fields(
    header: Sequence[str], rec: Record, settings: Settings, where: _Where
) -> list[Issue]:
    """Output fields must stay readable with the same ``max_field_chars`` limit, which the
    generated output profile keeps; normalization can make values longer."""
    limit = settings.source.max_field_chars
    return [
        Issue(
            "field_too_large",
            ERROR,
            f"The cleaned value has {len(value)} characters, more than max_field_chars "
            f"({limit}); the output could not be read back with its output profile.",
            "Raise [source] max_field_chars in the profile, or do not normalize this column.",
            column=name,
            value=value,
            remedy="max_field_chars",
            **where,
        )
        for name, value in zip(header, rec.fields, strict=True)
        if len(value) > limit
    ]


def _number_remedy(value: str, fmt: str) -> str:
    if value != value.strip() and parse_number(value.strip(), fmt) is not None:
        return "trim"
    return "number_format"


def _date_remedy(value: str, fmt_text: str) -> str | None:
    fmt = compile_date_format(fmt_text)
    if value != value.strip() and fmt.parse(value.strip()) is not None:
        return "trim"
    if fmt.matches_shape(value.strip()):
        return None  # a real calendar error: only the source can be corrected
    return "date_format"


def _number_suggestion(value: str, fmt: str, column: str, settings: Settings, stage: str) -> str:
    if value != value.strip() and parse_number(value.strip(), fmt) is not None:
        if stage == "source":
            return f"Select trimming for {column!r} (transform trim) or fix the source value."
        return "Fix the source value; trimming was not selected for this column."
    return (
        f"Use the '{fmt}' format, for example {NUMBER_EXAMPLES[fmt]}, "
        "or correct the value in the source."
    )


def _date_suggestion(value: str, fmt_text: str, column: str, settings: Settings, stage: str) -> str:
    fmt = compile_date_format(fmt_text)
    if value != value.strip() and fmt.parse(value.strip()) is not None:
        if stage == "source":
            return f"Select trimming for {column!r} (transform trim) or fix the source value."
        return "Fix the source value; trimming was not selected for this column."
    if fmt.matches_shape(value.strip()):
        return "Correct the date in the source; invalid calendar dates are never guessed."
    return f"Write dates as {fmt_text} or set the column's date_format to the format actually used."


def _sorted(issues: list[Issue], header: Sequence[str]) -> list[Issue]:
    positions = {name: i for i, name in reversed(list(enumerate(header)))}

    def key(issue: Issue) -> tuple[bool, int, int, int, str]:
        column_pos = positions.get(issue.column or "", len(header))
        return (
            issue.record is not None,
            issue.record or 0,
            issue.line_start or 0,
            column_pos,
            issue.code,
        )

    return sorted(issues, key=key)
