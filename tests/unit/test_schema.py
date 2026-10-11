"""AC-15, AC-16, AC-22: profile validation, precedence, and output profiles."""

import tomllib

import pytest

from csv_tidy import Overrides, ProfileError, load_profile
from csv_tidy.schema import output_profile, profile_from_dict, profile_to_toml, resolve_settings

BASE = """
schema_version = 1
[source]
delimiter = ";"
number_format = "id"
date_format = "DD/MM/YYYY"
[columns.amount]
type = "decimal"
[columns.date]
type = "date"
[transform]
trim = ["amount"]
normalize = ["amount"]
"""


def profile(text=BASE):
    return profile_from_dict(tomllib.loads(text))


def test_defaults_without_profile():
    s = resolve_settings()
    assert (
        s.source.delimiter,
        s.source.encoding,
        s.source.number_format,
        s.source.date_format,
    ) == (",", "utf-8", "canonical", "YYYY-MM-DD")
    assert (s.output.delimiter, s.output.line_ending) == (",", "crlf")
    assert (
        s.trim == () and s.normalize == () and s.deduplicate == "off" and s.duplicate_rows == "warn"
    )


def test_profile_values_and_output_follow_resolved_source():
    s = resolve_settings(profile())
    assert s.source.delimiter == ";" and s.output.delimiter == ";"
    assert s.output.number_format == "id"  # follows source when not set


def test_cli_overrides_win_and_output_follows_the_override():
    s = resolve_settings(profile(), Overrides(delimiter=",", number_format="us"))
    assert s.source.delimiter == "," and s.output.delimiter == ","
    assert s.source.number_format == "us" and s.output.number_format == "us"


def test_unspecified_overrides_do_not_replace_profile_values():
    s = resolve_settings(profile(), Overrides())
    assert (
        s.source.date_format == "DD/MM/YYYY"
        and s.trim == ("amount",)
        and s.normalize == ("amount",)
    )


def test_list_overrides_replace_rather_than_merge():
    s = resolve_settings(profile(), Overrides(trim=("date",), normalize=("date",)))
    assert s.trim == ("date",) and s.normalize == ("date",)
    cleared = resolve_settings(profile(), Overrides(trim=(), normalize=()))
    assert cleared.trim == () and cleared.normalize == ()


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("schema_version = 2", "unsupported schema_version"),
        ("[source]\ndelimiter=';'", "missing required key 'schema_version'"),
        ("schema_version = '1'", "unsupported schema_version"),
        ("schema_version = 1\nextra = 1", "unknown key 'extra'"),
        ("schema_version = 1\n[source]\ndelimter = ';'", "did you mean 'delimiter'"),
        ("schema_version = 1\n[source]\ndelimiter = '|'", "invalid value '|'"),
        ("schema_version = 1\n[source]\nencoding = 'nope-8'", "unknown encoding"),
        ("schema_version = 1\n[source]\nnumber_format = 'de'", "invalid value 'de'"),
        ("schema_version = 1\n[source]\ndate_format = '%d/%m/%Y'", "unsupported directive"),
        ("schema_version = 1\n[source]\nmax_field_chars = 0", "max_field_chars"),
        ("schema_version = 1\n[columns.a]\ntype = 'int'", "invalid value 'int'"),
        ("schema_version = 1\n[columns.a]\nrequired = 'yes'", "true or false"),
        ("schema_version = 1\n[columns.a]\nnumber_format = 'id'", "only valid for decimal"),
        (
            "schema_version = 1\n[columns.a]\ntype='decimal'\ndate_format = 'YYYY-MM-DD'",
            "only valid for date",
        ),
        ("schema_version = 1\n[columns.a]\ntyp = 'text'", "did you mean 'type'"),
        ("schema_version = 1\n[duplicates]\nkeys = ['id']", "non-empty list"),
        ("schema_version = 1\n[duplicates]\nkeys = [['id'], ['id']]", "duplicate key definitions"),
        ("schema_version = 1\n[duplicates]\nkeys = [['id', 'id']]", "must not repeat"),
        ("schema_version = 1\n[duplicates]\nrows = 'error'", "invalid value 'error'"),
        (
            "schema_version = 1\n[transform]\nnormalize = ['amount']",
            "cannot normalize column 'amount'",
        ),
        (
            "schema_version = 1\n[columns.a]\n[transform]\nnormalize = ['a']",
            "cannot normalize column 'a'",
        ),
        ("schema_version = 1\n[transform]\ndeduplicate = 'keys'", "requires at least one key"),
        ("schema_version = 1\n[transform]\ntrim = 'a'", "list of column names"),
        ("schema_version = 1\n[output]\nline_ending = 'cr'", "invalid value 'cr'"),
    ],
)
def test_invalid_profiles_are_rejected(text, fragment):
    with pytest.raises(ProfileError) as excinfo:
        profile(text)
    assert fragment in str(excinfo.value)


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        (Overrides(date_format="dd/mm/yyyy"), "--date-format"),
        (Overrides(output_encoding="bogus"), "--output-encoding"),
        (Overrides(normalize=("missing",)), "cannot normalize column 'missing'"),
        (Overrides(deduplicate="keys"), "requires at least one key"),
    ],
)
def test_invalid_overrides_are_rejected(overrides, fragment):
    with pytest.raises(ProfileError) as excinfo:
        resolve_settings(profile(), overrides)
    assert fragment in str(excinfo.value)


def test_load_profile_errors(tmp_path):
    with pytest.raises(ProfileError, match="not found"):
        load_profile(tmp_path / "missing.toml")
    bad = tmp_path / "bad.toml"
    bad.write_text("schema_version = ", encoding="utf-8")
    with pytest.raises(ProfileError, match="not valid TOML"):
        load_profile(bad)


def test_output_profile_uses_resolved_overrides_and_round_trips():
    settings = resolve_settings(
        profile(),
        Overrides(
            output_delimiter=",",
            output_number_format="us",
            output_date_format="YYYY-MM-DD",
            line_ending="lf",
            normalize=("amount", "date"),
        ),
    )
    out = output_profile(settings)
    assert (out.source_delimiter, out.source_number_format, out.source_date_format) == (
        ",",
        "us",
        "YYYY-MM-DD",
    )
    assert out.line_ending == "lf"
    columns = {c.name: c for c in out.columns}
    assert columns["amount"].number_format == "us" and columns["date"].date_format == "YYYY-MM-DD"
    text = profile_to_toml(out, "comment line")
    assert text.startswith("# comment line\n")
    assert profile_from_dict(tomllib.loads(text)) == out


def test_output_profile_keeps_source_format_for_columns_not_normalized():
    settings = resolve_settings(profile(), Overrides(output_number_format="canonical"))
    columns = {c.name: c for c in output_profile(settings).columns}
    assert columns["amount"].number_format == "canonical"  # normalized
    assert columns["date"].date_format == "DD/MM/YYYY"  # untouched, still source format


def test_unusual_column_names_round_trip():
    text = 'schema_version = 1\n[columns."amount \\"net\\" = ok"]\ntype = "decimal"\n'
    out = output_profile(resolve_settings(profile(text)))
    assert profile_from_dict(tomllib.loads(profile_to_toml(out))) == out
