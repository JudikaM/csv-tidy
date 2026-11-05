"""AC-51: the contract changes of 1.0.0 (docs/STABILITY.md, "Changes made in 1.0.0").

New option and keyword names, the identifiers that report schema_version 2 introduced and
later versions keep (artifact kinds, ``dry_run``, top-level ``artifacts`` in clean reports,
``output_field_too_large``), and the new exports. The deprecated aliases were removed in
2.0.0 (see test_contract_2_0.py).
"""

import inspect
import json

from conftest import EXAMPLES, run_cli

import datakrit
from datakrit import batch, clean_file, export_clean, run_batch, select_inputs

PROFILE = EXAMPLES / "profiles" / "transactions-id.toml"
FIXABLE = EXAMPLES / "transactions_fixable.csv"
CLEAN_ARGS = ("--trim", "amount", "--trim", "date")


def test_new_option_names_work_and_the_old_ones_are_hidden():
    result = run_cli("check", str(FIXABLE), "--profile", str(PROFILE), "--format", "json")
    assert result.err == "" and json.loads(result.out)["source"]["profile"] == str(PROFILE)
    clean_help = run_cli("clean", "--help").out
    batch_help = run_cli("batch", "clean", "--help").out
    assert "--profile PROFILE" in clean_help and "--output-profile PATH" in clean_help
    assert "--output-profiles" in batch_help
    for text in (clean_help, batch_help):
        assert "--schema" not in text and "--output-schema" not in text


def test_python_keywords_have_the_new_names():
    assert "output_profile" in inspect.signature(export_clean).parameters
    assert "output_profiles" in inspect.signature(run_batch).parameters


def test_reports_use_the_identifiers_of_schema_version_2(tmp_path):
    out = tmp_path / "out.csv"
    result = run_cli(
        "clean", str(FIXABLE), "--profile", str(PROFILE), *CLEAN_ARGS, "--apply",
        "--output", str(out), "--output-profile", str(tmp_path / "out.toml"), "--format", "json",
    )  # fmt: skip
    report = json.loads(result.out)
    assert report["schema_version"] == 3 and report["mode"] == "apply"
    assert [a["kind"] for a in report["artifacts"]] == ["output_csv", "output_profile"]
    assert report["artifacts"] == report["export"]["artifacts"]
    dry = json.loads(run_cli("clean", str(FIXABLE), "--format", "json").out)
    assert dry["mode"] == "dry_run" and dry["artifacts"] == []
    summary = run_cli(
        "batch", "clean", str(FIXABLE), "--profile", str(PROFILE), *CLEAN_ARGS, "--format",
        "json", "--report", str(tmp_path / "batch.json"),
    )  # fmt: skip
    data = json.loads(summary.out)
    assert data["schema_version"] == 3 and data["mode"] == "dry_run"
    assert [a["kind"] for a in data["artifacts"]] == ["report"]
    assert batch.run_batch("clean", select_inputs([FIXABLE]), PROFILE).mode == "dry_run"


def test_text_reports_name_artifacts_in_words(tmp_path):
    result = run_cli(
        "clean", str(FIXABLE), "--profile", str(PROFILE), *CLEAN_ARGS, "--apply",
        "--output", str(tmp_path / "out.csv"),
    )  # fmt: skip
    assert f"  output CSV: {tmp_path / 'out.csv'} - written" in result.out


def test_clean_results_count_like_check_results():
    fixed = clean_file(FIXABLE, PROFILE)
    assert fixed.ok and fixed.exit_code == 0 and fixed.source_errors > 0
    blocked = clean_file(EXAMPLES / "transactions_unfixable.csv", PROFILE)
    assert not blocked.ok and blocked.exit_code == 1
    for result in (fixed, blocked):
        assert result.source_errors == sum(i.severity == "error" for i in result.source_issues)
        source_warnings = sum(i.severity == "warning" for i in result.source_issues)
        assert result.source_warnings == source_warnings
        output_warnings = sum(i.severity == "warning" for i in result.output_issues)
        assert result.output_warnings == output_warnings


def test_returned_and_contained_types_are_exported():
    for name in ("FatalError", "SourceSettings", "OutputSettings", "BatchInput", "FileOutcome"):
        assert name in datakrit.__all__ and isinstance(getattr(datakrit, name), type)
    settings = clean_file(FIXABLE, PROFILE).settings
    assert isinstance(settings.source, datakrit.SourceSettings)
    assert isinstance(settings.output, datakrit.OutputSettings)
    assert isinstance(select_inputs([FIXABLE])[0], datakrit.BatchInput)
    outcome = run_batch("check", select_inputs([FIXABLE]), PROFILE).files[0]
    assert isinstance(outcome, datakrit.FileOutcome)
