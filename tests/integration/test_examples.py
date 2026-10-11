"""AC-13, AC-22, AC-23, AC-24, AC-27: documented commands on the example fixtures, end to end."""

import csv
import io
import json
from pathlib import Path

from conftest import run_cli, sha256

ID = "profiles/transactions-id.toml"
US = "profiles/customers-us.toml"


def parsed(path: Path, delimiter: str = ";") -> list[list[str]]:
    return list(
        csv.reader(io.StringIO(path.read_text(encoding="utf-8"), newline=""), delimiter=delimiter)
    )


def test_valid_fixtures_pass_check(examples):
    for data, profile in [
        ("transactions_valid.csv", ID),
        ("customers_valid.csv", US),
        ("transactions_canonical.csv", "profiles/transactions-canonical.toml"),
    ]:
        result = run_cli("check", str(examples / data), "--schema", str(examples / profile))
        assert result.code == 0, result.out


def test_transactions_fixable_full_chain(examples, monkeypatch):
    monkeypatch.chdir(examples.parent)
    source = examples / "transactions_fixable.csv"
    profile = examples / ID
    before = sha256(source), sha256(profile)

    check = run_cli("check", "examples/transactions_fixable.csv", "--schema", "examples/" + ID)
    assert check.code == 1
    assert "invalid_number (record 2, line 3, column 'amount')" in check.out
    assert "invalid_date (record 3, line 4, column 'date')" in check.out

    preview = run_cli(
        "clean", "examples/transactions_fixable.csv", "--schema", "examples/" + ID, "--dry-run"
    )
    assert preview.code == 0
    assert "Export: ready" in preview.out and "2 resolved" in preview.out
    assert not Path("output").exists()

    applied = run_cli(
        "clean",
        "examples/transactions_fixable.csv",
        "--schema",
        "examples/" + ID,
        "--apply",
        "--output",
        "output/transactions_clean.csv",
        "--output-schema",
        "output/transactions.output.toml",
    )
    assert applied.code == 0, applied.out + applied.err
    rows = parsed(Path("output/transactions_clean.csv"))
    assert rows == [
        ["transaction_id", "customer_id", "amount", "date", "note"],
        ["TX-001", "00123", "1250.50", "2026-02-01", "First payment"],
        ["TX-002", "00456", "980.00", "2026-02-15", "Paid in  two parts"],
        ["TX-003", "00789", "12000", "2026-02-28", "Note with ; semicolon"],
        ["TX-004", "00123", "-75.25", "2024-02-29", "Refund"],
    ]

    recheck = run_cli(
        "check", "output/transactions_clean.csv", "--schema", "output/transactions.output.toml"
    )
    assert recheck.code == 0, recheck.out
    again = run_cli(
        "clean",
        "output/transactions_clean.csv",
        "--schema",
        "output/transactions.output.toml",
        "--dry-run",
        "--format",
        "json",
    )
    report = json.loads(again.out)
    assert again.code == 0
    assert report["changes"]["changed_fields"] == 0 and report["changes"]["removed_records"] == 0
    assert (sha256(source), sha256(profile)) == before


def test_unfixable_transactions_block_export(examples, monkeypatch):
    monkeypatch.chdir(examples.parent)
    before = sha256(examples / "transactions_unfixable.csv")
    check = run_cli(
        "check",
        "examples/transactions_unfixable.csv",
        "--schema",
        "examples/" + ID,
        "--format",
        "json",
        "--report",
        "output/report.json",
    )
    assert check.code == 1
    report = json.loads(Path("output/report.json").read_text(encoding="utf-8"))
    assert json.loads(check.out) == report
    assert sorted((i["code"], i["record"]) for i in report["issues"]) == [
        ("invalid_date", 1),
        ("invalid_number", 3),
        ("missing_required", 2),
    ]
    blocked = run_cli(
        "clean",
        "examples/transactions_unfixable.csv",
        "--schema",
        "examples/" + ID,
        "--apply",
        "--output",
        "output/invalid_result.csv",
    )
    assert blocked.code == 1
    assert "Export: blocked by 3 remaining output errors" in blocked.out
    assert not Path("output/invalid_result.csv").exists()
    assert sha256(examples / "transactions_unfixable.csv") == before


def test_customers_us_profile_preserves_identifiers(examples, tmp_path):
    out = tmp_path / "customers.csv"
    result = run_cli(
        "clean",
        str(examples / "customers_fixable.csv"),
        "--schema",
        str(examples / US),
        "--apply",
        "--output",
        str(out),
    )
    assert result.code == 0, result.out
    rows = parsed(out, ",")
    assert rows[1] == ["00123", "Ada Lovelace", "081234567890", "1250.50", "2026-02-01"]
    assert rows[2][2] == "+62 812 3456 7890" and rows[3][1] == "Hopper, Grace Jr."


def test_trim_introduced_duplicates_block_until_deduplicated(examples, tmp_path):
    source, profile = str(examples / "customers_trim_duplicates.csv"), str(examples / US)
    assert run_cli("check", source, "--schema", profile).code == 0  # distinct before trimming
    blocked = run_cli("clean", source, "--schema", profile, "--format", "json")
    report = json.loads(blocked.out)
    assert blocked.code == 1
    assert [
        (i["code"], i["record"], i["introduced"]) for i in report["output_issues"]["items"]
    ] == [("duplicate_key", 2, True)]
    fixed = run_cli(
        "clean",
        source,
        "--schema",
        profile,
        "--deduplicate",
        "keys",
        "--apply",
        "--output",
        str(tmp_path / "dedup.csv"),
        "--output-schema",
        str(tmp_path / "dedup.toml"),
    )
    assert fixed.code == 0, fixed.out
    assert [r[1] for r in parsed(tmp_path / "dedup.csv", ",")[1:]] == [
        "Ada Lovelace",
        "Grace Hopper",
    ]
    assert 'deduplicate = "keys"' in (tmp_path / "dedup.toml").read_text(encoding="utf-8")
    recheck = run_cli(
        "check", str(tmp_path / "dedup.csv"), "--schema", str(tmp_path / "dedup.toml")
    )
    assert recheck.code == 0


def test_generated_profile_reflects_cli_overrides(examples, tmp_path):
    out, schema = tmp_path / "us.csv", tmp_path / "us.toml"
    result = run_cli(
        "clean",
        str(examples / "transactions_fixable.csv"),
        "--schema",
        str(examples / ID),
        "--output-delimiter",
        ",",
        "--output-number-format",
        "us",
        "--output-date-format",
        "MM/DD/YYYY",
        "--line-ending",
        "lf",
        "--apply",
        "--output",
        str(out),
        "--output-schema",
        str(schema),
    )
    assert result.code == 0, result.out
    assert out.read_bytes().startswith(
        b'transaction_id,customer_id,amount,date,note\nTX-001,00123,"1,250.50"'
    )
    text = schema.read_text(encoding="utf-8")
    assert (
        'delimiter = ","' in text
        and 'number_format = "us"' in text
        and 'line_ending = "lf"' in text
    )
    assert run_cli("check", str(out), "--schema", str(schema)).code == 0
    second = json.loads(run_cli("clean", str(out), "--schema", str(schema), "--format", "json").out)
    assert second["changes"]["changed_fields"] == 0
