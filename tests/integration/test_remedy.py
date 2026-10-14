"""Issues name the kind of repair they need (``remedy``) so interfaces can explain it in their
own terms. The English messages and suggestions of the CLI are unchanged."""

import json

from conftest import EXAMPLES, run_cli

from csv_tidy import check_file, clean_file, load_profile

ID_PROFILE = EXAMPLES / "profiles" / "transactions-id.toml"


def remedies(issues):
    return [(i.code, i.remedy) for i in issues]


def test_value_problems_name_their_repair():
    check = check_file(EXAMPLES / "transactions_fixable.csv", load_profile(ID_PROFILE))
    assert remedies(check.issues) == [("invalid_number", "trim"), ("invalid_date", "trim")]
    unfixable = check_file(EXAMPLES / "transactions_unfixable.csv", load_profile(ID_PROFILE))
    assert remedies(unfixable.issues) == [
        ("invalid_date", None),  # 31/02/2026: only the source can be corrected
        ("missing_required", None),
        ("invalid_number", "number_format"),
    ]


def test_dates_in_another_format_point_to_the_date_format(write):
    path = write("d.csv", "when\n2026-01-31\n")
    profile = write(
        "p.toml", 'schema_version = 1\n[columns.when]\ntype = "date"\ndate_format = "DD/MM/YYYY"\n'
    )
    assert remedies(check_file(path, profile).issues) == [("invalid_date", "date_format")]


def test_output_stage_keeps_the_trim_remedy(write):
    path = write("t.csv", "v\n 5\n")
    profile = write("p.toml", 'schema_version = 1\n[columns.v]\ntype = "decimal"\n')
    result = clean_file(path, profile)
    assert remedies(result.output_issues) == [("invalid_number", "trim")]


def test_duplicates_delimiter_and_fatal_problems(write):
    rows = check_file(write("r.csv", "a\n1\n1\n"))
    assert remedies(rows.issues) == [("duplicate_record", "deduplicate_rows")]
    keys = check_file(
        write("k.csv", "id\n1\n1\n"),
        write("k.toml", 'schema_version = 1\n[duplicates]\nkeys = [["id"]]\n'),
    )
    assert ("duplicate_key", "deduplicate_keys") in remedies(keys.issues)
    wrong = check_file(write("w.csv", "a;b\n1;2\n"))
    assert remedies(wrong.issues) == [("possible_wrong_delimiter", "delimiter")]
    decode = check_file(write("x.csv", b"a\n\xff\n"))
    assert remedies(decode.issues)[-1] == ("decode_error", "encoding")
    quoting = check_file(write("q.csv", 'a,b\n1,"bad"x\n'))
    assert remedies(quoting.issues)[-1] == ("malformed_csv", "quoting")
    big = check_file(
        write("b.csv", "a\n" + "x" * 20 + "\n"),
        write("m.toml", "schema_version = 1\n[source]\nmax_field_chars = 5\n"),
    )
    assert remedies(big.issues)[-1] == ("field_too_large", "max_field_chars")


def test_json_reports_add_remedy_and_text_reports_are_unchanged():
    args = ["check", str(EXAMPLES / "transactions_fixable.csv"), "--schema", str(ID_PROFILE)]
    data = json.loads(run_cli(*args, "--format", "json").out)
    assert [i["remedy"] for i in data["issues"]] == ["trim", "trim"]
    text = run_cli(*args).out
    assert "remedy" not in text
    assert (
        "Suggestion: Select trimming for 'amount' (transform trim) or fix the source value." in text
    )
