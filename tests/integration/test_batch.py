"""`csv-tidy batch`: many files, one explicit profile, separate results, aggregate exit code."""

import json
import shutil
from pathlib import Path

import pytest
from conftest import EXAMPLES, run_cli, sha256

from csv_tidy import load_profile
from csv_tidy.batch import run_batch, select_inputs
from csv_tidy.errors import CsvTidyError

ID_PROFILE = str(EXAMPLES / "profiles" / "transactions-id.toml")


@pytest.fixture
def data(tmp_path):
    """in/: valid.csv, fixable.csv, unfixable.csv, notes.txt, sub/more.CSV"""
    folder = tmp_path / "in"
    (folder / "sub").mkdir(parents=True)
    for name in ("valid", "fixable", "unfixable"):
        shutil.copy(EXAMPLES / f"transactions_{name}.csv", folder / f"{name}.csv")
    shutil.copy(EXAMPLES / "transactions_valid.csv", folder / "sub" / "more.CSV")
    (folder / "notes.txt").write_text("not a csv", encoding="utf-8")
    return folder


def batch(*args):
    return run_cli("batch", *args)


def as_json(result):
    return json.loads(result.out)


# --------------------------------------------------------------------------- selection


def test_directory_selection_is_documented_sorted_and_not_recursive(data):
    chosen = select_inputs([data])
    assert [item.relative.as_posix() for item in chosen] == [
        "fixable.csv",
        "unfixable.csv",
        "valid.csv",
    ]
    deep = select_inputs([data], recursive=True)
    assert [item.relative.as_posix() for item in deep] == [
        "fixable.csv",
        "sub/more.CSV",
        "unfixable.csv",
        "valid.csv",
    ]
    only = select_inputs([data], pattern="*fix*.csv")
    assert [item.relative.name for item in only] == ["fixable.csv", "unfixable.csv"]


def test_explicit_files_are_taken_as_given_in_order(data):
    chosen = select_inputs([data / "notes.txt", data / "valid.csv"])
    assert [item.relative.name for item in chosen] == ["notes.txt", "valid.csv"]


def test_empty_and_repeated_selections_are_refused(data, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(CsvTidyError, match="no files matching"):
        select_inputs([empty])
    with pytest.raises(CsvTidyError, match="selected more than once"):
        select_inputs([data, data / "valid.csv"])
    result = batch("check", str(empty), "--schema", ID_PROFILE)
    assert result.code == 2 and "no files matching" in result.err


# --------------------------------------------------------------------------- check


def test_batch_check_reports_each_file_and_totals(data):
    result = batch("check", str(data), "--schema", ID_PROFILE, "--format", "json")
    report = as_json(result)
    assert result.code == 1 and report["summary"]["exit_code"] == 1
    assert report["command"] == "batch" and report["action"] == "check"
    assert [(f["path"], f["status"], f["exit_code"], f["errors"]) for f in report["files"]] == [
        (str(data / "fixable.csv"), "invalid", 1, 2),
        (str(data / "unfixable.csv"), "invalid", 1, 3),
        (str(data / "valid.csv"), "valid", 0, 0),
    ]
    assert report["totals"] == {
        "files": 3,
        "ok": 1,
        "data_errors": 2,
        "failed": 0,
        "data_records": 12,
        "errors": 5,
        "warnings": 0,
        "changed_fields": 0,
        "removed_records": 0,
        "written": 0,
    }


def test_aggregate_exit_code_prefers_operational_failures(data, write):
    valid = str(data / "valid.csv")
    assert batch("check", valid, "--schema", ID_PROFILE).code == 0
    assert batch("check", valid, str(data / "fixable.csv"), "--schema", ID_PROFILE).code == 1
    broken = write("in/broken.csv", b"transaction_id;customer_id;amount;date;note\n1;\xff\n")
    result = batch("check", str(data / "fixable.csv"), str(broken), valid, "--schema", ID_PROFILE)
    assert result.code == 2
    assert "INCOMPLETE" in result.out and "INVALID" in result.out and "OK" in result.out
    missing = batch(
        "check", str(data / "none.csv"), valid, "--schema", ID_PROFILE, "--format", "json"
    )
    report = as_json(missing)
    assert missing.code == 2
    assert report["files"][0]["status"] == "failed"
    assert "input file not found" in report["files"][0]["error"]
    assert report["files"][1]["status"] == "valid"  # the other file was still checked
    assert report["totals"]["failed"] == 1 and report["totals"]["ok"] == 1


def test_batch_check_says_when_only_structure_was_checked(data):
    result = batch("check", str(data), "--delimiter", ";")
    assert result.code == 0
    assert "structure only" in result.out and "profile init" in result.out


def test_configuration_errors_stop_the_batch_before_reading(data, write):
    bad = write("bad.toml", "schema_version = 1\n[source]\ndelimter = ';'\n")
    result = batch("check", str(data), "--schema", str(bad))
    assert result.code == 2 and "did you mean 'delimiter'" in result.err and result.out == ""


# --------------------------------------------------------------------------- clean


def test_batch_clean_is_a_preview_by_default(data, tmp_path):
    before = sorted(p.name for p in tmp_path.rglob("*"))
    result = batch("clean", str(data), "--schema", ID_PROFILE)
    assert result.code == 1  # unfixable.csv stays blocked
    assert "dry run, nothing written" in result.out
    assert "READY" in result.out and "BLOCKED" in result.out
    assert sorted(p.name for p in tmp_path.rglob("*")) == before
    need = batch("clean", str(data), "--schema", ID_PROFILE, "--output-dir", str(tmp_path / "o"))
    assert need.code == 2 and "require --apply" in need.err
    need = batch("clean", str(data), "--schema", ID_PROFILE, "--apply")
    assert need.code == 2 and "--apply requires --output-dir" in need.err


def test_apply_writes_separate_deterministic_outputs_and_skips_blocked_files(data, tmp_path):
    digests = {p: sha256(p) for p in data.rglob("*") if p.is_file()}
    out, reports = tmp_path / "out", tmp_path / "reports"
    result = batch(
        "clean",
        str(data),
        "--recursive",
        "--schema",
        ID_PROFILE,
        "--apply",
        "--output-dir",
        str(out),
        "--output-schemas",
        "--report-dir",
        str(reports),
        "--format",
        "json",
    )
    report = as_json(result)
    assert result.code == 1
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == [
        "fixable.clean.csv",
        "fixable.output.toml",
        "sub/more.clean.csv",
        "sub/more.output.toml",
        "valid.clean.csv",
        "valid.output.toml",
    ]
    by_name = {f["path"]: f for f in report["files"]}
    blocked = by_name[str(data / "unfixable.csv")]
    assert blocked["status"] == "blocked" and blocked["output_errors"] == 3
    assert [a["status"] for a in blocked["artifacts"]] == ["not_written", "not_written", "written"]
    fixable = by_name[str(data / "fixable.csv")]
    assert fixable["status"] == "ready" and fixable["changed_fields"] == 9
    assert report["totals"]["written"] == 3 and report["totals"]["data_errors"] == 1

    single = tmp_path / "single.csv"
    one = run_cli(
        "clean",
        str(data / "fixable.csv"),
        "--schema",
        ID_PROFILE,
        "--apply",
        "--output",
        str(single),
    )
    assert one.code == 0 and (out / "fixable.clean.csv").read_bytes() == single.read_bytes()
    recheck = run_cli(
        "check", str(out / "fixable.clean.csv"), "--schema", str(out / "fixable.output.toml")
    )
    assert recheck.code == 0
    per_file = json.loads((reports / "unfixable.report.json").read_text(encoding="utf-8"))
    assert per_file["command"] == "clean" and per_file["summary"]["status"] == "blocked"
    assert (reports / "sub" / "more.report.json").exists()
    assert digests == {p: sha256(p) for p in data.rglob("*") if p.is_file()}


def test_overrides_apply_to_every_file(data):
    report = as_json(
        batch("clean", str(data), "--schema", ID_PROFILE, "--no-trim", "--format", "json")
    )
    by_name = {f["path"]: f for f in report["files"]}
    assert by_name[str(data / "fixable.csv")]["status"] == "blocked"


def test_output_name_collisions_stop_the_batch_before_writing(tmp_path):
    for folder in ("a", "b"):
        (tmp_path / folder).mkdir()
        shutil.copy(EXAMPLES / "transactions_valid.csv", tmp_path / folder / "data.csv")
    out = tmp_path / "out"
    args = ["--schema", ID_PROFILE, "--apply", "--output-dir", str(out)]
    result = batch(
        "clean", str(tmp_path / "a" / "data.csv"), str(tmp_path / "b" / "data.csv"), *args
    )
    assert result.code == 2 and "would both be written to" in result.err
    assert not out.exists()


def test_existing_outputs_and_inputs_are_protected(data, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "valid.clean.csv").write_text("keep me", encoding="utf-8")
    args = ["clean", str(data), "--schema", ID_PROFILE, "--apply", "--output-dir", str(out)]
    refused = batch(*args)
    assert refused.code == 2 and "already exists" in refused.err
    assert [p.name for p in out.iterdir()] == ["valid.clean.csv"]  # nothing else was written
    assert (out / "valid.clean.csv").read_text(encoding="utf-8") == "keep me"
    assert batch(*args, "--overwrite").code == 1
    assert (out / "valid.clean.csv").read_bytes().startswith(b"transaction_id;")

    shutil.copy(EXAMPLES / "transactions_valid.csv", data / "fixable.clean.csv")
    digest = sha256(data / "fixable.clean.csv")
    onto_input = batch(
        "clean",
        str(data),
        "--schema",
        ID_PROFILE,
        "--apply",
        "--output-dir",
        str(data),
        "--overwrite",
    )
    assert onto_input.code == 2 and "refusing to overwrite" in onto_input.err
    assert sha256(data / "fixable.clean.csv") == digest


def test_one_failed_write_does_not_undo_the_other_files(data, tmp_path, monkeypatch):
    import csv_tidy.output as output

    real = output.write_atomic

    def flaky(path, payload, overwrite):
        if path.name == "fixable.clean.csv":
            raise OSError(28, "No space left on device")
        return real(path, payload, overwrite)

    monkeypatch.setattr(output, "write_atomic", flaky)
    out = tmp_path / "out"
    result = batch(
        "clean",
        str(data / "valid.csv"),
        str(data / "fixable.csv"),
        str(data / "sub" / "more.CSV"),
        "--schema",
        ID_PROFILE,
        "--apply",
        "--output-dir",
        str(out),
        "--format",
        "json",
    )
    report = as_json(result)
    assert result.code == 2
    assert [f["status"] for f in report["files"]] == ["ready", "failed", "ready"]
    assert "No space left" in report["files"][1]["error"]
    assert sorted(p.name for p in out.iterdir()) == ["more.clean.csv", "valid.clean.csv"]


def test_batch_report_file_and_text_summary(data, tmp_path):
    saved = tmp_path / "summary.txt"
    result = batch("clean", str(data), "--schema", ID_PROFILE, "--report", str(saved))
    lines = result.out.splitlines()
    assert lines[1].startswith("Verdict: 1 of 3 files needs attention")
    assert any(
        line.startswith("Totals: 3 files: 2 ready, 1 with data errors, 0 failed") for line in lines
    )
    assert lines[-1] == "Status: exit code 1"
    assert saved.read_text(encoding="utf-8") == result.out


def test_library_entry_point_matches_the_command(data):
    result = run_batch("clean", select_inputs([data]), load_profile(ID_PROFILE))
    assert result.exit_code == 1
    assert [(f.relative.name, f.status) for f in result.files] == [
        ("fixable.csv", "ready"),
        ("unfixable.csv", "blocked"),
        ("valid.csv", "ready"),
    ]


def test_labels_name_files_in_outcomes_and_reports(data, tmp_path):
    from csv_tidy.batch import BatchInput

    inputs = [
        BatchInput(data / "fixable.csv", Path("fixable.csv"), label="January.csv"),
        BatchInput(data / "missing.csv", Path("missing.csv"), label="February.csv"),
    ]
    reports = tmp_path / "reports"
    result = run_batch("clean", inputs, load_profile(ID_PROFILE), report_dir=reports)
    assert [(f.path, f.status) for f in result.files] == [
        ("January.csv", "ready"),
        ("February.csv", "failed"),
    ]
    report = json.loads((reports / "fixable.report.json").read_text(encoding="utf-8"))
    assert report["source"]["path"] == "January.csv"
    unlabelled = run_batch("check", [BatchInput(data / "valid.csv", Path("valid.csv"))])
    assert unlabelled.files[0].path == str(data / "valid.csv")


def test_single_file_commands_are_unchanged_and_help_lists_batch(data):
    assert "batch" in run_cli("--help").out
    text = batch("clean", "--help").out
    assert "--output-dir" in text and "--recursive" in text and "*.csv" in text
    single = run_cli("check", str(data / "valid.csv"), "--schema", ID_PROFILE)
    assert single.code == 0 and "batch" not in single.out
