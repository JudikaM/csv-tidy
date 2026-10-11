"""AC-09, AC-10, AC-11: number grammars and date formats."""

import datetime as dt
from decimal import Decimal

import pytest

from csv_tidy.formats import (
    compile_date_format,
    explain_invalid_number,
    format_number,
    parse_number,
)


@pytest.mark.parametrize(
    ("text", "fmt", "expected"),
    [
        ("1.250,50", "id", "1250.50"),
        ("1,250.50", "us", "1250.50"),
        ("1250.50", "canonical", "1250.50"),
        ("1.250", "id", "1250"),  # id grouping: one thousand two hundred fifty
        ("1.250", "canonical", "1.250"),  # canonical: one point two five zero
        ("1.250", "us", "1.250"),
        ("1.234.567,891", "id", "1234567.891"),
        ("-75,25", "id", "-75.25"),
        ("+3", "us", "3"),
        ("0,00", "id", "0.00"),
        ("007.50", "canonical", "7.50"),
    ],
)
def test_parse_and_normalize_to_canonical(text, fmt, expected):
    parsed = parse_number(text, fmt)
    assert parsed is not None
    assert format_number(parsed, "canonical") == expected


def test_scale_and_precision_are_preserved_exactly():
    parsed = parse_number("12345678901234567890,123456789", "id")
    assert format_number(parsed, "canonical") == "12345678901234567890.123456789"
    assert parsed.to_decimal() == Decimal("12345678901234567890.123456789")
    assert format_number(parse_number("980,00", "id"), "canonical") == "980.00"


@pytest.mark.parametrize(
    ("number", "fmt", "expected"),
    [("1234567.5", "id", "1.234.567,5"), ("1234567.5", "us", "1,234,567.5"), ("999", "id", "999")],
)
def test_format_with_grouping(number, fmt, expected):
    assert format_number(parse_number(number, "canonical"), fmt) == expected


@pytest.mark.parametrize(
    ("text", "fmt"),
    [
        ("1.25", "id"),  # group must have three digits
        ("12,50", "us"),
        ("1,250.50", "id"),  # mixed / other grammar
        ("1.250,50", "us"),
        ("1,250.50", "canonical"),  # canonical has no grouping
        ("0.250", "id"),  # grouped numbers cannot start with zero
        (" 12", "canonical"),
        ("12 ", "canonical"),
        ("NaN", "canonical"),
        ("Infinity", "canonical"),
        ("-inf", "us"),
        ("1e5", "canonical"),
        ("1.5E-3", "us"),
        ("Rp 1.000", "id"),
        ("$12.00", "us"),
        ("(12)", "us"),
        ("12-", "us"),
        ("--1", "us"),
        ("1.", "canonical"),
        (".5", "canonical"),
        ("", "canonical"),
        ("١٢", "canonical"),  # non-ASCII digits are rejected
    ],
)
def test_invalid_numbers_are_rejected(text, fmt):
    assert parse_number(text, fmt) is None


@pytest.mark.parametrize(
    ("text", "fmt", "fragment"),
    [
        (" 1", "canonical", "whitespace"),
        ("NaN", "canonical", "non-finite"),
        ("1e5", "canonical", "scientific notation"),
        ("$1", "us", "currency"),
        ("1,250.50", "id", "would match 'us'"),
    ],
)
def test_invalid_number_explanations(text, fmt, fragment):
    assert fragment in explain_invalid_number(text, fmt)


@pytest.mark.parametrize(
    ("fmt", "text", "expected"),
    [
        ("DD/MM/YYYY", "01/02/2026", dt.date(2026, 2, 1)),
        ("MM/DD/YYYY", "01/02/2026", dt.date(2026, 1, 2)),
        ("YYYY-MM-DD", "2026-02-01", dt.date(2026, 2, 1)),
        ("D.M.YYYY", "1.2.2026", dt.date(2026, 2, 1)),
        ("DD/MM/YYYY", "29/02/2024", dt.date(2024, 2, 29)),
    ],
)
def test_dates_follow_the_configured_format(fmt, text, expected):
    assert compile_date_format(fmt).parse(text) == expected


@pytest.mark.parametrize(
    ("fmt", "text"),
    [
        ("DD/MM/YYYY", "31/02/2026"),
        ("DD/MM/YYYY", "29/02/2025"),  # not a leap year
        ("DD/MM/YYYY", "00/01/2026"),
        ("DD/MM/YYYY", "1/2/2026"),  # DD requires two digits
        ("DD/MM/YYYY", "2026-02-01"),  # no guessing between formats
        ("YYYY-MM-DD", "2026-13-01"),
        ("YYYY-MM-DD", "0000-01-01"),
        ("YYYY-MM-DD", "2026-02-01 "),
        ("YYYY-MM-DD", "2026-02-01T00:00"),
        ("DD/MM/YYYY", "01-02-2026"),
    ],
)
def test_invalid_dates_are_rejected(fmt, text):
    assert compile_date_format(fmt).parse(text) is None


def test_date_formatting_and_padding():
    assert compile_date_format("YYYY-MM-DD").format(dt.date(2026, 2, 1)) == "2026-02-01"
    assert compile_date_format("D/M/YYYY").format(dt.date(2026, 2, 1)) == "1/2/2026"


@pytest.mark.parametrize(
    "fmt",
    [
        "yyyy-mm-dd",
        "YYYY-MM",
        "YYYY-MM-DD-DD",
        "YYYYMMDD",
        "%Y-%m-%d",
        "DD MMM YYYY",
        "YYYY-MM-",
        "",
        "YYYY_MM_DD",
    ],
)
def test_invalid_date_directives_are_rejected(fmt):
    with pytest.raises(ValueError):
        compile_date_format(fmt)
