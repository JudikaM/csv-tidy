"""AC-51: the contract changes of 1.0.0 (docs/STABILITY.md, "Changes made in 1.0.0").

New option and keyword names, the deprecated aliases that keep old commands and calls
working, report schema_version 2 (identifier artifact kinds, ``dry_run``, top-level
``artifacts`` in clean reports, ``output_field_too_large``), and the new exports.
"""

import inspect
import json
import warnings

import pytest
from conftest import EXAMPLES, run_cli

import csv_tidy
from csv_tidy import batch, clean_file, export_clean, run_batch, select_inputs

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


@pytest.mark.parametrize(
    ("old", "new", "extra"),
    [
        ("--schema", "--profile", ()),
        ("--output-schema", "--output-profile", ("--apply", "--output", "{dir}/out.csv")),
    ],
)
def test_old_clean_options_still_work_and_warn(tmp_path, old, new, extra):
    value = str(PROFILE) if old == "--schema" else str(tmp_path / "out.toml")
    profile = () if old == "--schema" else ("--profile", str(PROFILE))
    args = [a.format(dir=tmp_path) for a in extra]
    result = run_cli("clean", str(FIXABLE), *profile, *CLEAN_ARGS, old, value, *args)
    assert result.code == 0, result.err
    assert f"warning: {old} is deprecated and will be removed in CSV Tidy 2.0.0; use {new}" in (
        result.err
    )
    if old == "--output-schema":
        assert (tmp_path / "out.toml").is_file()


def test_old_batch_option_still_works_and_warns(tmp_path):
    result = run_cli(
        "batch", "clean", str(FIXABLE), "--schema", str(PROFILE), *CLEAN_ARGS,
        "--apply", "--output-dir", str(tmp_path), "--output-schemas",
    )  # fmt: skip
    assert result.code == 0, result.out
    assert "use --profile" in result.err and "use --output-profiles" in result.err
    assert (tmp_path / "transactions_fixable.output.toml").is_file()


def test_an_old_and_a_new_name_together_are_refused():
    result = run_cli("check", str(FIXABLE), "--schema", str(PROFILE), "--profile", str(PROFILE))
    assert result.code == 2 and "--schema is the old name of --profile" in result.err


def test_python_keywords_have_new_names_and_deprecated_aliases(tmp_path):
    assert "output_profile" in inspect.signature(export_clean).parameters
    assert "output_profiles" in inspect.signature(run_batch).parameters
    result = clean_file(FIXABLE, PROFILE, overrides=csv_tidy.Overrides(trim=("amount", "date")))
    assert result.ok
    with pytest.warns(DeprecationWarning, match=r"use export_clean\(output_profile=\.\.\.\)"):
        export_clean(result, tmp_path / "a.csv", output_schema=tmp_path / "a.toml")
    assert (tmp_path / "a.toml").is_file()
    with pytest.raises(TypeError, match="both 'output_profile' and its deprecated alias"):
        export_clean(result, tmp_path / "b.csv", output_profile="x.toml", output_schema="y.toml")
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # the new name warns about nothing
        export_clean(result, tmp_path / "c.csv", output_profile=tmp_path / "c.toml")
    inputs = select_inputs([FIXABLE])
    with pytest.warns(DeprecationWarning, match=r"run_batch\(output_schemas=\.\.\.\)"):
        run_batch("clean", inputs, PROFILE, output_schemas=False)
    with pytest.raises(TypeError, match="output_profiles"):
        run_batch("clean", inputs, PROFILE, output_profiles=False, output_schemas=False)


def test_reports_use_schema_version_2_identifiers(tmp_path):
    out = tmp_path / "out.csv"
    result = run_cli(
        "clean", str(FIXABLE), "--profile", str(PROFILE), *CLEAN_ARGS, "--apply",
        "--output", str(out), "--output-profile", str(tmp_path / "out.toml"), "--format", "json",
    )  # fmt: skip
    report = json.loads(result.out)
    assert report["schema_version"] == 2 and report["mode"] == "apply"
    assert [a["kind"] for a in report["artifacts"]] == ["output_csv", "output_profile"]
    assert report["artifacts"] == report["export"]["artifacts"]
    dry = json.loads(run_cli("clean", str(FIXABLE), "--format", "json").out)
    assert dry["mode"] == "dry_run" and dry["artifacts"] == []
    summary = run_cli(
        "batch", "clean", str(FIXABLE), "--profile", str(PROFILE), *CLEAN_ARGS, "--format",
        "json", "--report", str(tmp_path / "batch.json"),
    )  # fmt: skip
    data = json.loads(summary.out)
    assert data["schema_version"] == 2 and data["mode"] == "dry_run"
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
        assert name in csv_tidy.__all__ and isinstance(getattr(csv_tidy, name), type)
    settings = clean_file(FIXABLE, PROFILE).settings
    assert isinstance(settings.source, csv_tidy.SourceSettings)
    assert isinstance(settings.output, csv_tidy.OutputSettings)
    assert isinstance(select_inputs([FIXABLE])[0], csv_tidy.BatchInput)
    outcome = run_batch("check", select_inputs([FIXABLE]), PROFILE).files[0]
    assert isinstance(outcome, csv_tidy.FileOutcome)
