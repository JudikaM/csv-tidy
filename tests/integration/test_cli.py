"""AC-14, AC-15, AC-18, AC-19, AC-21, AC-25: CLI contract, reports, exit codes, API parity."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import EXAMPLES, run_cli

from csv_tidy import __version__, check_file, clean_file, load_profile

ID_PROFILE = str(EXAMPLES / "profiles" / "transactions-id.toml")
FIXABLE = str(EXAMPLES / "transactions_fixable.csv")


def test_version_and_help():
    with pytest.raises(SystemExit) as excinfo:
        from csv_tidy.cli import main

        main(["--version"])
    assert excinfo.value.code == 0
    help_text = run_cli("--help").out
    assert "examples:" in help_text and "exit codes" in help_text
    clean_help = run_cli("clean", "--help").out
    assert "--apply" in clean_help and "trim, normalize" in clean_help


def test_python_dash_m_runs_the_cli():
    proc = subprocess.run(
        [sys.executable, "-m", "csv_tidy", "--version"], capture_output=True, text=True
    )
    assert proc.returncode == 0 and proc.stdout.strip() == f"csv-tidy {__version__}"


def test_dry_run_and_apply_are_exclusive(tmp_path):
    result = run_cli(
        "clean",
        FIXABLE,
        "--schema",
        ID_PROFILE,
        "--dry-run",
        "--apply",
        "--output",
        str(tmp_path / "x.csv"),
    )
    assert result.code == 2 and "not allowed with argument" in result.err
    assert not (tmp_path / "x.csv").exists()


def test_apply_requires_output_and_output_requires_apply(tmp_path):
    assert run_cli("clean", FIXABLE, "--schema", ID_PROFILE, "--apply").code == 2
    result = run_cli("clean", FIXABLE, "--schema", ID_PROFILE, "--output", str(tmp_path / "x.csv"))
    assert result.code == 2 and "require --apply" in result.err
    assert not (tmp_path / "x.csv").exists()


def test_dry_run_may_save_a_report_but_no_csv_or_profile(tmp_path):
    report = tmp_path / "r.json"
    result = run_cli(
        "clean", FIXABLE, "--schema", ID_PROFILE, "--format", "json", "--report", str(report)
    )
    assert result.code == 0
    assert [p.name for p in tmp_path.iterdir()] == ["r.json"]
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["mode"] == "dry-run"
    assert data["export"]["artifacts"] == [
        {"kind": "report", "path": str(report), "status": "written", "error": None}
    ]


def test_configuration_errors_exit_2_without_traceback(tmp_path, write):
    bad = write("bad.toml", "schema_version = 1\n[source]\ndelimter = ';'\n")
    result = run_cli("check", FIXABLE, "--schema", str(bad))
    assert result.code == 2
    assert "did you mean 'delimiter'" in result.err and "Traceback" not in result.err
    missing = run_cli("check", str(tmp_path / "nope.csv"))
    assert missing.code == 2 and "input file not found" in missing.err
    bad_option = run_cli("check", FIXABLE, "--date-format", "dd/mm/yyyy")
    assert bad_option.code == 2 and "--date-format" in bad_option.err


def test_cli_options_override_profile(write):
    path = write("c.csv", 'transaction_id,customer_id,amount,date\nT1,C1,"1,250.50",02/01/2026\n')
    via_profile = run_cli("check", str(path), "--schema", ID_PROFILE)
    assert via_profile.code == 1  # profile says ';' and id numbers
    overridden = run_cli(
        "check",
        str(path),
        "--schema",
        ID_PROFILE,
        "--delimiter",
        ",",
        "--number-format",
        "us",
        "--date-format",
        "MM/DD/YYYY",
    )
    assert overridden.code == 0, overridden.out


def test_report_collisions_and_input_protection(tmp_path, write):
    source = write("in.csv", "a\n1\n")
    same = run_cli(
        "clean",
        str(source),
        "--apply",
        "--output",
        str(tmp_path / "o.csv"),
        "--report",
        str(tmp_path / "o.csv"),
    )
    assert same.code == 2 and "same file" in same.err
    into_input = run_cli("check", str(source), "--report", str(source))
    assert into_input.code == 2 and "refers to the input CSV" in into_input.err
    assert source.read_text(encoding="utf-8") == "a\n1\n"
    schema = write("p.toml", "schema_version = 1\n")
    over_profile = run_cli(
        "clean",
        str(source),
        "--schema",
        str(schema),
        "--apply",
        "--output",
        str(tmp_path / "x.csv"),
        "--output-schema",
        str(schema),
        "--overwrite",
    )
    assert over_profile.code == 2 and "input profile" in over_profile.err
    assert schema.read_text(encoding="utf-8") == "schema_version = 1\n"


def test_existing_outputs_and_overwrite(tmp_path, write):
    source = write("in.csv", "a\n1\n")
    out = write("out.csv", "keep me")
    refused = run_cli("clean", str(source), "--apply", "--output", str(out))
    assert refused.code == 2 and "already exists" in refused.err
    assert out.read_text(encoding="utf-8") == "keep me"
    allowed = run_cli("clean", str(source), "--apply", "--output", str(out), "--overwrite")
    assert allowed.code == 0 and out.read_bytes() == b"a\r\n1\r\n"


def test_json_report_contract_and_truncation(write):
    rows = "\n".join(f"{i}," for i in range(1, 8))
    path = write("t.csv", "id,v\n" + rows + "\n")
    profile = write("p.toml", "schema_version = 1\n[columns.v]\nrequired = true\n")
    result = run_cli(
        "check", str(path), "--schema", str(profile), "--format", "json", "--max-details", "3"
    )
    data = json.loads(result.out)
    assert result.code == 1
    assert data["schema_version"] == 1 and data["command"] == "check"
    assert data["summary"] == {
        "status": "invalid",
        "errors": 7,
        "warnings": 0,
        "fatal": 0,
        "exit_code": 1,
    }
    assert data["details"] == {"limit": 3, "total": 7, "shown": 3, "truncated": True}
    assert data["scan"]["complete"] is True and data["scan"]["data_records"] == 7
    issue = data["issues"][0]
    assert {
        "code",
        "severity",
        "record",
        "line_start",
        "column",
        "value",
        "message",
        "suggestion",
    } <= issue.keys()
    assert result.err == ""


def test_incomplete_scan_is_reported_with_exit_2(write):
    path = write("bad.csv", b"a,b\n1,2\n3,\xff\n")
    result = run_cli("check", str(path), "--format", "json")
    data = json.loads(result.out)
    assert result.code == 2
    assert data["summary"]["status"] == "incomplete" and data["scan"]["complete"] is False
    assert data["scan"]["fatal_error"]["code"] == "decode_error"
    clean = run_cli("clean", str(path))
    assert clean.code == 2 and "scan is incomplete" in clean.out


def test_warnings_alone_exit_0(write):
    result = run_cli("check", str(write("w.csv", "a\n1\n1\n")))
    assert result.code == 0 and "duplicate_record" in result.out


def test_cli_and_api_agree(examples):
    profile = load_profile(examples / "profiles" / "transactions-id.toml")
    for name in ("transactions_fixable.csv", "transactions_unfixable.csv"):
        path = str(examples / name)
        api_check = check_file(path, profile)
        cli_check = json.loads(
            run_cli(
                "check",
                path,
                "--schema",
                str(examples / "profiles" / "transactions-id.toml"),
                "--format",
                "json",
            ).out
        )
        assert cli_check["summary"]["errors"] == api_check.errors
        assert [i["code"] for i in cli_check["issues"]] == [i.code for i in api_check.issues]
        api_clean = clean_file(path, profile)
        cli_clean = json.loads(
            run_cli(
                "clean",
                path,
                "--schema",
                str(examples / "profiles" / "transactions-id.toml"),
                "--format",
                "json",
            ).out
        )
        assert cli_clean["summary"]["exit_code"] == api_clean.exit_code
        assert cli_clean["changes"]["changed_fields"] == len(api_clean.changes)


def test_api_example_runs():
    proc = subprocess.run(
        [sys.executable, str(Path(EXAMPLES / "api_example.py"))], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    assert "check: 2 errors, 0 warnings, exit code 1" in proc.stdout
    assert "clean: export ready = True, 9 fields changed" in proc.stdout
    assert "TX-002;00456;980.00;2026-02-15;Paid in  two parts" in proc.stdout


def test_list_options_replace_or_disable_profile_lists():
    base = ["clean", FIXABLE, "--schema", ID_PROFILE, "--format", "json"]
    default = json.loads(run_cli(*base).out)["transformations"]
    assert default["trim"] == ["customer_id", "amount", "date"]
    replaced = json.loads(run_cli(*base, "--trim", "date").out)["transformations"]
    assert replaced["trim"] == ["date"]
    disabled = run_cli(*base, "--no-trim", "--no-normalize")
    data = json.loads(disabled.out)
    assert data["transformations"]["trim"] == [] and data["transformations"]["normalize"] == []
    assert data["changes"]["changed_fields"] == 0 and disabled.code == 1
    conflict = run_cli(*base, "--trim", "date", "--no-trim")
    assert conflict.code == 2 and "cannot be combined" in conflict.err
