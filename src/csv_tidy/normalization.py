"""Explicit transformations in a fixed order: trim, normalize, deduplicate.

Only selected columns are touched. Records with a wrong field count are never modified or
removed. Values that cannot be parsed are left unchanged so output validation reports them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .formats import compile_date_format, format_number, parse_number
from .reader import Record
from .schema import Settings


@dataclass(frozen=True)
class FieldChange:
    """A field whose final value differs from the source value."""

    record: int
    line_start: int
    column: str
    before: str
    after: str
    steps: tuple[str, ...]


@dataclass(frozen=True)
class RemovedRecord:
    """A record removed by explicit deduplication (the first occurrence is kept)."""

    record: int
    line_start: int
    reason: str
    kept_record: int
    key: tuple[str, ...] | None = None


@dataclass(frozen=True)
class TransformResult:
    records: list[Record]
    changes: list[FieldChange]
    removed: list[RemovedRecord]
    # (record index, column) of non-empty values selected for normalization that could not
    # be parsed in their source format. They stay errors even if they happen to look valid
    # in the output format.
    unconverted: frozenset[tuple[int, str]] = frozenset()


def transform(
    header: Sequence[str], records: Sequence[Record], settings: Settings
) -> TransformResult:
    index: dict[str, int] = {}
    for position, name in enumerate(header):
        index.setdefault(name, position)
    width = len(header)
    trim_positions = [(n, index[n]) for n in settings.trim if n in index]
    normalizers = []
    for name in settings.normalize:
        column = settings.column(name)
        if column is None or name not in index:
            continue
        source_fmt, output_fmt = settings.source_format(column), settings.output_format(column)
        if column.type == "decimal":
            normalizers.append((name, index[name], _number_converter(source_fmt, output_fmt)))
        else:
            normalizers.append((name, index[name], _date_converter(source_fmt, output_fmt)))

    transformed: list[Record] = []
    unconverted: set[tuple[int, str]] = set()
    steps_by_record: dict[int, dict[int, list[str]]] = {}
    for rec in records:
        if len(rec.fields) != width:
            transformed.append(rec)
            continue
        fields = list(rec.fields)
        steps: dict[int, list[str]] = {}
        for _name, pos in trim_positions:
            trimmed = fields[pos].strip()
            if trimmed != fields[pos]:
                fields[pos] = trimmed
                steps.setdefault(pos, []).append("trim")
        for name, pos, convert in normalizers:
            value = fields[pos]
            if not value.strip():
                continue
            converted = convert(value)
            if converted is None:
                unconverted.add((rec.index, name))
            elif converted != value:
                fields[pos] = converted
                steps.setdefault(pos, []).append("normalize")
        transformed.append(Record(rec.index, rec.line_start, rec.line_end, tuple(fields)))
        steps_by_record[rec.index] = steps

    kept, removed = _deduplicate(transformed, settings, index, width)

    original = {rec.index: rec for rec in records}
    changes = []
    for rec in kept:
        for pos, steps in sorted(steps_by_record.get(rec.index, {}).items()):
            before = original[rec.index].fields[pos]
            if rec.fields[pos] != before:
                changes.append(
                    FieldChange(
                        rec.index,
                        rec.line_start,
                        header[pos],
                        before,
                        rec.fields[pos],
                        tuple(steps),
                    )
                )
    kept_ids = {rec.index for rec in kept}
    failed = frozenset(key for key in unconverted if key[0] in kept_ids)
    return TransformResult(kept, changes, removed, failed)


def _deduplicate(records: list[Record], settings: Settings, index: dict[str, int], width: int):
    if settings.deduplicate == "off":
        return records, []
    keys = []
    if settings.deduplicate == "keys":
        keys = [
            (key, [index[n] for n in key])
            for key in settings.duplicate_keys
            if all(n in index for n in key)
        ]
    seen_rows: dict[tuple[str, ...], Record] = {}
    seen_keys: list[dict[tuple[str, ...], Record]] = [{} for _ in keys]
    kept: list[Record] = []
    removed: list[RemovedRecord] = []
    for rec in records:
        if len(rec.fields) != width:
            kept.append(rec)
            continue
        earlier = seen_rows.get(rec.fields)
        if earlier is not None:
            removed.append(
                RemovedRecord(rec.index, rec.line_start, "duplicate_record", earlier.index)
            )
            continue
        hit = None
        for (key, positions), seen in zip(keys, seen_keys, strict=True):
            values = tuple(rec.fields[p] for p in positions)
            if all(v.strip() for v in values) and values in seen:
                hit = (key, seen[values])
                break
        if hit is not None:
            removed.append(
                RemovedRecord(rec.index, rec.line_start, "duplicate_key", hit[1].index, hit[0])
            )
            continue
        seen_rows[rec.fields] = rec
        for (_key, positions), seen in zip(keys, seen_keys, strict=True):
            values = tuple(rec.fields[p] for p in positions)
            if all(v.strip() for v in values):
                seen.setdefault(values, rec)
        kept.append(rec)
    return kept, removed


def _number_converter(source_fmt: str, output_fmt: str):
    def convert(value: str) -> str | None:
        parsed = parse_number(value, source_fmt)
        return None if parsed is None else format_number(parsed, output_fmt)

    return convert


def _date_converter(source_fmt: str, output_fmt: str):
    source, output = compile_date_format(source_fmt), compile_date_format(output_fmt)

    def convert(value: str) -> str | None:
        parsed = source.parse(value)
        return None if parsed is None else output.format(parsed)

    return convert
