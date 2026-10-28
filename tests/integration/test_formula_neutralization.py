"""AC-44: opt-in neutralization of spreadsheet formulas in selected text columns."""

import json
import tomllib

import pytest
from conftest import run_cli

from csv_tidy import Overrides, ProfileError, clean_file, load_profile, run_batch, select_inputs
from csv_tidy.reporting import clean_report, render_clean_text
from csv_tidy.schema import profile_from_dict, profile_to_toml

# Values that start with a formula trigger (OWASP: = + - @ tab CR), and values that do not.
CSV = (
    "id,amount,note\n"
    "1,10,=SUM(A1:A9)\n"
    "2,-5,+1\n"
    "3,7,-1\n"
    "4,8,@cmd\n"
    '5,9,"\tx"\n'
    '6,1,"\rx"\n'
    "7,2,plain\n"
    "8,3,\n"
    "9,4,'=already\n"
    "10,5, =spaced\n"
)
NEUTRALIZED = ["'=SUM(A1:A9)", "'+1", "'-1", "'@cmd", "'\tx", "'\rx", "plain", "", "'=already"]


def profile(transform="", columns='[columns.amount]\ntype = "decimal"\n'):
    text = f"schema_version = 1\n{columns}[transform]\n{transform}\n"
    return profile_from_dict(tomllib.loads(text))


def notes(result):
    return [row[2] for row in result.rows]


def test_selected_text_column_is_neutralized(write):
    result = clean_file(write("f.csv", CSV), profile('neutralize_formulas = ["note"]'))
    assert notes(result)[:9] == NEUTRALIZED
    assert notes(result)[9] == " =spaced"  # starts with a space: left as it is
    changed = {c.record: c for c in result.changes}
    assert sorted(changed) == [1, 2, 3, 4, 5, 6]
    assert changed[1].before == "=SUM(A1:A9)" and changed[1].after == "'=SUM(A1:A9)"
    assert all(c.steps == ("neutralize_formulas",) for c in result.changes)
    assert [row[1] for row in result.rows][1] == "-5"  # the decimal column is never touched
    assert result.export_ready


def test_nothing_is_neutralized_unless_selected(write):
    result = clean_file(write("f.csv", CSV), profile())
    assert notes(result)[0] == "=SUM(A1:A9)" and result.changes == ()


def test_trimming_first_exposes_a_formula_to_neutralization(write):
    selected = 'trim = ["note"]\nneutralize_formulas = ["note"]'
    result = clean_file(write("f.csv", CSV), profile(selected))
    assert notes(result)[9] == "'=spaced"
    assert next(c for c in result.changes if c.record == 10).steps == (
        "trim",
        "neutralize_formulas",
    )


@pytest.mark.parametrize("kind", ["decimal", "date"])
def test_number_and_date_columns_cannot_be_neutralized(kind):
    columns = f'[columns.amount]\ntype = "{kind}"\n'
    with pytest.raises(ProfileError, match="text columns"):
        profile('neutralize_formulas = ["amount"]', columns=columns)


def test_a_column_missing_from_the_file_is_reported(write):
    result = clean_file(write("f.csv", CSV), profile('neutralize_formulas = ["nope"]'))
    assert any(i.code == "missing_column" and i.column == "nope" for i in result.source_issues)


def test_output_profile_keeps_the_selection_and_a_second_clean_changes_nothing(write, tmp_path):
    first = clean_file(write("f.csv", CSV), profile('neutralize_formulas = ["note"]'))
    saved = tmp_path / "out.toml"
    saved.write_text(first.output_profile_toml(), encoding="utf-8")
    assert load_profile(saved).neutralize_formulas == ("note",)
    cleaned = tmp_path / "out.csv"
    cleaned.write_text(first.csv_text(), encoding="utf-8", newline="")
    second = clean_file(cleaned, load_profile(saved))
    assert second.changes == () and second.export_ready


def test_unused_selection_is_not_written_to_profiles(write):
    result = clean_file(write("f.csv", CSV), profile())
    assert "neutralize_formulas" not in result.output_profile_toml()
    assert "neutralize_formulas" not in profile_to_toml(profile())


def test_reports_list_the_transformation_only_when_selected(write):
    used = clean_file(write("f.csv", CSV), profile('neutralize_formulas = ["note"]'))
    report = clean_report(used, "dry-run", 10, 10)
    transformations = report["transformations"]
    assert transformations["order"] == ["trim", "normalize", "neutralize_formulas", "deduplicate"]
    assert transformations["neutralize_formulas"] == ["note"]
    text = render_clean_text(report)
    assert "3. neutralize formulas: note" in text and "4. deduplicate: off" in text
    assert "[neutralize formulas]" in text

    unused = clean_report(clean_file(write("g.csv", CSV), profile()), "dry-run", 10, 10)
    assert unused["transformations"]["order"] == ["trim", "normalize", "deduplicate"]
    assert unused["transformations"]["neutralize_formulas"] == []
    assert "neutralize" not in render_clean_text(unused)


def test_cli_options_select_and_clear_the_columns(write, tmp_path):
    source = write("f.csv", CSV)
    out = tmp_path / "out.csv"
    result = run_cli(
        "clean", str(source), "--neutralize-formulas", "note", "--apply", "--output", str(out)
    )
    assert result.code == 0, result.err
    assert "'=SUM(A1:A9)" in out.read_text(encoding="utf-8")

    schema = write("p.toml", 'schema_version = 1\n[transform]\nneutralize_formulas = ["note"]\n')
    cleared = run_cli(
        "clean", str(source), "--schema", str(schema), "--no-neutralize-formulas", "--format",
        "json",
    )  # fmt: skip
    assert json.loads(cleared.out)["transformations"]["neutralize_formulas"] == []

    both = run_cli(
        "clean", str(source), "--neutralize-formulas", "note", "--no-neutralize-formulas"
    )
    assert both.code == 2 and "cannot be combined" in both.err


def test_batch_applies_the_selection_to_every_file(write, tmp_path):
    write("in/a.csv", CSV)
    write("in/b.csv", CSV)
    result = run_batch(
        "clean",
        select_inputs([tmp_path / "in"]),
        None,
        overrides=Overrides(neutralize_formulas=("note",)),
        apply=True,
        output_dir=tmp_path / "out",
    )
    assert result.exit_code == 0
    for name in ("a", "b"):
        text = (tmp_path / "out" / f"{name}.clean.csv").read_text(encoding="utf-8")
        assert "'=SUM(A1:A9)" in text
