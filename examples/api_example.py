"""Library example: check and clean the fixable transactions file without writing anything.

Run it from anywhere: python examples/api_example.py
"""

from pathlib import Path

from csv_tidy import check_file, clean_file, load_profile

HERE = Path(__file__).resolve().parent
profile = load_profile(HERE / "profiles" / "transactions-id.toml")
source = HERE / "transactions_fixable.csv"

check = check_file(source, profile)
print(f"check: {check.errors} errors, {check.warnings} warnings, exit code {check.exit_code}")
for issue in check.issues:
    print(f"  {issue.code}: record {issue.record}, column {issue.column}, value {issue.value!r}")

result = clean_file(source, profile)
print(f"clean: export ready = {result.export_ready}, {len(result.changes)} fields changed")
for change in result.changes[:3]:
    print(f"  record {change.record}, {change.column}: {change.before!r} -> {change.after!r}")
print(result.csv_text(), end="")
