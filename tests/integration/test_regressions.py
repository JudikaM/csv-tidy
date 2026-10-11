"""Regression tests for defects found in the 2026-10-11 audit of commit e1e4a63.

R1 failed normalization marked resolved, R2 export after a working-directory change,
R3 output fields longer than max_field_chars, R4 no-clobber race, R5 non-text codecs,
R6 unvalidated direct Profile objects, R7 report-write failures hidden in reports.
"""

import json
import os
import tomllib

import pytest
from conftest import run_cli, sha256

from csv_tidy import (
    ColumnSpec,
    OutputError,
    Overrides,
    Profile,
    ProfileError,
    check_file,
    clean_file,
    export_clean,
)
from csv_tidy.output import write_atomic
from csv_tidy.schema import profile_from_dict


def prof(text: str) -> Profile:
    return profile_from_dict(tomllib.loads("schema_version = 1\n" + text))


ID_TO_CANONICAL = """
[source]
number_format = "id"
[output]
number_format = "canonical"
[columns.amount]
type = "decimal"
[duplicates]
keys = [["id"]]
[transform]
normalize = ["amount"]
"""

# --------------------------------------------------------------------- R1


def test_r1_unparsable_number_that_looks_like_output_format_stays_invalid(write):
    path = write("n.csv", "id,amount\n1,1.25\n")
    assert check_file(path, prof(ID_TO_CANONICAL)).exit_code == 1
    result = clean_file(path, prof(ID_TO_CANONICAL))
    assert result.changes == ()
    assert not result.export_ready and result.exit_code == 1
    assert [i.status for i in result.source_issues] == ["unresolved"]
    [issue] = result.output_issues
    assert (issue.code, issue.record, issue.column) == ("invalid_number", 1, "amount")
    assert "could not be normalized" in issue.message and "'id'" in issue.message


def test_r1_unparsable_date_that_looks_like_output_format_stays_invalid(write):
    profile = prof(
        '[source]\ndate_format = "DD/MM/YYYY"\n[output]\ndate_format = "MM/DD/YYYY"\n'
        '[columns.day]\ntype = "date"\n[transform]\nnormalize = ["day"]'
    )
    result = clean_file(write("d.csv", "day\n12/31/2026\n"), profile)
    assert [i.status for i in result.source_issues] == ["unresolved"]
    assert [i.code for i in result.output_issues] == ["invalid_date"]
    assert not result.export_ready


def test_r1_trim_then_parse_is_still_a_real_repair(write):
    profile = prof(
        ID_TO_CANONICAL.replace(
            'normalize = ["amount"]', 'trim = ["amount"]\nnormalize = ["amount"]'
        )
    )
    result = clean_file(write("t.csv", 'id,amount\n1," 1.250,50 "\n'), profile)
    assert result.rows == (("1", "1250.50"),)
    assert [i.status for i in result.source_issues] == ["resolved"]
    assert result.export_ready


def test_r1_valid_values_with_no_textual_change_remain_valid(write):
    profile = prof(
        '[source]\nnumber_format = "canonical"\n[columns.amount]\ntype = "decimal"\n'
        '[transform]\nnormalize = ["amount"]'
    )
    result = clean_file(write("z.csv", "amount\n12.50\n0\n"), profile)
    assert result.changes == () and result.output_issues == () and result.export_ready


def test_r1_invalid_value_in_explicitly_removed_record_is_removed_not_resolved(write):
    profile = prof(ID_TO_CANONICAL + 'deduplicate = "keys"\n')
    result = clean_file(write("r.csv", "id,amount\n1,5\n1,1.25\n"), profile)
    assert [(r.record, r.reason) for r in result.removed] == [(2, "duplicate_key")]
    assert {(i.code, i.status) for i in result.source_issues} == {
        ("invalid_number", "removed"),
        ("duplicate_key", "removed"),
    }
    assert result.export_ready and result.rows == (("1", "5"),)


# --------------------------------------------------------------------- R2


def test_r2_export_after_cwd_change_cannot_overwrite_inputs(tmp_path, monkeypatch):
    a, b = tmp_path / "A", tmp_path / "B"
    a.mkdir()
    b.mkdir()
    (a / "source.csv").write_bytes(b"a\n1\n")
    (a / "p.toml").write_text("schema_version = 1\n", encoding="utf-8")
    before = sha256(a / "source.csv"), sha256(a / "p.toml")
    monkeypatch.chdir(a)
    result = clean_file("source.csv", "p.toml")
    assert result.source_file == (a / "source.csv").resolve()
    monkeypatch.chdir(b)
    for target in (a / "source.csv", a / "p.toml"):
        with pytest.raises(OutputError, match="refers to the input"):
            export_clean(result, target.resolve(), overwrite=True)
    with pytest.raises(OutputError, match="refers to the input profile"):
        export_clean(result, b / "ok.csv", output_schema=a / "p.toml", overwrite=True)
    link = b / "alias.csv"
    os.link(a / "source.csv", link)
    with pytest.raises(OutputError, match="refers to the input CSV"):
        export_clean(result, link, overwrite=True)
    assert (sha256(a / "source.csv"), sha256(a / "p.toml")) == before
    assert not (b / "ok.csv").exists()
    export_clean(result, "separate.csv")
    assert (b / "separate.csv").read_bytes() == b"a\r\n1\r\n"
    assert (sha256(a / "source.csv"), sha256(a / "p.toml")) == before


# --------------------------------------------------------------------- R3


NUMBER_GROWS = """
[source]
max_field_chars = 7
[output]
number_format = "us"
[columns.amount]
type = "decimal"
[transform]
normalize = ["amount"]
"""
DATE_GROWS = """
[source]
max_field_chars = 8
date_format = "D/M/YYYY"
[output]
date_format = "YYYY-MM-DD"
[columns.amount]
type = "date"
[transform]
normalize = ["amount"]
"""


@pytest.mark.parametrize(
    ("data", "settings"),
    [("amount\n1000000\n", NUMBER_GROWS), ("amount\n1/2/2026\n", DATE_GROWS)],
)
def test_r3_expanded_output_beyond_field_limit_blocks_export(write, tmp_path, data, settings):
    path = write("big.csv", data)
    assert check_file(path, prof(settings)).exit_code == 0
    result = clean_file(path, prof(settings))
    assert [i.code for i in result.output_issues] == ["field_too_large"]
    assert not result.export_ready
    schema = write("p.toml", "schema_version = 1\n" + settings)
    out, out_schema = tmp_path / "o.csv", tmp_path / "o.toml"
    cli = run_cli("clean", str(path), "--schema", str(schema), "--apply", "--output", str(out),
                  "--output-schema", str(out_schema))  # fmt: skip
    assert cli.code == 1 and "field_too_large" in cli.out
    assert not out.exists() and not out_schema.exists()


def test_r3_chain_stays_valid_when_the_limit_allows_expansion(write, tmp_path):
    settings = NUMBER_GROWS.replace("max_field_chars = 7", "max_field_chars = 9")
    path, schema = (
        write("ok.csv", "amount\n1000000\n"),
        write("p.toml", "schema_version = 1\n" + settings),
    )
    out, out_schema = tmp_path / "o.csv", tmp_path / "o.toml"
    cli = run_cli("clean", str(path), "--schema", str(schema), "--apply", "--output", str(out),
                  "--output-schema", str(out_schema))  # fmt: skip
    assert cli.code == 0
    assert run_cli("check", str(out), "--schema", str(out_schema)).code == 0
    again = json.loads(
        run_cli("clean", str(out), "--schema", str(out_schema), "--format", "json").out
    )
    assert again["changes"]["changed_fields"] == 0 and again["summary"]["exit_code"] == 0


# --------------------------------------------------------------------- R4


def test_r4_destination_created_during_finalization_is_not_clobbered(tmp_path, monkeypatch):
    target = tmp_path / "out.csv"
    real_fsync = os.fsync

    def competing_writer(fd):
        real_fsync(fd)
        target.write_bytes(b"other writer")

    monkeypatch.setattr(os, "fsync", competing_writer)
    with pytest.raises(OutputError, match="created by another process"):
        write_atomic(target, b"ours", overwrite=False)
    assert target.read_bytes() == b"other writer"
    assert [p.name for p in tmp_path.iterdir()] == ["out.csv"]
    monkeypatch.setattr(os, "fsync", real_fsync)
    write_atomic(target, b"ours", overwrite=True)
    assert target.read_bytes() == b"ours"


# --------------------------------------------------------------------- R5


@pytest.mark.parametrize("codec", ["base64_codec", "hex_codec", "rot_13", "zlib_codec"])
def test_r5_non_text_codecs_are_configuration_errors(write, codec):
    path = write("a.csv", "amount\n1\n")
    with pytest.raises(ProfileError, match="not a text encoding"):
        check_file(path, overrides=Overrides(encoding=codec))
    with pytest.raises(ProfileError, match="not a text encoding"):
        prof(f'[output]\nencoding = "{codec}"')
    cli = run_cli("check", str(path), "--encoding", codec)
    assert cli.code == 2 and "not a text encoding" in cli.err and "Traceback" not in cli.err


def test_r5_text_encodings_still_work(write):
    path = write("w.csv", "name\nJosé\n", encoding="cp1252")
    assert check_file(path, overrides=Overrides(encoding="cp1252")).exit_code == 0
    utf16 = write("u.csv", "a\n1\n", encoding="utf-16")
    assert check_file(utf16, overrides=Overrides(encoding="utf-16")).exit_code == 0


# --------------------------------------------------------------------- R6


@pytest.mark.parametrize(
    ("profile", "fragment"),
    [
        (Profile(source_delimiter="|"), "delimiter"),
        (Profile(output_delimiter="\t"), "delimiter"),
        (Profile(columns=(ColumnSpec("amount", type="unknown"),)), "type"),
        (
            Profile(columns=(ColumnSpec("amount", type="decimal", number_format="bogus"),)),
            "number_format",
        ),
        (
            Profile(columns=(ColumnSpec("amount", type="text", number_format="id"),)),
            "only valid for decimal",
        ),
        (Profile(columns=(ColumnSpec("amount", type="date", date_format="dd/mm"),)), "date_format"),
        (Profile(columns=(ColumnSpec("amount", required="yes"),)), "true or false"),
        (Profile(columns=(ColumnSpec("a"), ColumnSpec("a"))), "more than once"),
        (Profile(source_encoding="nope"), "unknown encoding"),
        (Profile(source_date_format="%Y"), "unsupported directive"),
        (Profile(max_field_chars=0), "max_field_chars"),
        (Profile(line_ending="cr"), "line_ending"),
        (Profile(duplicate_rows="error"), "rows"),
        (Profile(duplicate_keys=(("a", "a"),)), "must not repeat"),
        (Profile(duplicate_keys=("a",)), "keys"),
        (Profile(trim="amount"), "trim"),
        (Profile(deduplicate="all"), "deduplicate"),
        (Profile(deduplicate="keys"), "requires at least one key"),
    ],
)
def test_r6_direct_profile_objects_are_validated(write, profile, fragment):
    path = write("a.csv", "amount,a\n1,2\n")
    with pytest.raises(ProfileError) as excinfo:
        check_file(path, profile)
    assert fragment in str(excinfo.value)
    with pytest.raises(ProfileError):
        clean_file(path, profile)


def test_r6_valid_direct_profile_is_supported(write):
    profile = Profile(
        source_delimiter=";",
        source_number_format="id",
        output_number_format="canonical",
        columns=(ColumnSpec("amount", type="decimal", required=True),),
        normalize=("amount",),
    )
    result = clean_file(write("v.csv", "amount\n1.250,5\n"), profile)
    assert result.rows == (("1250.5",),) and result.export_ready


def test_r6_override_lists_must_be_sequences(write):
    with pytest.raises(ProfileError, match="--trim"):
        check_file(write("a.csv", "a\n1\n"), overrides=Overrides(trim="a"))


# --------------------------------------------------------------------- R7


def test_r7_check_report_write_failure_is_in_json_and_exit_code(write, tmp_path):
    source = write("a.csv", "a\n1\n")
    blocker = write("not_a_dir", "x")
    result = run_cli("check", str(source), "--format", "json", "--report", str(blocker / "r.json"))
    data = json.loads(result.out)
    assert result.code == 2
    assert data["summary"]["exit_code"] == 2 and data["summary"]["status"] == "valid"
    assert [(a["kind"], a["status"]) for a in data["artifacts"]] == [("report", "failed")]
    assert "cannot write the report" in result.err


def test_r7_clean_report_failure_keeps_written_csv_outcome(write, tmp_path):
    source = write("a.csv", "a\n1\n")
    blocker = write("not_a_dir", "x")
    out = tmp_path / "clean.csv"
    result = run_cli(
        "clean",
        str(source),
        "--apply",
        "--output",
        str(out),
        "--format",
        "json",
        "--report",
        str(blocker / "r.json"),
    )
    data = json.loads(result.out)
    assert result.code == 2 and data["summary"]["exit_code"] == 2
    assert [(a["kind"], a["status"]) for a in data["export"]["artifacts"]] == [
        ("output CSV", "written"),
        ("report", "failed"),
    ]
    assert out.read_bytes() == b"a\r\n1\r\n"


def test_r7_successful_report_lists_itself_and_matches_stdout(write, tmp_path):
    report = tmp_path / "r.txt"
    result = run_cli("check", str(write("a.csv", "a\n1\n")), "--report", str(report))
    assert result.code == 0
    assert report.read_text(encoding="utf-8") == result.out
    assert f"report: {report} - written" in result.out


# --------------------------------------------------------------- parsing contract


def test_quote_inside_unquoted_field_follows_python_csv_and_is_kept_literally(write):
    result = clean_file(write("q.csv", 'a,b\n1,a"b\n'))
    assert result.scan.complete and result.rows == (("1", 'a"b'),)
