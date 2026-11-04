"""AC-45: docs/STABILITY.md lists the whole covered surface that the code has.

Each test collects one part of the surface from the code (parser options, profile keys, issue
codes, remedies, JSON report fields, exported names) and checks that the inventory names it,
so that an addition to the public surface cannot be made without updating the inventory.
"""

import argparse
import ast
import re
from pathlib import Path

import csv_tidy
from csv_tidy import batch, formats, schema
from csv_tidy.api import FATAL_REMEDIES
from csv_tidy.cli import build_parser
from csv_tidy.reporting import check_report, clean_report

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "csv_tidy"
DOC = (ROOT / "docs" / "STABILITY.md").read_text(encoding="utf-8")
EXAMPLES = ROOT / "examples"


def section(title):
    """The text of one '###' section of the inventory, up to the next heading."""
    start = DOC.index(f"### {title}\n")
    end = re.compile(r"^#{2,3} ", flags=re.M).search(DOC, start + 1)
    return DOC[start : end.start() if end else len(DOC)]


def named(text, name):
    """``name`` appears in ``text`` as inline code, alone or followed by a space or '('."""
    return re.search("`" + re.escape(name) + r"[` (]", text) is not None


def parsers(parser, path=()):
    """Every (command path, parser) pair of the command-line interface."""
    yield path, parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                yield from parsers(child, (*path, name))


def first_string_args(module, call_name):
    tree = ast.parse((SRC / module).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == call_name
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            yield node.args[0].value


def keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys(item)


def test_every_command_and_option_is_listed():
    text = section("Commands and options")
    missing = []
    for path, parser in parsers(build_parser()):
        groups = ("batch", "profile", "shortcut")  # only hold subcommands
        if path and path[-1] not in groups and not named(text, " ".join(path)):
            missing.append(" ".join(path))
        for action in parser._actions:
            for option in action.option_strings:
                if option.startswith("--") and option != "--help" and not named(text, option):
                    missing.append(f"{' '.join(path) or 'csv-tidy'} {option}")
    assert not missing


def test_every_profile_key_and_value_is_listed():
    text = section("Profiles (`schema_version = 1`)")
    names = {
        *schema._TOP_KEYS,
        *schema._SOURCE_KEYS,
        *schema._OUTPUT_KEYS,
        *schema._COLUMN_KEYS,
        *schema._DUPLICATE_KEYS,
        *schema._TRANSFORM_KEYS,
    }
    names -= {"source", "output", "columns", "duplicates", "transform"}  # the table names
    values = {
        *schema.COLUMN_TYPES,
        *schema.LINE_ENDINGS,
        *schema.DUPLICATE_ROW_POLICIES,
        *schema.DEDUPLICATE_MODES,
        *formats.NUMBER_FORMATS,
    }
    assert [n for n in sorted(names) if not named(text, n)] == []
    assert [v for v in sorted(values) if f'`"{v}"`' not in text] == []
    for table in ("source", "output", "columns.NAME", "duplicates", "transform"):
        assert f"`[{table}]`" in text


def test_issue_codes_match_the_code_both_ways():
    text = section("Issue codes")
    in_code = set(first_string_args("validation.py", "Issue"))
    in_code |= set(first_string_args("reader.py", "FatalError"))
    listed = set(re.findall(r"^\| `([a-z_]+)` \|", text, flags=re.M))
    assert in_code == listed


def test_every_remedy_value_is_listed():
    tree = ast.parse((SRC / "validation.py").read_text(encoding="utf-8"))
    values = []  # remedy=... keywords and the return values of the *_remedy helpers
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "remedy":
            values.append(node.value)
        if isinstance(node, ast.FunctionDef) and node.name.endswith("_remedy"):
            values += [ret.value for ret in ast.walk(node) if isinstance(ret, ast.Return)]
    remedies = set(FATAL_REMEDIES.values())
    remedies |= {v.value for v in values if isinstance(v, ast.Constant) and v.value is not None}
    line = re.search(r"`remedy` values: (.*?)\.\n", section("Issue codes"), flags=re.S)
    assert line, "the issue-code section lists the remedy values"
    listed = set(re.findall(r"`([a-z_]+)`", line.group(1)))
    assert remedies == listed - {"null"}


def test_every_json_report_field_is_listed(tmp_path):
    text = section("JSON reports (`schema_version = 2`)")
    profile = EXAMPLES / "profiles" / "transactions-id.toml"
    data = EXAMPLES / "transactions_fixable.csv"
    clean = csv_tidy.clean_file(data, profile)
    reports = [
        check_report(csv_tidy.check_file(data, profile), 100),
        clean_report(clean, "dry_run", 100, 10),
    ]
    inputs = batch.select_inputs([data])
    reports.append(batch.batch_report(batch.run_batch("clean", inputs, profile)))
    found = {key for report in reports for key in keys(report)}
    assert [key for key in sorted(found) if not named(text, key)] == []
    assert clean.changes, "the example must produce change examples"


def test_every_exported_name_is_listed():
    text = section("Python API")
    assert [n for n in csv_tidy.__all__ if not named(text, n)] == []
