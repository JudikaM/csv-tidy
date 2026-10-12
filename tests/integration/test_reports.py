"""Report clarity: verdict first, validation coverage, unresolved-before-repaired, next steps."""

import json

from conftest import EXAMPLES, run_cli

ID_PROFILE = str(EXAMPLES / "profiles" / "transactions-id.toml")
FIXABLE = str(EXAMPLES / "transactions_fixable.csv")
UNFIXABLE = str(EXAMPLES / "transactions_unfixable.csv")
NO_SCHEMA = ("--delimiter", ";", "--number-format", "id", "--date-format", "DD/MM/YYYY")


def lines(text):
    return text.splitlines()


def test_check_without_column_rules_says_only_structure_was_checked():
    result = run_cli("check", UNFIXABLE, *NO_SCHEMA)
    assert result.code == 0  # unchanged: nothing is guessed, so no value is judged
    out = lines(result.out)
    assert out[1].startswith("Verdict: PASSED (structure only)")
    assert "values were not checked" in out[1]
    assert any(line.startswith("Not checked: values in all 5 columns") for line in out)
    assert "csv-tidy profile init" in result.out and '--delimiter ";"' in result.out
    assert "Status: structure check passed; values were not checked (exit code 0)" in out


def test_check_without_column_rules_reports_coverage_in_json():
    data = json.loads(run_cli("check", UNFIXABLE, *NO_SCHEMA, "--format", "json").out)
    assert data["summary"] == {
        "status": "valid",
        "errors": 0,
        "warnings": 0,
        "fatal": 0,
        "exit_code": 0,
    }
    coverage = data["coverage"]
    assert coverage["scope"] == "structure_only"
    assert coverage["declared_columns"] == [] and coverage["unique_keys"] == []
    assert coverage["undeclared_columns"] == [
        "transaction_id",
        "customer_id",
        "amount",
        "date",
        "note",
    ]
    assert data["verdict"]["state"] == "passed_structure_only"
    assert any("profile init" in step for step in data["next_steps"])


def test_check_with_a_profile_lists_checked_and_unchecked_columns():
    result = run_cli("check", UNFIXABLE, "--schema", ID_PROFILE)
    out = lines(result.out)
    assert result.code == 1
    assert out[1] == "Verdict: FAILED - 3 errors found in the source file."
    checked = next(line for line in out if line.startswith("Checked:"))
    assert "file structure" in checked and "values in 4 of 5 columns" in checked
    assert "amount (decimal, id, required)" in checked
    assert "date (date, DD/MM/YYYY, required)" in checked
    assert "unique key (transaction_id)" in checked
    assert "Not checked: values in 1 column without rules (note)" in out
    data = json.loads(run_cli("check", UNFIXABLE, "--schema", ID_PROFILE, "--format", "json").out)
    assert data["coverage"]["scope"] == "structure_and_values"
    assert data["coverage"]["undeclared_columns"] == ["note"]
    assert data["coverage"]["declared_columns"][2] == {
        "column": "amount",
        "type": "decimal",
        "required": True,
        "format": "id",
    }
    assert data["verdict"]["state"] == "failed"


def test_passing_check_with_rules_states_what_passed():
    valid = str(EXAMPLES / "transactions_valid.csv")
    out = lines(run_cli("check", valid, "--schema", ID_PROFILE).out)
    assert out[1] == "Verdict: PASSED - no errors found by the declared rules."
    assert out[-1] == "Status: source validation passed (exit code 0)"


def test_incomplete_check_puts_the_stop_location_in_the_verdict(write):
    result = run_cli("check", str(write("bad.csv", b"a,b\r1,2\r3,\xff\r")))
    out = lines(result.out)
    assert result.code == 2
    assert out[1].startswith("Verdict: INCOMPLETE - the scan stopped at line 3 (decode_error)")
    assert "Scan: INCOMPLETE (stopped by a fatal error); 1 data record, 2 physical lines" in (
        result.out
    )


def test_clean_preview_separates_repaired_problems_from_remaining_ones():
    result = run_cli("clean", FIXABLE, "--schema", ID_PROFILE)
    out = lines(result.out)
    assert result.code == 0
    assert out[1].startswith("Verdict: READY TO EXPORT")
    assert "2 source problems repaired" in out[1]
    assert "ERROR" not in result.out and "[resolved]" not in result.out
    assert "  FIXED invalid_number (record 2, line 3, column 'amount')" in out
    assert out.index("Still to fix: nothing; the cleaned result has no errors or warnings.") < (
        out.index("Repaired by the selected transformations: 2 (no action needed)")
    )
    assert any("--apply --output" in line for line in out[out.index("Next steps:") :])


def test_blocked_clean_lists_unresolved_problems_first_and_once():
    result = run_cli("clean", UNFIXABLE, "--schema", ID_PROFILE)
    out = lines(result.out)
    assert result.code == 1
    assert out[1] == (
        "Verdict: BLOCKED - 3 errors remain in the cleaned result; nothing can be exported."
    )
    assert result.out.count("ERROR invalid_date (record 1, line 2, column 'date')") == 1
    assert "Still to fix: 3 errors, 0 warnings" in result.out
    assert "FIXED" not in result.out
    assert "Export: blocked by 3 remaining output errors; no CSV is written." in out


def test_clean_json_keeps_the_issue_history_and_adds_coverage():
    data = json.loads(run_cli("clean", FIXABLE, "--schema", ID_PROFILE, "--format", "json").out)
    assert [(i["code"], i["severity"], i["status"]) for i in data["source_issues"]["items"]] == [
        ("invalid_number", "error", "resolved"),
        ("invalid_date", "error", "resolved"),
    ]
    assert data["summary"] == {
        "status": "ready",
        "export_ready": True,
        "output_errors": 0,
        "exit_code": 0,
    }
    assert data["verdict"]["state"] == "ready"
    assert data["coverage"]["scope"] == "structure_and_values"


def test_incomplete_clean_shows_what_was_found_before_the_stop(write):
    result = run_cli("clean", str(write("bad.csv", b"a,b\n1,2\n3,\xff\n")))
    out = lines(result.out)
    assert result.code == 2
    assert out[1].startswith("Verdict: INCOMPLETE - the scan stopped at line 3 (decode_error)")
    assert "  FATAL decode_error (line 3)" in out
    assert "Export: not possible; the scan is incomplete." in out


def test_duplicates_removed_by_deduplication_are_listed_as_removed(write):
    path = write("d.csv", "id,v\n1,a\n1,a\n")
    result = run_cli("clean", str(path), "--deduplicate", "rows")
    assert result.code == 0
    assert "  REMOVED duplicate_record (record 2, line 3)" in lines(result.out)
    assert "WARNING duplicate_record" not in result.out
