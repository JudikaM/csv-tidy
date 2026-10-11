"""Strict TOML profiles (schema_version 1), option resolution, and output profiles.

Resolution order for every setting: explicit CLI/API override, then profile value, then the
application default. Output settings that are not set explicitly follow the *resolved*
source setting. List-valued transformation options (``trim``, ``normalize``) given as
overrides replace the profile list; they are never merged.
"""

from __future__ import annotations

import codecs
import difflib
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import tomli_w

from .errors import ProfileError
from .formats import NUMBER_FORMATS, compile_date_format

SCHEMA_VERSION = 1
DELIMITERS = (",", ";")
COLUMN_TYPES = ("text", "decimal", "date")
LINE_ENDINGS = ("crlf", "lf")
DUPLICATE_ROW_POLICIES = ("warn", "ignore")
DEDUPLICATE_MODES = ("off", "rows", "keys")

DEFAULT_DELIMITER = ","
DEFAULT_ENCODING = "utf-8"
DEFAULT_NUMBER_FORMAT = "canonical"
DEFAULT_DATE_FORMAT = "YYYY-MM-DD"
DEFAULT_MAX_FIELD_CHARS = 131072
MAX_FIELD_CHARS_LIMIT = 100_000_000

_TOP_KEYS = ("schema_version", "source", "output", "columns", "duplicates", "transform")
_SOURCE_KEYS = ("delimiter", "encoding", "number_format", "date_format", "max_field_chars")
_OUTPUT_KEYS = ("delimiter", "encoding", "number_format", "date_format", "line_ending")
_COLUMN_KEYS = ("type", "required", "number_format", "date_format")
_DUPLICATE_KEYS = ("rows", "keys")
_TRANSFORM_KEYS = ("trim", "normalize", "deduplicate")


@dataclass(frozen=True)
class ColumnSpec:
    """Declared rules for one column.

    ``number_format``/``date_format`` override the source default for this column.
    """

    name: str
    type: str = "text"
    required: bool = False
    number_format: str | None = None
    date_format: str | None = None


@dataclass(frozen=True)
class Profile:
    """A validated profile. ``None`` means "not set" so that defaults and overrides can apply."""

    source_delimiter: str | None = None
    source_encoding: str | None = None
    source_number_format: str | None = None
    source_date_format: str | None = None
    max_field_chars: int | None = None
    output_delimiter: str | None = None
    output_encoding: str | None = None
    output_number_format: str | None = None
    output_date_format: str | None = None
    line_ending: str | None = None
    columns: tuple[ColumnSpec, ...] = ()
    duplicate_rows: str | None = None
    duplicate_keys: tuple[tuple[str, ...], ...] = ()
    trim: tuple[str, ...] | None = None
    normalize: tuple[str, ...] | None = None
    deduplicate: str | None = None
    path: str | None = field(default=None, compare=False)
    # Absolute path captured when the profile file was read (used to protect it from writes).
    resolved_path: str | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Overrides:
    """Explicit option values (for example from the CLI). ``None`` leaves the profile value."""

    delimiter: str | None = None
    encoding: str | None = None
    number_format: str | None = None
    date_format: str | None = None
    output_delimiter: str | None = None
    output_encoding: str | None = None
    output_number_format: str | None = None
    output_date_format: str | None = None
    line_ending: str | None = None
    trim: tuple[str, ...] | None = None
    normalize: tuple[str, ...] | None = None
    deduplicate: str | None = None


@dataclass(frozen=True)
class SourceSettings:
    delimiter: str
    encoding: str
    number_format: str
    date_format: str
    max_field_chars: int


@dataclass(frozen=True)
class OutputSettings:
    delimiter: str
    encoding: str
    number_format: str
    date_format: str
    line_ending: str


@dataclass(frozen=True)
class Settings:
    """Fully resolved settings used by ``check`` and ``clean``."""

    source: SourceSettings
    output: OutputSettings
    columns: tuple[ColumnSpec, ...]
    duplicate_rows: str
    duplicate_keys: tuple[tuple[str, ...], ...]
    trim: tuple[str, ...]
    normalize: tuple[str, ...]
    deduplicate: str

    def column(self, name: str) -> ColumnSpec | None:
        return next((c for c in self.columns if c.name == name), None)

    def source_format(self, column: ColumnSpec) -> str:
        """Number grammar or date format text used to read ``column`` from the source."""
        if column.type == "decimal":
            return column.number_format or self.source.number_format
        return column.date_format or self.source.date_format

    def output_format(self, column: ColumnSpec) -> str:
        """Format of ``column`` in the cleaned output (unchanged unless normalized)."""
        if column.name not in self.normalize:
            return self.source_format(column)
        if column.type == "decimal":
            return self.output.number_format
        return self.output.date_format

    def referenced_columns(self) -> tuple[str, ...]:
        names = [c.name for c in self.columns]
        names += list(self.trim) + list(self.normalize)
        names += [name for key in self.duplicate_keys for name in key]
        return tuple(dict.fromkeys(names))


# --------------------------------------------------------------------------- loading


def load_profile(path: str | Path) -> Profile:
    """Read and strictly validate a TOML profile file."""
    label = str(path)
    path = Path(path)
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        raise ProfileError(f"profile not found: {path}") from None
    except OSError as exc:
        raise ProfileError(f"cannot read profile {path}: {exc.strerror or exc}") from None
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"profile {path} is not valid TOML: {exc}") from None
    return replace(profile_from_dict(data, source=label), resolved_path=str(path.resolve()))


def profile_from_dict(data: Mapping[str, Any], source: str = "profile") -> Profile:
    """Validate a parsed profile mapping and return a ``Profile``."""
    where = source
    _check_keys(data, _TOP_KEYS, where)
    if "schema_version" not in data:
        raise ProfileError(
            f"{where}: missing required key 'schema_version' (use schema_version = 1)"
        )
    version = data["schema_version"]
    if not _is_int(version) or version != SCHEMA_VERSION:
        raise ProfileError(
            f"{where}: unsupported schema_version {version!r}; this version supports 1"
        )

    src = _table(data, "source", where)
    _check_keys(src, _SOURCE_KEYS, f"{where} [source]")
    out = _table(data, "output", where)
    _check_keys(out, _OUTPUT_KEYS, f"{where} [output]")
    dup = _table(data, "duplicates", where)
    _check_keys(dup, _DUPLICATE_KEYS, f"{where} [duplicates]")
    tr = _table(data, "transform", where)
    _check_keys(tr, _TRANSFORM_KEYS, f"{where} [transform]")

    columns = []
    for name, spec in _table(data, "columns", where).items():
        cwhere = f"{where} [columns.{name}]"
        if not name.strip():
            raise ProfileError(f"{where}: column names must not be empty")
        if not isinstance(spec, dict):
            raise ProfileError(f"{cwhere}: must be a table")
        _check_keys(spec, _COLUMN_KEYS, cwhere)
        ctype = _choice(spec.get("type", "text"), COLUMN_TYPES, f"{cwhere} type")
        required = spec.get("required", False)
        if not isinstance(required, bool):
            raise ProfileError(f"{cwhere}: 'required' must be true or false")
        number_format = date_format = None
        if "number_format" in spec:
            if ctype != "decimal":
                raise ProfileError(f"{cwhere}: 'number_format' is only valid for decimal columns")
            number_format = _choice(
                spec["number_format"], NUMBER_FORMATS, f"{cwhere} number_format"
            )
        if "date_format" in spec:
            if ctype != "date":
                raise ProfileError(f"{cwhere}: 'date_format' is only valid for date columns")
            date_format = check_date_format(spec["date_format"], f"{cwhere} date_format")
        columns.append(ColumnSpec(name, ctype, required, number_format, date_format))

    profile = Profile(
        source_delimiter=_opt_choice(src, "delimiter", DELIMITERS, f"{where} [source]"),
        source_encoding=_opt_encoding(src, f"{where} [source]"),
        source_number_format=_opt_choice(src, "number_format", NUMBER_FORMATS, f"{where} [source]"),
        source_date_format=_opt_date(src, f"{where} [source]"),
        max_field_chars=_opt_max_field(src, f"{where} [source]"),
        output_delimiter=_opt_choice(out, "delimiter", DELIMITERS, f"{where} [output]"),
        output_encoding=_opt_encoding(out, f"{where} [output]"),
        output_number_format=_opt_choice(out, "number_format", NUMBER_FORMATS, f"{where} [output]"),
        output_date_format=_opt_date(out, f"{where} [output]"),
        line_ending=_opt_choice(out, "line_ending", LINE_ENDINGS, f"{where} [output]"),
        columns=tuple(columns),
        duplicate_rows=_opt_choice(dup, "rows", DUPLICATE_ROW_POLICIES, f"{where} [duplicates]"),
        duplicate_keys=_keys(dup.get("keys", []), f"{where} [duplicates] keys"),
        trim=_names(tr["trim"], f"{where} [transform] trim") if "trim" in tr else None,
        normalize=_names(tr["normalize"], f"{where} [transform] normalize")
        if "normalize" in tr
        else None,
        deduplicate=_opt_choice(tr, "deduplicate", DEDUPLICATE_MODES, f"{where} [transform]"),
        path=source if source != "profile" else None,
    )
    # Cross-reference checks that do not depend on overrides.
    resolve_settings(profile)
    return profile


# --------------------------------------------------------------------------- resolution


def _first(*values: Any) -> Any:
    return next(v for v in values if v is not None)


def resolve_settings(
    profile: Profile | None = None, overrides: Overrides | None = None
) -> Settings:
    """Apply override > profile > default precedence and validate cross-references."""
    if profile is not None:
        validate_profile(profile)
    p = profile or Profile()
    o = overrides or Overrides()
    _validate_overrides(o)
    source = SourceSettings(
        delimiter=_first(o.delimiter, p.source_delimiter, DEFAULT_DELIMITER),
        encoding=_first(o.encoding, p.source_encoding, DEFAULT_ENCODING),
        number_format=_first(o.number_format, p.source_number_format, DEFAULT_NUMBER_FORMAT),
        date_format=_first(o.date_format, p.source_date_format, DEFAULT_DATE_FORMAT),
        max_field_chars=_first(p.max_field_chars, DEFAULT_MAX_FIELD_CHARS),
    )
    output = OutputSettings(
        delimiter=_first(o.output_delimiter, p.output_delimiter, source.delimiter),
        encoding=_first(o.output_encoding, p.output_encoding, source.encoding),
        number_format=_first(o.output_number_format, p.output_number_format, source.number_format),
        date_format=_first(o.output_date_format, p.output_date_format, source.date_format),
        line_ending=_first(o.line_ending, p.line_ending, "crlf"),
    )
    settings = Settings(
        source=source,
        output=output,
        columns=p.columns,
        duplicate_rows=_first(p.duplicate_rows, "warn"),
        duplicate_keys=p.duplicate_keys,
        trim=_first(o.trim, p.trim, ()),
        normalize=_first(o.normalize, p.normalize, ()),
        deduplicate=_first(o.deduplicate, p.deduplicate, "off"),
    )
    for name in settings.normalize:
        column = settings.column(name)
        if column is None or column.type == "text":
            raise ProfileError(
                f'cannot normalize column \'{name}\': declare it with type = "decimal" or "date"'
            )
    if settings.deduplicate == "keys" and not settings.duplicate_keys:
        raise ProfileError('deduplicate = "keys" requires at least one key in [duplicates] keys')
    return settings


def validate_profile(profile: Profile) -> None:
    """Apply the TOML profile rules to a ``Profile`` object, including one built directly
    through the API, so that every entry point enforces the same constraints."""
    if not isinstance(profile, Profile):
        raise ProfileError("profile must be a Profile object, a path to a TOML file, or None")
    where = profile.path or "profile"
    for label, value, choices in (
        ("[source] delimiter", profile.source_delimiter, DELIMITERS),
        ("[output] delimiter", profile.output_delimiter, DELIMITERS),
        ("[source] number_format", profile.source_number_format, NUMBER_FORMATS),
        ("[output] number_format", profile.output_number_format, NUMBER_FORMATS),
        ("[output] line_ending", profile.line_ending, LINE_ENDINGS),
        ("[duplicates] rows", profile.duplicate_rows, DUPLICATE_ROW_POLICIES),
        ("[transform] deduplicate", profile.deduplicate, DEDUPLICATE_MODES),
    ):
        if value is not None:
            _choice(value, choices, f"{where} {label}")
    for label, value in (
        ("[source] encoding", profile.source_encoding),
        ("[output] encoding", profile.output_encoding),
    ):
        if value is not None:
            check_encoding(value, f"{where} {label}")
    for label, value in (
        ("[source] date_format", profile.source_date_format),
        ("[output] date_format", profile.output_date_format),
    ):
        if value is not None:
            check_date_format(value, f"{where} {label}")
    if profile.max_field_chars is not None:
        _opt_max_field({"max_field_chars": profile.max_field_chars}, f"{where} [source]")
    if not isinstance(profile.columns, (list, tuple)):
        raise ProfileError(f"{where}: columns must be a sequence of ColumnSpec objects")
    names: set[str] = set()
    for column in profile.columns:
        if not isinstance(column, ColumnSpec):
            raise ProfileError(f"{where}: columns must be ColumnSpec objects")
        cwhere = f"{where} [columns.{column.name}]"
        if not isinstance(column.name, str) or not column.name.strip():
            raise ProfileError(f"{where}: column names must be non-empty strings")
        if column.name in names:
            raise ProfileError(f"{where}: column {column.name!r} is declared more than once")
        names.add(column.name)
        _choice(column.type, COLUMN_TYPES, f"{cwhere} type")
        if not isinstance(column.required, bool):
            raise ProfileError(f"{cwhere}: 'required' must be true or false")
        if column.number_format is not None:
            if column.type != "decimal":
                raise ProfileError(f"{cwhere}: 'number_format' is only valid for decimal columns")
            _choice(column.number_format, NUMBER_FORMATS, f"{cwhere} number_format")
        if column.date_format is not None:
            if column.type != "date":
                raise ProfileError(f"{cwhere}: 'date_format' is only valid for date columns")
            check_date_format(column.date_format, f"{cwhere} date_format")
    keys = profile.duplicate_keys
    if not isinstance(keys, (list, tuple)) or not all(isinstance(k, (list, tuple)) for k in keys):
        raise ProfileError(f"{where} [duplicates] keys: must be a sequence of column lists")
    _keys([list(k) for k in keys], f"{where} [duplicates] keys")
    for label, value in (("trim", profile.trim), ("normalize", profile.normalize)):
        if value is None:
            continue
        if not isinstance(value, (list, tuple)):
            raise ProfileError(f"{where} [transform] {label}: must be a list of column names")
        _names(list(value), f"{where} [transform] {label}")


def _validate_overrides(o: Overrides) -> None:
    where = "option"
    for name, value, choices in (
        ("--delimiter", o.delimiter, DELIMITERS),
        ("--output-delimiter", o.output_delimiter, DELIMITERS),
        ("--number-format", o.number_format, NUMBER_FORMATS),
        ("--output-number-format", o.output_number_format, NUMBER_FORMATS),
        ("--line-ending", o.line_ending, LINE_ENDINGS),
        ("--deduplicate", o.deduplicate, DEDUPLICATE_MODES),
    ):
        if value is not None:
            _choice(value, choices, f"{where} {name}")
    for name, value in (("--encoding", o.encoding), ("--output-encoding", o.output_encoding)):
        if value is not None:
            check_encoding(value, f"{where} {name}")
    for name, value in (
        ("--date-format", o.date_format),
        ("--output-date-format", o.output_date_format),
    ):
        if value is not None:
            check_date_format(value, f"{where} {name}")
    for name, value in (("--trim", o.trim), ("--normalize", o.normalize)):
        if value is None:
            continue
        if not isinstance(value, (list, tuple)):
            raise ProfileError(f"{where} {name}: must be a list of column names")
        _names(list(value), f"{where} {name}")


# --------------------------------------------------------------------------- output profile


def output_profile(settings: Settings) -> Profile:
    """Describe the cleaned output so that it can be checked and cleaned again.

    The output format becomes the source format; selected transformations are kept and are
    no-ops on already-clean output, which makes a second clean idempotent.
    """
    columns = []
    for column in settings.columns:
        fmt = settings.output_format(column) if column.type != "text" else None
        columns.append(
            ColumnSpec(
                column.name,
                column.type,
                column.required,
                number_format=fmt if column.type == "decimal" else None,
                date_format=fmt if column.type == "date" else None,
            )
        )
    out = settings.output
    return Profile(
        source_delimiter=out.delimiter,
        source_encoding=out.encoding,
        source_number_format=out.number_format,
        source_date_format=out.date_format,
        max_field_chars=settings.source.max_field_chars,
        output_delimiter=out.delimiter,
        output_encoding=out.encoding,
        output_number_format=out.number_format,
        output_date_format=out.date_format,
        line_ending=out.line_ending,
        columns=tuple(columns),
        duplicate_rows=settings.duplicate_rows,
        duplicate_keys=settings.duplicate_keys,
        trim=settings.trim,
        normalize=settings.normalize,
        deduplicate=settings.deduplicate,
    )


def profile_to_dict(profile: Profile) -> dict[str, Any]:
    """Convert a profile to the TOML document structure (unset values are omitted)."""

    def pick(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        return {k: v for k, v in pairs if v is not None}

    doc: dict[str, Any] = {"schema_version": SCHEMA_VERSION}
    for name, table in (
        (
            "source",
            pick(
                [
                    ("delimiter", profile.source_delimiter),
                    ("encoding", profile.source_encoding),
                    ("number_format", profile.source_number_format),
                    ("date_format", profile.source_date_format),
                    ("max_field_chars", profile.max_field_chars),
                ]
            ),
        ),
        (
            "output",
            pick(
                [
                    ("delimiter", profile.output_delimiter),
                    ("encoding", profile.output_encoding),
                    ("number_format", profile.output_number_format),
                    ("date_format", profile.output_date_format),
                    ("line_ending", profile.line_ending),
                ]
            ),
        ),
    ):
        if table:
            doc[name] = table
    if profile.columns:
        doc["columns"] = {
            c.name: pick(
                [
                    ("type", c.type),
                    ("required", c.required),
                    ("number_format", c.number_format),
                    ("date_format", c.date_format),
                ]
            )
            for c in profile.columns
        }
    dup = pick(
        [
            ("rows", profile.duplicate_rows),
            ("keys", [list(k) for k in profile.duplicate_keys] or None),
        ]
    )
    if dup:
        doc["duplicates"] = dup
    tr = pick(
        [
            ("trim", list(profile.trim) if profile.trim is not None else None),
            ("normalize", list(profile.normalize) if profile.normalize is not None else None),
            ("deduplicate", profile.deduplicate),
        ]
    )
    if tr:
        doc["transform"] = tr
    return doc


def profile_to_toml(profile: Profile, header: str = "") -> str:
    """Serialize a profile with ``tomli_w``; the result is verified by parsing it back."""
    text = tomli_w.dumps(profile_to_dict(profile))
    if profile_from_dict(tomllib.loads(text)) != profile:
        raise ProfileError("internal error: generated profile does not round-trip")
    prefix = "".join(f"# {line}\n" for line in header.splitlines())
    return prefix + text


# --------------------------------------------------------------------------- validators


def check_encoding(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProfileError(f"{where}: encoding must be a non-empty string")
    try:
        codecs.lookup(value)
    except LookupError:
        raise ProfileError(f"{where}: unknown encoding '{value}'") from None
    try:
        # Binary (base64_codec, hex_codec) and text-to-text (rot_13) codecs exist but cannot
        # convert between text and bytes; str.encode/bytes.decode reject them.
        "".encode(value)
        b"".decode(value)
    except LookupError:
        raise ProfileError(f"{where}: '{value}' is not a text encoding") from None
    return value


def check_date_format(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise ProfileError(f'{where}: date format must be a string such as "DD/MM/YYYY"')
    try:
        compile_date_format(value)
    except ValueError as exc:
        raise ProfileError(f"{where}: {exc}") from None
    return value


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_keys(table: Mapping[str, Any], allowed: tuple[str, ...], where: str) -> None:
    for key in table:
        if key not in allowed:
            hint = difflib.get_close_matches(key, allowed, n=1)
            suffix = (
                f"; did you mean '{hint[0]}'?" if hint else f"; allowed keys: {', '.join(allowed)}"
            )
            raise ProfileError(f"{where}: unknown key '{key}'{suffix}")


def _table(data: Mapping[str, Any], key: str, where: str) -> Mapping[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ProfileError(f"{where}: '{key}' must be a table")
    return value


def _choice(value: Any, choices: tuple[str, ...], where: str) -> str:
    if not isinstance(value, str) or value not in choices:
        options = ", ".join(repr(c) for c in choices)
        raise ProfileError(f"{where}: invalid value {value!r}; expected one of {options}")
    return value


def _opt_choice(
    table: Mapping[str, Any], key: str, choices: tuple[str, ...], where: str
) -> str | None:
    return _choice(table[key], choices, f"{where} {key}") if key in table else None


def _opt_encoding(table: Mapping[str, Any], where: str) -> str | None:
    return check_encoding(table["encoding"], f"{where} encoding") if "encoding" in table else None


def _opt_date(table: Mapping[str, Any], where: str) -> str | None:
    return (
        check_date_format(table["date_format"], f"{where} date_format")
        if "date_format" in table
        else None
    )


def _opt_max_field(table: Mapping[str, Any], where: str) -> int | None:
    if "max_field_chars" not in table:
        return None
    value = table["max_field_chars"]
    if not _is_int(value) or not 1 <= value <= MAX_FIELD_CHARS_LIMIT:
        raise ProfileError(
            f"{where} max_field_chars: must be an integer from 1 to {MAX_FIELD_CHARS_LIMIT}"
        )
    return value


def _names(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise ProfileError(f"{where}: must be a list of column names")
    if len(set(value)) != len(value):
        raise ProfileError(f"{where}: column names must not repeat")
    return tuple(value)


def _keys(value: Any, where: str) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, list):
        raise ProfileError(f'{where}: must be a list of key column lists, e.g. [["id"]]')
    keys = []
    for item in value:
        if not isinstance(item, list) or not item:
            raise ProfileError(f"{where}: each key must be a non-empty list of column names")
        keys.append(_names(item, where))
    if len(set(keys)) != len(keys):
        raise ProfileError(f"{where}: duplicate key definitions")
    return tuple(keys)
