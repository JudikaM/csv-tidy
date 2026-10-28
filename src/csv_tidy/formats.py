"""Number grammars and numeric calendar date formats.

Numbers are parsed from text into exact digit strings and converted to ``Decimal`` only
from those strings; floats are never used. Dates use an explicit token grammar instead of
``strptime`` so that parsing never depends on the machine locale.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal

NUMBER_FORMATS = ("id", "us", "canonical")
NUMBER_EXAMPLES = {"id": "1.250,50", "us": "1,250.50", "canonical": "1250.50"}
_GROUP_SEP = {"id": ".", "us": ","}
_DECIMAL_SEP = {"id": ",", "us": ".", "canonical": "."}


def _number_pattern(fmt: str) -> re.Pattern[str]:
    if fmt == "canonical":
        integer = r"\d+"
    else:
        group = re.escape(_GROUP_SEP[fmt])
        integer = rf"[1-9]\d{{0,2}}(?:{group}\d{{3}})+|\d+"
    decimal = re.escape(_DECIMAL_SEP[fmt])
    return re.compile(rf"(?P<sign>[+-])?(?P<int>{integer})(?:{decimal}(?P<frac>\d+))?", re.ASCII)


_NUMBER_PATTERNS = {fmt: _number_pattern(fmt) for fmt in NUMBER_FORMATS}
_NONFINITE = re.compile(r"[+-]?(?:nan|inf|infinity)", re.IGNORECASE)
_EXPONENT = re.compile(r"[+-]?[\d.,]*\d[eE][+-]?\d+")


@dataclass(frozen=True)
class ParsedNumber:
    """An exactly parsed decimal number: sign, integer digits and fraction digits."""

    negative: bool
    integer: str
    fraction: str

    def to_decimal(self) -> Decimal:
        sign = "-" if self.negative else ""
        return Decimal(
            f"{sign}{self.integer}.{self.fraction}" if self.fraction else f"{sign}{self.integer}"
        )


def parse_number(text: str, fmt: str) -> ParsedNumber | None:
    """Parse ``text`` with grammar ``fmt``; return ``None`` when it does not match exactly."""
    match = _NUMBER_PATTERNS[fmt].fullmatch(text)
    if match is None:
        return None
    digits = (
        match["int"].replace(_GROUP_SEP.get(fmt, ""), "") if fmt != "canonical" else match["int"]
    )
    integer = digits.lstrip("0") or "0"
    return ParsedNumber(match["sign"] == "-", integer, match["frac"] or "")


def format_number(number: ParsedNumber, fmt: str) -> str:
    """Render ``number`` in grammar ``fmt``. Fraction digits (scale) are preserved exactly."""
    integer = number.integer
    if fmt in _GROUP_SEP and len(integer) > 3:
        head = len(integer) % 3 or 3
        groups = [integer[:head]] + [integer[i : i + 3] for i in range(head, len(integer), 3)]
        integer = _GROUP_SEP[fmt].join(groups)
    text = integer + (_DECIMAL_SEP[fmt] + number.fraction if number.fraction else "")
    return ("-" if number.negative else "") + text


def explain_invalid_number(text: str, fmt: str) -> str:
    """Return an English explanation of why ``text`` is not a valid ``fmt`` number."""
    if text != text.strip():
        return "the value has leading or trailing whitespace"
    if _NONFINITE.fullmatch(text):
        return "non-finite values such as NaN or Infinity are not accepted"
    if _EXPONENT.fullmatch(text):
        return "scientific notation is not supported"
    if re.search(r"[^\d.,+\-]", text, re.ASCII):
        return (
            "the value contains characters that are not part of a number "
            "(currency symbols are not supported)"
        )
    for other in NUMBER_FORMATS:
        if other != fmt and parse_number(text, other) is not None:
            return (
                f"it does not match the '{fmt}' number format (example {NUMBER_EXAMPLES[fmt]}) "
                f"but would match '{other}'"
            )
    return f"it does not match the '{fmt}' number format (example {NUMBER_EXAMPLES[fmt]})"


_DATE_TOKENS = (
    ("YYYY", "year", r"\d{4}"),
    ("MM", "month", r"\d{2}"),
    ("DD", "day", r"\d{2}"),
    ("M", "month", r"\d{1,2}"),
    ("D", "day", r"\d{1,2}"),
)
_DATE_SEPARATORS = "-/."


@dataclass(frozen=True)
class DateFormat:
    """A compiled numeric calendar date format such as ``DD/MM/YYYY``."""

    text: str
    parts: tuple[str, ...]
    pattern: re.Pattern[str]

    def parse(self, value: str) -> dt.date | None:
        match = self.pattern.fullmatch(value)
        if match is None:
            return None
        try:
            return dt.date(int(match["year"]), int(match["month"]), int(match["day"]))
        except ValueError:
            return None

    def matches_shape(self, value: str) -> bool:
        return self.pattern.fullmatch(value) is not None

    def format(self, value: dt.date) -> str:
        rendered = {
            "YYYY": f"{value.year:04d}",
            "MM": f"{value.month:02d}",
            "M": str(value.month),
            "DD": f"{value.day:02d}",
            "D": str(value.day),
        }
        return "".join(rendered.get(part, part) for part in self.parts)


def compile_date_format(text: str) -> DateFormat:
    """Compile a date format or raise ``ValueError`` with an English explanation.

    Tokens are separated by one separator each, or by none at all (``YYYYMMDD``). A format
    without separators may only use fixed-width tokens, because ``M`` and ``D`` would make
    values such as ``2026111`` ambiguous.
    """
    parts: list[str] = []
    regex = ""
    seen: set[str] = set()
    separated = adjacent = False
    i = 0
    expect_token = True
    while i < len(text):
        if not expect_token and any(text.startswith(t, i) for t, _, _ in _DATE_TOKENS):
            adjacent = True  # no separator between the previous token and this one
            expect_token = True
        if expect_token:
            for token, field, digits in _DATE_TOKENS:
                if text.startswith(token, i):
                    if field in seen:
                        raise ValueError(
                            f"date format '{text}' contains more than one {field} token"
                        )
                    seen.add(field)
                    parts.append(token)
                    regex += f"(?P<{field}>{digits})"
                    i += len(token)
                    break
            else:
                raise ValueError(
                    f"date format '{text}' has an unsupported directive at position {i + 1}; "
                    "use YYYY, MM, M, DD or D (uppercase)"
                )
        else:
            if text[i] not in _DATE_SEPARATORS:
                raise ValueError(
                    f"date format '{text}' needs one separator ('-', '/' or '.') between tokens, "
                    "or none at all (for example YYYYMMDD)"
                )
            separated = True
            parts.append(text[i])
            regex += re.escape(text[i])
            i += 1
        expect_token = not expect_token
    if expect_token or seen != {"year", "month", "day"}:
        raise ValueError(f"date format '{text}' must contain exactly one year, month and day token")
    if adjacent and separated:
        raise ValueError(
            f"date format '{text}' must use one separator ('-', '/' or '.') between every two "
            "tokens, or none at all (for example YYYYMMDD)"
        )
    if adjacent and not set(parts) <= {"YYYY", "MM", "DD"}:
        raise ValueError(
            f"date format '{text}' has no separators, so every token needs a fixed width "
            "(YYYY, MM, DD); with M or D a value such as 2026111 would be ambiguous"
        )
    return DateFormat(text, tuple(parts), re.compile(regex, re.ASCII))


def explain_invalid_date(value: str, fmt: DateFormat) -> str:
    """Return an English explanation of why ``value`` is not a valid date in ``fmt``."""
    if value != value.strip():
        return "the value has leading or trailing whitespace"
    if fmt.matches_shape(value):
        return f"it matches {fmt.text} but is not a valid calendar date"
    return f"it does not match the date format {fmt.text}"
