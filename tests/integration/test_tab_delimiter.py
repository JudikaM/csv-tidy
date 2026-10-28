"""AC-42: tab-separated files, with the delimiter always declared explicitly."""

import tomllib

from conftest import run_cli

from csv_tidy import check_file, clean_file
from csv_tidy.reader import read_csv
from csv_tidy.schema import profile_from_dict

TSV = 'id\tamount\tnote\n1\t1.250,50\tsays "hi", ok\n2\t 980,00 \tsemi;colon\n'
PROFILE = """
schema_version = 1
[source]
delimiter = "\\t"
number_format = "id"
[output]
number_format = "canonical"
[columns.amount]
type = "decimal"
[transform]
trim = ["amount"]
normalize = ["amount"]
"""


def test_reader_splits_on_tabs(write):
    table = read_csv(write("t.tsv", TSV), "\t", "utf-8", 131072)
    assert table.header == ("id", "amount", "note")
    assert [r.fields for r in table.records] == [
        ("1", "1.250,50", 'says "hi", ok'),
        ("2", " 980,00 ", "semi;colon"),
    ]


def test_profile_with_a_tab_delimiter_checks_and_cleans(write):
    profile = profile_from_dict(tomllib.loads(PROFILE))
    path = write("t.tsv", TSV)
    assert check_file(path, profile).exit_code == 1  # ' 980,00 ' needs trimming
    result = clean_file(path, profile)
    assert result.export_ready
    assert result.csv_text() == (
        'id\tamount\tnote\r\n1\t1250.50\t"says ""hi"", ok"\r\n2\t980.00\tsemi;colon\r\n'
    )


def test_output_profile_keeps_the_tab_delimiter(write):
    result = clean_file(write("t.tsv", TSV), profile_from_dict(tomllib.loads(PROFILE)))
    written = tomllib.loads(result.output_profile_toml())
    assert written["source"]["delimiter"] == "\t"


def test_cli_accepts_tab_for_source_and_output(write, tmp_path):
    path = write("t.tsv", TSV)
    checked = run_cli("check", str(path), "--delimiter", "tab")
    assert checked.code == 0
    assert "delimiter '\\t'" in checked.out
    # A tab character, or backslash-t as typed in shells without an easy way to type a tab.
    assert run_cli("check", str(path), "--delimiter", "\t").code == 0
    assert run_cli("check", str(path), "--delimiter", "\\t").code == 0
    out = tmp_path / "out.csv"
    cleaned = run_cli(
        "clean", str(path), "--delimiter", "tab", "--output-delimiter", ",",
        "--apply", "--output", str(out),
    )  # fmt: skip
    assert cleaned.code == 0
    assert out.read_text(encoding="utf-8").splitlines()[0] == "id,amount,note"
    back = tmp_path / "back.tsv"
    run_cli("clean", str(out), "--output-delimiter", "tab", "--apply", "--output", str(back))
    assert back.read_text(encoding="utf-8").splitlines()[0] == "id\tamount\tnote"


def test_cli_rejects_other_delimiters(write):
    result = run_cli("check", str(write("t.tsv", TSV)), "--delimiter", "|")
    assert result.code == 2 and "tab" in result.err


def test_single_column_header_with_tabs_suggests_the_tab_delimiter(write):
    result = check_file(write("t.tsv", TSV), None)
    hint = next(i for i in result.issues if i.code == "possible_wrong_delimiter")
    assert "'\\t'" in hint.message
    assert "--delimiter tab" in hint.suggestion


def test_next_step_commands_spell_the_tab_delimiter_as_tab(write):
    result = run_cli("check", str(write("t.tsv", "id\tamount\n1\n")), "--delimiter", "tab")
    assert result.code == 1
    assert "--delimiter tab" in result.out
    assert "--delimiter \t" not in result.out and '--delimiter "\t"' not in result.out


def test_profile_init_writes_a_tab_delimiter(write, tmp_path):
    out = tmp_path / "p.toml"
    result = run_cli(
        "profile", "init", str(write("t.tsv", TSV)), "--output", str(out), "--delimiter", "tab"
    )
    assert result.code == 0
    profile = tomllib.loads(out.read_text(encoding="utf-8"))
    assert profile["source"]["delimiter"] == "\t"
    assert set(profile["columns"]) == {"id", "amount", "note"}
