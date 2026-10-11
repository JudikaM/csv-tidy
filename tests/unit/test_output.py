"""AC-17 to AC-20: path identity, collisions, overwrite policy, and atomic writes."""

import os
from pathlib import Path

import pytest

from csv_tidy import OutputError, clean_file, export_clean
from csv_tidy.output import render_csv, validate_artifact_paths, write_atomic


def test_render_csv_quotes_and_line_endings():
    rows = [("1", "a;b"), ("2", 'say "x"'), ("3", "multi\nline"), ("4", "cr\ronly")]
    text = render_csv(("id", "v"), rows, ";", "lf")
    assert text == 'id;v\n1;"a;b"\n2;"say ""x"""\n3;"multi\nline"\n4;"cr\ronly"\n'
    assert render_csv(("a",), [("",)], ",", "crlf") == 'a\r\n""\r\n'


def test_output_cannot_be_the_input(tmp_path):
    source = tmp_path / "in.csv"
    source.write_text("a\n1\n", encoding="utf-8")
    alias = tmp_path / "sub" / ".." / "in.csv"
    for target in (source, alias):
        with pytest.raises(OutputError, match="refers to the input CSV"):
            validate_artifact_paths({"input CSV": source}, {"output CSV": target}, overwrite=True)


def test_hardlink_alias_of_input_is_rejected(tmp_path):
    source = tmp_path / "in.csv"
    source.write_text("a\n1\n", encoding="utf-8")
    link = tmp_path / "hard.csv"
    os.link(source, link)
    with pytest.raises(OutputError, match="refers to the input CSV"):
        validate_artifact_paths({"input CSV": source}, {"output CSV": link}, overwrite=True)


def test_symlink_alias_of_input_is_rejected(tmp_path):
    source = tmp_path / "in.csv"
    source.write_text("a\n1\n", encoding="utf-8")
    link = tmp_path / "soft.csv"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available for this user/platform")
    with pytest.raises(OutputError, match="refers to the input CSV"):
        validate_artifact_paths({"input CSV": source}, {"output CSV": link}, overwrite=True)


def test_artifact_collisions_are_rejected(tmp_path):
    source = tmp_path / "in.csv"
    source.write_text("a\n", encoding="utf-8")
    same = tmp_path / "out.csv"
    with pytest.raises(OutputError, match="same file"):
        validate_artifact_paths(
            {"input CSV": source},
            {"output CSV": same, "report": tmp_path / "." / "out.csv"},
            overwrite=False,
        )


def test_existing_output_requires_overwrite(tmp_path):
    source = tmp_path / "in.csv"
    source.write_text("a\n", encoding="utf-8")
    existing = tmp_path / "out.csv"
    existing.write_text("old", encoding="utf-8")
    with pytest.raises(OutputError, match="already exists"):
        validate_artifact_paths({"input CSV": source}, {"output CSV": existing}, overwrite=False)
    validate_artifact_paths({"input CSV": source}, {"output CSV": existing}, overwrite=True)


def test_failed_replace_keeps_existing_file_and_removes_temp(tmp_path, monkeypatch):
    target = tmp_path / "out.csv"
    target.write_bytes(b"previous content")

    def broken_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", broken_replace)
    with pytest.raises(OSError):
        write_atomic(target, b"new content", overwrite=True)
    assert target.read_bytes() == b"previous content"
    assert [p.name for p in tmp_path.iterdir()] == ["out.csv"]


def test_export_writes_csv_and_profile_and_refuses_blocked_results(write, tmp_path):
    good = clean_file(write("g.csv", "a\n1\n"))
    outcomes = export_clean(
        good, tmp_path / "o" / "clean.csv", output_schema=tmp_path / "o" / "clean.toml"
    )
    assert [o.status for o in outcomes] == ["written", "written"]
    assert (tmp_path / "o" / "clean.csv").read_bytes() == b"a\r\n1\r\n"
    bad = clean_file(write("b.csv", "a,b\n1\n"))
    with pytest.raises(OutputError, match="export blocked"):
        export_clean(bad, tmp_path / "never.csv")
    assert not (tmp_path / "never.csv").exists()


def test_profile_write_failure_after_csv_is_reported(write, tmp_path, monkeypatch):
    result = clean_file(write("g.csv", "a\n1\n"))
    real = os.replace
    calls = []

    def replace_once(src, dst):
        calls.append(dst)
        if len(calls) == 2:
            raise OSError("permission denied")
        return real(src, dst)

    monkeypatch.setattr(os, "replace", replace_once)
    with pytest.raises(OutputError) as excinfo:
        export_clean(result, tmp_path / "c.csv", output_schema=tmp_path / "c.toml")
    assert [(o.kind, o.status) for o in excinfo.value.outcomes] == [
        ("output CSV", "written"),
        ("output profile", "failed"),
    ]
    assert Path(tmp_path / "c.csv").exists() and not (tmp_path / "c.toml").exists()
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]


def test_unencodable_output_fails_before_writing(write, tmp_path):
    from csv_tidy import Overrides

    result = clean_file(
        write("u.csv", "name\nZoë 日本\n"), overrides=Overrides(output_encoding="latin-1")
    )
    with pytest.raises(OutputError, match="cannot encode"):
        export_clean(result, tmp_path / "out.csv")
    assert not (tmp_path / "out.csv").exists()
