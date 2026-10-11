"""AC-03, AC-04, AC-06, AC-07, AC-08: structural and value validation."""

import tomllib

from csv_tidy import check_file
from csv_tidy.schema import profile_from_dict


def prof(text):
    return profile_from_dict(tomllib.loads("schema_version = 1\n" + text))


def codes(result):
    return [(i.code, i.record, i.column) for i in result.issues]


def test_empty_file_is_an_error_and_header_only_is_a_warning(write):
    empty = check_file(write("e.csv", ""))
    assert codes(empty) == [("empty_file", None, None)] and empty.exit_code == 1
    header_only = check_file(write("h.csv", "a,b\n"))
    assert codes(header_only) == [("no_records", None, None)] and header_only.exit_code == 0


def test_blank_lines_are_warnings_with_line_numbers(write):
    result = check_file(write("b.csv", "a\n1\n\n2\n"))
    assert [(i.code, i.line_start, i.severity) for i in result.issues] == [
        ("blank_line", 3, "warning")
    ]
    assert result.exit_code == 0


def test_header_problems(write):
    result = check_file(write("h.csv", "id,,id, name \n1,2,3,4\n"))
    found = {(i.code, i.column) for i in result.issues}
    assert ("empty_header", "") in found
    assert ("duplicate_header", "id") in found
    assert ("header_whitespace", " name ") in found
    assert result.exit_code == 1


def test_missing_profile_column(write):
    result = check_file(write("m.csv", "id\n1\n"), prof("[columns.amount]\ntype='decimal'"))
    assert ("missing_column", None, "amount") in codes(result)


def test_possible_wrong_delimiter_hint(write):
    result = check_file(write("d.csv", "a;b;c\n1;2;3\n"))
    assert [i.code for i in result.issues] == ["possible_wrong_delimiter"]


def test_inconsistent_columns(write):
    result = check_file(write("w.csv", "a,b\n1\n1,2,3\n1,2\n"))
    assert codes(result) == [("inconsistent_columns", 1, None), ("inconsistent_columns", 2, None)]


def test_required_whitespace_and_zero(write):
    profile = prof("[columns.qty]\ntype='decimal'\nrequired=true\n[columns.note]\nrequired=true")
    result = check_file(write("r.csv", "qty,note\n0,ok\n   ,x\n,y\n5, \n"), profile)
    assert codes(result) == [
        ("missing_required", 2, "qty"),
        ("missing_required", 3, "qty"),
        ("missing_required", 4, "note"),
    ]


def test_optional_empty_values_are_not_errors(write):
    profile = prof("[columns.amount]\ntype='decimal'\n[columns.day]\ntype='date'")
    assert check_file(write("o.csv", "amount,day\n,\n"), profile).issues == ()


def test_identifiers_keep_leading_zeros(write):
    path = write("i.csv", "customer_id,phone_number\n00123,081234567890\n")
    result = check_file(
        path, prof("[columns.customer_id]\nrequired=true\n[columns.phone_number]\n")
    )
    assert result.issues == ()


def test_duplicate_rows_warn_and_keys_error(write):
    profile = prof("[duplicates]\nkeys=[['id'], ['a','b']]")
    text = "id,a,b\n1,x,y\n1,x,y\n2,x,z\n3,x,y\n"
    result = check_file(write("d.csv", text), profile)
    found = [(i.code, i.severity, i.record, i.related_record) for i in result.issues]
    assert ("duplicate_record", "warning", 2, 1) in found
    assert ("duplicate_key", "error", 2, 1) in found  # id
    assert ("duplicate_key", "error", 4, 1) in found  # (a, b)
    assert ("duplicate_key", "error", 3, 1) not in found


def test_empty_key_values_never_form_an_identity(write):
    profile = prof("[duplicates]\nkeys=[['id'], ['a','b']]")
    result = check_file(write("k.csv", "id,a,b,n\n,x,,1\n,x,,2\n , ,y,3\n"), profile)
    assert [i.code for i in result.issues] == []


def test_duplicate_row_warnings_can_be_ignored(write):
    profile = prof("[duplicates]\nrows='ignore'")
    assert check_file(write("i.csv", "a\n1\n1\n"), profile).issues == ()


def test_invalid_number_and_date_messages(write):
    profile = prof(
        "[source]\nnumber_format='id'\ndate_format='DD/MM/YYYY'\n"
        "[columns.amount]\ntype='decimal'\n[columns.day]\ntype='date'"
    )
    result = check_file(
        write("v.csv", "amount,day\n1.25,31/02/2026\n1.250,50,01/02/2026\n"), profile
    )
    by_code = {i.code: i for i in result.issues}
    assert set(by_code) == {"invalid_number", "invalid_date", "inconsistent_columns"}
    assert "not a valid calendar date" in by_code["invalid_date"].message
    assert by_code["invalid_number"].value == "1.25"


def test_issue_order_is_deterministic(write):
    path = write("o.csv", "a,b\n1,2\n1\n,\n1,2\n")
    profile = prof("[columns.a]\nrequired=true\n[duplicates]\nkeys=[['a']]")
    first = check_file(path, profile).issues
    assert first == check_file(path, profile).issues
    assert [i.record for i in first] == sorted(i.record for i in first)
