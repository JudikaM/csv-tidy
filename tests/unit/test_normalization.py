"""AC-09, AC-12, AC-13: transformations, their order, and resolved/introduced issues."""

import tomllib

from csv_tidy import Overrides, clean_file
from csv_tidy.schema import profile_from_dict

PROFILE = """
schema_version = 1
[source]
number_format = "id"
date_format = "DD/MM/YYYY"
delimiter = ";"
[output]
number_format = "canonical"
date_format = "YYYY-MM-DD"
[columns.id]
required = true
[columns.amount]
type = "decimal"
[columns.day]
type = "date"
[duplicates]
keys = [["id"]]
"""


def prof(extra=""):
    return profile_from_dict(tomllib.loads(PROFILE + extra))


def test_nothing_changes_without_selected_transformations(write):
    path = write("n.csv", "id;amount;day;note\n 1 ;1.250,50;01/02/2026; keep  this \n")
    result = clean_file(path, prof())
    assert result.changes == ()
    assert result.rows == ((" 1 ", "1.250,50", "01/02/2026", " keep  this "),)


def test_trim_only_selected_columns_and_keep_internal_whitespace(write):
    path = write("t.csv", "id;amount;day;note\n a  b ;1,5; 01/02/2026 ; x \n")
    result = clean_file(path, prof('[transform]\ntrim = ["id", "day"]'))
    assert result.rows == (("a  b", "1,5", "01/02/2026", " x "),)
    assert {(c.column, c.steps) for c in result.changes} == {("id", ("trim",)), ("day", ("trim",))}


def test_normalize_converts_valid_values_and_leaves_invalid_ones(write):
    path = write("v.csv", "id;amount;day;note\n1;1.250,50;29/02/2024;\n2;abc;31/02/2026;\n3;;;\n")
    result = clean_file(path, prof('[transform]\nnormalize = ["amount", "day"]'))
    assert result.rows == (
        ("1", "1250.50", "2024-02-29", ""),
        ("2", "abc", "31/02/2026", ""),
        ("3", "", "", ""),
    )
    assert {(i.code, i.record) for i in result.output_issues} == {
        ("invalid_number", 2),
        ("invalid_date", 2),
    }
    assert all(i.status == "unresolved" for i in result.source_issues)
    assert "could not be normalized" in result.output_issues[0].message
    assert not result.export_ready and result.exit_code == 1


def test_whitespace_is_not_silently_fixed_by_normalize(write):
    path = write("w.csv", "id;amount;day;note\n1; 7,5 ;01/02/2026;\n")
    without_trim = clean_file(path, prof('[transform]\nnormalize = ["amount"]'))
    assert without_trim.rows[0][1] == " 7,5 " and without_trim.exit_code == 1
    with_trim = clean_file(path, prof('[transform]\ntrim=["amount"]\nnormalize = ["amount"]'))
    assert with_trim.rows[0][1] == "7.5" and with_trim.exit_code == 0
    assert with_trim.source_issues[0].status == "resolved"
    assert with_trim.changes[0].steps == ("trim", "normalize")


def test_transformations_can_introduce_duplicate_keys(write):
    path = write("d.csv", "id;amount;day;note\nA1;1;01/02/2026;first\n A1;2;01/02/2026;second\n")
    result = clean_file(path, prof('[transform]\ntrim = ["id"]'))
    assert result.source_issues == ()
    dup = [i for i in result.output_issues if i.code == "duplicate_key"]
    assert len(dup) == 1 and dup[0].introduced is True and dup[0].related_record == 1
    assert not result.export_ready


def test_normalization_can_make_rows_identical(write):
    path = write("n.csv", "id;amount;day;note\n1;1.000;01/02/2026;x\n1;1000;01/02/2026;x\n")
    profile = prof('[transform]\nnormalize = ["amount"]\ndeduplicate = "rows"')
    result = clean_file(path, profile)
    assert [(r.record, r.reason, r.kept_record) for r in result.removed] == [
        (2, "duplicate_record", 1)
    ]
    assert len(result.rows) == 1


def test_deduplicate_keys_keeps_first_and_marks_source_issue_removed(write):
    path = write(
        "k.csv",
        "id;amount;day;note\n1;1;01/02/2026;first\n2;1;01/02/2026;x\n1;9;01/02/2026;later\n",
    )
    result = clean_file(path, prof('[transform]\ndeduplicate = "keys"'))
    assert [r[3] for r in result.rows] == ["first", "x"]
    assert [(r.record, r.reason, r.key) for r in result.removed] == [(3, "duplicate_key", ("id",))]
    assert [i.status for i in result.source_issues] == ["removed"]
    assert result.export_ready


def test_records_with_wrong_field_count_are_never_transformed_or_removed(write):
    path = write("b.csv", "id;amount;day;note\n 1 ;1,0\n")
    result = clean_file(path, prof('[transform]\ntrim=["id"]\ndeduplicate="rows"'))
    assert result.rows == ((" 1 ", "1,0"),)
    assert result.output_errors == 1 and result.output_issues[0].code == "inconsistent_columns"


def test_cli_style_overrides_change_output_format(write):
    path = write("o.csv", "id;amount;day;note\n1;1.234,5;01/02/2026;\n")
    result = clean_file(
        path,
        prof(),
        overrides=Overrides(
            normalize=("amount", "day"), output_number_format="us", output_date_format="MM/DD/YYYY"
        ),
    )
    assert result.rows[0][1:3] == ("1,234.5", "02/01/2026")
