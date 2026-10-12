"""Starting profiles built from a file's header.

Every column starts as ``text``. Types, formats, required columns, keys and transformations
come only from explicit choices (options or guided answers); nothing is inferred from the
values or the column names. Functions here never print: guided questions go through the
``ask``/``say`` callables supplied by the caller.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from . import __version__
from .errors import CsvTidyError, InputError, ProfileError
from .formats import NUMBER_EXAMPLES, NUMBER_FORMATS
from .reader import read_csv
from .schema import (
    DEFAULT_DATE_FORMAT,
    DEFAULT_DELIMITER,
    DEFAULT_ENCODING,
    DEFAULT_NUMBER_FORMAT,
    ColumnSpec,
    Overrides,
    Profile,
    check_date_format,
    check_encoding,
    profile_to_toml,
    resolve_settings,
)
from .validation import validate_table

UNUSABLE_HEADER_CODES = ("empty_header", "duplicate_header", "possible_wrong_delimiter")
QUIT_WORDS = ("q", "quit", "cancel")


class Cancelled(CsvTidyError):
    """The guided questions were stopped before the profile was confirmed."""


@dataclass(frozen=True)
class Header:
    """Column names of a file, with one example value per column for display only."""

    columns: tuple[str, ...]
    examples: tuple[str | None, ...]
    delimiter: str
    encoding: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Choices:
    """Explicit selections for a new profile. Unset formats fall back to the defaults."""

    number_format: str | None = None
    date_format: str | None = None
    decimal: tuple[str, ...] = ()
    date: tuple[str, ...] = ()
    required: tuple[str, ...] = ()
    keys: tuple[tuple[str, ...], ...] = ()
    trim: tuple[str, ...] = ()
    normalize: tuple[str, ...] = ()
    deduplicate: str | None = None
    output_number_format: str | None = None
    output_date_format: str | None = None


def read_header(path: str | Path, delimiter: str, encoding: str) -> Header:
    """Read the header of ``path`` with the given delimiter and encoding.

    Raises ``InputError``/``ProfileError`` when the header cannot name columns reliably: no
    header row, an unreadable start of the file, empty or duplicate names, or a single column
    that contains the other delimiter.
    """
    settings = resolve_settings(None, Overrides(delimiter=delimiter, encoding=encoding))
    table = read_csv(path, delimiter, encoding, settings.source.max_field_chars)
    issues = validate_table(table, settings, "source")
    fatal = table.fatal
    if table.header is None:
        if fatal is not None:
            raise InputError(f"cannot read the header of {path}: {fatal.code}: {fatal.message}")
        raise InputError(f"{path} has no header row; a profile needs the column names")
    for issue in issues:
        if issue.code in UNUSABLE_HEADER_CODES:
            raise ProfileError(
                f"cannot build a profile from the header of {path} ({issue.code}): "
                f"{issue.message} {issue.suggestion}"
            )
    warnings = [
        f"{issue.code}: {issue.message}" for issue in issues if issue.code == "header_whitespace"
    ]
    if fatal is not None:
        warnings.append(
            f"{fatal.code}: {fatal.message}. The header was read, but check will stop there."
        )
    # One example per column, for display in the guided questions only.
    examples: list[str | None] = [None] * len(table.header)
    for record in table.records[:200]:
        if len(record.fields) != len(table.header):
            continue
        for position, value in enumerate(record.fields):
            if examples[position] is None and value.strip():
                examples[position] = value
    return Header(table.header, tuple(examples), delimiter, encoding, tuple(warnings))


def build_profile(header: Header, choices: Choices | None = None) -> Profile:
    """A validated profile for ``header``: all columns are text unless ``choices`` says so."""
    choices = choices or Choices()
    known = set(header.columns)
    for option, names in (
        ("--decimal", choices.decimal),
        ("--date", choices.date),
        ("--required", choices.required),
        ("--key", tuple(name for key in choices.keys for name in key)),
        ("--trim", choices.trim),
        ("--normalize", choices.normalize),
    ):
        for name in names:
            if name not in known:
                listed = ", ".join(repr(column) for column in header.columns)
                raise ProfileError(
                    f"{option}: {name!r} is not a column of this file; "
                    f"the columns are: {listed} (names are case-sensitive)"
                )
    both = [name for name in choices.decimal if name in choices.date]
    if both:
        raise ProfileError(
            f"column {both[0]!r} is selected with both --decimal and --date; choose one type"
        )
    columns = tuple(
        ColumnSpec(
            name,
            "decimal" if name in choices.decimal else "date" if name in choices.date else "text",
            name in choices.required,
        )
        for name in header.columns
    )
    profile = Profile(
        source_delimiter=header.delimiter,
        source_encoding=header.encoding,
        source_number_format=choices.number_format or DEFAULT_NUMBER_FORMAT,
        source_date_format=choices.date_format or DEFAULT_DATE_FORMAT,
        output_number_format=choices.output_number_format,
        output_date_format=choices.output_date_format,
        columns=columns,
        duplicate_rows="warn",
        duplicate_keys=tuple(tuple(key) for key in choices.keys),
        trim=tuple(choices.trim),
        normalize=tuple(choices.normalize),
        deduplicate=choices.deduplicate or "off",
    )
    resolve_settings(profile)  # the same cross-checks as a profile loaded from TOML
    return profile


def render_profile(profile: Profile, source_name: str) -> str:
    """TOML text for a new profile, written by the shared profile serializer."""
    lines = [
        f"CSV Tidy profile for {source_name}, created by csv-tidy {__version__} (profile init).",
        "Column types were chosen explicitly; nothing was inferred from the data or the",
        "column names. Columns left as text are not checked as numbers or dates.",
        'To change a column: type = "text" | "decimal" | "date", required = true | false.',
        'Per column, optionally: number_format = "id" | "us" | "canonical" (decimal) or',
        'date_format = "DD/MM/YYYY" (date). List columns to repair under [transform].',
    ]
    return profile_to_toml(profile, "\n".join(lines))


# --------------------------------------------------------------------------- guided questions

Ask = Callable[[str], str]
Say = Callable[[str], None]


def ask_source(ask: Ask, say: Say, delimiter: str | None, encoding: str | None) -> tuple[str, str]:
    """Ask for the delimiter and encoding that were not given as options."""
    if delimiter is None:
        say("How are the columns separated in the file? (This is never detected automatically.)")
        delimiter = _pick(
            ask, say, "Delimiter", [(",", "comma  ,"), (";", "semicolon  ;")], DEFAULT_DELIMITER
        )
    if encoding is None:
        encoding = _text(
            ask,
            say,
            f"Encoding of the file [{DEFAULT_ENCODING}]",
            DEFAULT_ENCODING,
            lambda value: check_encoding(value, "encoding"),
        )
    return delimiter, encoding


def guided_choices(header: Header, base: Choices, ask: Ask, say: Say) -> Choices:
    """Ask which columns are numbers or dates, required, keys, and what to repair.

    Raises ``Cancelled`` when the user quits. Answers are column numbers (``1,3``, ``2-4``),
    exact names, ``all`` or nothing; ``q`` quits. Values of ``base`` are offered as defaults.
    """
    names = header.columns
    say("")
    say(f"Columns (delimiter {header.delimiter!r}, encoding {header.encoding}):")
    width = max(len(name) for name in names)
    for number, (name, example) in enumerate(zip(names, header.examples, strict=True), start=1):
        shown = "(no value in the first records)" if example is None else f"e.g. {example!r}"
        say(f"  {number}. {name.ljust(width)}  {shown}")
    for warning in header.warnings:
        say(f"  Note: {warning}")
    say("Example values are shown to help you answer. CSV Tidy does not infer types from them.")
    say("Answer with column numbers (1,3 or 2-4), 'all', or press Enter for none; q cancels.")
    say("")

    decimal = _columns(ask, say, "Which columns hold decimal numbers?", names, base.decimal)
    number_format = base.number_format or DEFAULT_NUMBER_FORMAT
    if decimal:
        say("How are numbers written in the file?")
        number_format = _pick(ask, say, "Number format", _number_options(), number_format)
    rest = tuple(name for name in names if name not in decimal)
    date = _columns(
        ask, say, "Which columns hold dates?", names, base.date, allowed=rest, what="non-decimal"
    )
    date_format = base.date_format or DEFAULT_DATE_FORMAT
    if date:
        date_format = _text(
            ask,
            say,
            f"Date format in the file, for example DD/MM/YYYY or MM/DD/YYYY [{date_format}]",
            date_format,
            lambda value: check_date_format(value, "date format"),
        )
    required = _columns(ask, say, "Which columns must never be empty?", names, base.required)

    keys = list(base.keys)
    while True:
        label = f"Unique key {len(keys) + 1}: which column(s) together identify a record?"
        key = _columns(ask, say, label + " (Enter to finish)", names, ())
        if not key:
            break
        if key in keys:
            say("  That key is already listed.")
            continue
        keys.append(key)

    trim = _columns(ask, say, "Trim leading/trailing spaces in which columns?", names, base.trim)
    typed = tuple(name for name in names if name in decimal or name in date)
    normalize: tuple[str, ...] = ()
    output_number_format, output_date_format = base.output_number_format, base.output_date_format
    if typed:
        normalize = _columns(
            ask,
            say,
            "Rewrite which number/date columns in an output format?",
            names,
            tuple(name for name in base.normalize if name in typed),
            allowed=typed,
            what="decimal or date",
        )
        if any(name in decimal for name in normalize):
            say("How should numbers be written in the cleaned file?")
            output_number_format = _pick(
                ask, say, "Output number format", _number_options(), number_format
            )
        if any(name in date for name in normalize):
            output_date_format = _text(
                ask,
                say,
                f"Output date format [{date_format}]",
                date_format,
                lambda value: check_date_format(value, "date format"),
            )
    modes = [
        ("off", "keep every record"),
        ("rows", "remove later rows that are identical to an earlier row"),
    ]
    if keys:
        modes.append(("keys", "also remove later records with an already used key"))
    say("Remove duplicates when cleaning? (The first record is always kept.)")
    deduplicate = _pick(ask, say, "Duplicates", modes, base.deduplicate or "off")
    return replace(
        base,
        number_format=number_format,
        date_format=date_format,
        decimal=decimal,
        date=date,
        required=required,
        keys=tuple(keys),
        trim=trim,
        normalize=normalize,
        deduplicate=deduplicate,
        output_number_format=output_number_format,
        output_date_format=output_date_format,
    )


def confirm(ask: Ask, say: Say, question: str) -> bool:
    while True:
        answer = _answer(ask, f"{question} [y/N]").lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("", "n", "no"):
            return False
        say("  Please answer y or n (q cancels).")


def _number_options() -> list[tuple[str, str]]:
    return [(name, f"{name}, for example {NUMBER_EXAMPLES[name]}") for name in NUMBER_FORMATS]


def _answer(ask: Ask, prompt: str) -> str:
    try:
        answer = ask(prompt + ": ").strip()
    except EOFError:
        raise Cancelled("the input ended before the profile was confirmed") from None
    if answer.lower() in QUIT_WORDS:
        raise Cancelled("cancelled by the user")
    return answer


def _pick(ask: Ask, say: Say, label: str, options: list[tuple[str, str]], default: str) -> str:
    values = [value for value, _ in options]
    for number, (value, text) in enumerate(options, start=1):
        say(f"  {number}) {text}" + ("  (default)" if value == default else ""))
    while True:
        answer = _answer(ask, f"{label} [1-{len(options)}]")
        if not answer:
            return default
        if answer in values:
            return answer
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return values[int(answer) - 1]
        say(f"  Please answer with a number from 1 to {len(options)} (q cancels).")


def _text(ask: Ask, say: Say, prompt: str, default: str, validate: Callable[[str], str]) -> str:
    while True:
        answer = _answer(ask, prompt) or default
        try:
            return validate(answer)
        except ProfileError as exc:
            say(f"  Please answer again: {exc}")


def _columns(
    ask: Ask,
    say: Say,
    question: str,
    names: Sequence[str],
    default: Iterable[str],
    allowed: Sequence[str] | None = None,
    what: str = "",
) -> tuple[str, ...]:
    default = tuple(default)
    allowed = tuple(names) if allowed is None else tuple(allowed)
    hint = f" [{', '.join(str(names.index(name) + 1) for name in default)}]" if default else ""
    while True:
        answer = _answer(ask, question + hint)
        if not answer:
            return default
        try:
            chosen = _selection(answer, names, allowed)
        except ValueError as exc:
            scope = f" Only {what} columns can be chosen here." if what else ""
            say(f"  Please answer again: {exc}.{scope}")
            continue
        return chosen


def _selection(answer: str, names: Sequence[str], allowed: Sequence[str]) -> tuple[str, ...]:
    """Parse ``1,3``, ``2-4``, exact names, ``all`` or ``none`` into column names in file order."""
    if answer.lower() == "all":
        return tuple(allowed)
    if answer.lower() == "none":
        return ()
    if answer in names:  # an exact name, which may itself contain commas or dashes
        tokens = [answer]
    else:
        tokens = [token.strip() for token in answer.split(",") if token.strip()]
    chosen: set[str] = set()
    for token in tokens:
        low, dash, high = token.partition("-")
        if token in names:
            picked = [token]
        elif token.isdigit():
            picked = [_by_number(int(token), names)]
        elif dash and low.strip().isdigit() and high.strip().isdigit():
            first, last = int(low), int(high)
            if first > last:
                raise ValueError(f"the range {token!r} runs backwards")
            picked = [_by_number(number, names) for number in range(first, last + 1)]
        else:
            raise ValueError(f"{token!r} is not a column number, range, or exact column name")
        for name in picked:
            if name not in allowed:
                raise ValueError(f"column {name!r} cannot be chosen for this question")
        chosen.update(picked)
    return tuple(name for name in names if name in chosen)


def _by_number(number: int, names: Sequence[str]) -> str:
    if not 1 <= number <= len(names):
        raise ValueError(f"there is no column {number}; the file has {len(names)} columns")
    return names[number - 1]
