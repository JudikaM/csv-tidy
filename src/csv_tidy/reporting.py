"""English text and JSON reports. Totals are always complete even when details are truncated."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from . import __version__
from .api import CheckResult, CleanResult, ScanInfo
from .output import ArtifactOutcome
from .schema import DEFAULT_DELIMITER, DEFAULT_ENCODING, Settings, delimiter_option
from .validation import ERROR, FATAL, WARNING, Issue

REPORT_SCHEMA_VERSION = 1
VALUE_LIMIT = 200


def _issue_dict(issue: Issue) -> dict[str, Any]:
    value = issue.value
    truncated = value is not None and len(value) > VALUE_LIMIT
    data: dict[str, Any] = {
        "code": issue.code,
        "severity": issue.severity,
        "stage": issue.stage,
        "record": issue.record,
        "line_start": issue.line_start,
        "line_end": issue.line_end,
        "column": issue.column,
        "value": value[:VALUE_LIMIT] if value is not None and truncated else value,
        "value_truncated": truncated,
        "message": issue.message,
        "suggestion": issue.suggestion,
        "related_record": issue.related_record,
        "related_line": issue.related_line,
        "remedy": issue.remedy,
    }
    if issue.status is not None:
        data["status"] = issue.status
    if issue.introduced is not None:
        data["introduced"] = issue.introduced
    return data


def _scan_dict(scan: ScanInfo) -> dict[str, Any]:
    fatal = scan.fatal
    return {
        "complete": scan.complete,
        "data_records": scan.data_records,
        "physical_lines": scan.physical_lines,
        "blank_lines": scan.blank_lines,
        "fatal_error": {"code": fatal.code, "message": fatal.message, "line": fatal.line}
        if fatal
        else None,
    }


def _source_dict(path: str, profile: str | None, settings: Settings, bom: bool) -> dict[str, Any]:
    s = settings.source
    return {
        "path": path,
        "profile": profile,
        "delimiter": s.delimiter,
        "encoding": s.encoding,
        "bom": bom,
        "number_format": s.number_format,
        "date_format": s.date_format,
        "max_field_chars": s.max_field_chars,
    }


def _count(issues: Sequence[Issue], severity: str) -> int:
    return sum(i.severity == severity for i in issues)


def _artifact_list(artifacts: Sequence[ArtifactOutcome]) -> list[dict[str, Any]]:
    return [
        {"kind": a.kind, "path": a.path, "status": a.status, "error": a.error} for a in artifacts
    ]


def coverage_dict(settings: Settings, header: Sequence[str] | None) -> dict[str, Any]:
    """What the run could check. Without column rules only the file structure is checked;
    nothing is inferred from values or column names."""
    declared = [
        {
            "column": c.name,
            "type": c.type,
            "required": c.required,
            "format": None if c.type == "text" else settings.source_format(c),
        }
        for c in settings.columns
    ]
    ruled = {c.name for c in settings.columns if c.type != "text" or c.required}
    ruled |= {name for key in settings.duplicate_keys for name in key}
    names = {c.name for c in settings.columns}
    columns = list(dict.fromkeys(header or ()))
    return {
        "scope": "structure_and_values" if ruled else "structure_only",
        "structure": True,
        "header_columns": len(header) if header is not None else None,
        "declared_columns": declared,
        "undeclared_columns": [name for name in columns if name not in names],
        "unchecked_columns": [name for name in columns if name not in ruled],
        "unique_keys": [list(key) for key in settings.duplicate_keys],
        "duplicate_rows": settings.duplicate_rows,
    }


def shown_arg(value: str) -> str:
    """Quote a command-line value for display when it would not survive unquoted."""
    safe = value and all(ch.isalnum() or ch in "-_./\\:=+," for ch in value)
    return value if safe else '"' + value.replace('"', '\\"') + '"'


def _command(action: str, source: dict[str, Any], *extra: str) -> str:
    """A command for the same input. Without a profile, the non-default source settings are
    repeated; with one, options given on the command line must be repeated by the user."""
    parts = ["csv-tidy", action, shown_arg(source["path"])]
    if source["profile"]:
        parts += ["--schema", shown_arg(source["profile"])]
    else:
        if source["delimiter"] != DEFAULT_DELIMITER:
            parts += ["--delimiter", shown_arg(delimiter_option(source["delimiter"]))]
        if source["encoding"] != DEFAULT_ENCODING:
            parts += ["--encoding", shown_arg(source["encoding"])]
    return " ".join([*parts, *extra])


def _stop(scan: dict[str, Any]) -> str:
    fatal = scan["fatal_error"]
    where = f"at line {fatal['line']} " if fatal["line"] is not None else ""
    return f"the scan stopped {where}({fatal['code']})"


def _incomplete_steps(scan: dict[str, Any]) -> list[str]:
    fatal = scan["fatal_error"]
    where = f" near line {fatal['line']}" if fatal["line"] is not None else ""
    hint = {
        "decode_error": "Fix the bytes{where} or set the encoding the file really uses "
        "(--encoding, or [source] encoding in the profile)",
        "malformed_csv": "Fix the quoting{where} or set the delimiter the file really uses "
        "(--delimiter, or [source] delimiter in the profile)",
        "field_too_large": "Fix the record{where} (often an unclosed quote) or raise "
        "[source] max_field_chars in the profile",
    }.get(fatal["code"], "Fix the problem{where}")
    return [
        hint.format(where=where) + ", then run the command again.",
        f"Only {_n(scan['data_records'], 'record')} in front of that point "
        f"{'was' if scan['data_records'] == 1 else 'were'} read; "
        "nothing after it was scanned.",
    ]


def _profile_steps(source: dict[str, Any], coverage: dict[str, Any]) -> list[str]:
    if coverage["scope"] != "structure_only":
        return []
    if source["profile"]:
        return [
            f"The profile {source['profile']} declares no value rules. Declare decimal, date "
            "or required columns (or unique keys) in it to have values checked."
        ]
    start = _command("profile init", {**source, "profile": None}, "--output profile.toml")
    return [
        "No values were checked: numbers, dates, required fields and unique keys are only "
        "checked for columns declared in a profile, and nothing is guessed from the data.",
        f"Create a profile: {start} (add --interactive for guided questions), "
        "then run check again with --schema profile.toml.",
    ]


def _check_verdict(
    status: str, errors: int, warnings: int, scan: dict[str, Any], coverage: dict[str, Any]
) -> dict[str, str]:
    notes = f" ({_n(warnings, 'warning')} to review)" if warnings else ""
    if status == "incomplete":
        return {
            "state": "incomplete",
            "headline": f"INCOMPLETE - {_stop(scan)}; the file was not fully validated.",
        }
    if status == "invalid":
        return {
            "state": "failed",
            "headline": f"FAILED - {_n(errors, 'error')} found in the source file.{notes}",
        }
    if coverage["scope"] == "structure_only":
        return {
            "state": "passed_structure_only",
            "headline": "PASSED (structure only) - the file structure is consistent, but "
            f"values were not checked because no column rules are declared.{notes}",
        }
    return {
        "state": "passed",
        "headline": f"PASSED - no errors found by the declared rules.{notes}",
    }


def _check_steps(
    status: str, source: dict[str, Any], scan: dict[str, Any], coverage: dict[str, Any]
) -> list[str]:
    if status == "incomplete":
        return _incomplete_steps(scan)
    if status == "invalid":
        return [
            "Fix the listed values in the source file, or preview explicit repairs (a dry "
            f"run that writes nothing): {_command('clean', source)}",
            *_profile_steps(source, coverage),
        ]
    steps = _profile_steps(source, coverage)
    if not steps:
        steps = [
            "No action is needed. To prepare a cleaned copy, preview it with: "
            f"{_command('clean', source)}"
        ]
    return steps


def check_report(
    result: CheckResult,
    max_details: int,
    artifacts: Sequence[ArtifactOutcome] = (),
    exit_code: int | None = None,
) -> dict[str, Any]:
    """``summary.exit_code`` is the command's exit code, which is 2 if writing an artifact
    (the report) failed even when validation passed; ``summary.status`` is the validation result."""
    shown = list(result.issues[:max_details])
    status = "incomplete" if not result.scan.complete else ("invalid" if result.errors else "valid")
    source = _source_dict(result.source_path, result.profile_path, result.settings, result.scan.bom)
    scan = _scan_dict(result.scan)
    coverage = coverage_dict(result.settings, result.header)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "tool": {"name": "csv-tidy", "version": __version__},
        "command": "check",
        "verdict": _check_verdict(status, result.errors, result.warnings, scan, coverage),
        "source": source,
        "scan": scan,
        "coverage": coverage,
        "summary": {
            "status": status,
            "errors": result.errors,
            "warnings": result.warnings,
            "fatal": _count(result.issues, FATAL),
            "exit_code": result.exit_code if exit_code is None else exit_code,
        },
        "issues": [_issue_dict(i) for i in shown],
        "details": {
            "limit": max_details,
            "total": len(result.issues),
            "shown": len(shown),
            "truncated": len(shown) < len(result.issues),
        },
        "next_steps": _check_steps(status, source, scan, coverage),
        "artifacts": _artifact_list(artifacts),
    }


def _transformations(settings: Settings) -> dict[str, Any]:
    normalize = []
    for name in settings.normalize:
        column = settings.column(name)
        if column is None:  # unreachable: resolve_settings rejects undeclared columns
            continue
        normalize.append(
            {
                "column": name,
                "type": column.type,
                "from": settings.source_format(column),
                "to": settings.output_format(column),
            }
        )
    # The step appears in "order" only when selected, so reports without it are unchanged.
    neutralize = ["neutralize_formulas"] if settings.neutralize_formulas else []
    return {
        "order": ["trim", "normalize", *neutralize, "deduplicate"],
        "trim": list(settings.trim),
        "normalize": normalize,
        "neutralize_formulas": list(settings.neutralize_formulas),
        "deduplicate": settings.deduplicate,
    }


def clean_report(
    result: CleanResult,
    mode: str,
    max_details: int,
    max_examples: int,
    artifacts: Sequence[ArtifactOutcome] = (),
    exit_code: int | None = None,
) -> dict[str, Any]:
    src, out = result.source_issues, result.output_issues
    src_shown, out_shown = list(src[:max_details]), list(out[:max_details])
    changed_records = len({c.record for c in result.changes})
    if not result.scan.complete:
        status = "incomplete"
    else:
        status = "ready" if result.export_ready else "blocked"
    o = result.settings.output
    source = _source_dict(result.source_path, result.profile_path, result.settings, result.scan.bom)
    scan = _scan_dict(result.scan)
    coverage = coverage_dict(result.settings, result.header)
    repaired = sum(i.status == "resolved" and i.severity == ERROR for i in src)
    warnings = _count(out, WARNING)
    notes = f" ({_n(warnings, 'warning')} to review)" if warnings else ""
    if status == "incomplete":
        verdict = f"INCOMPLETE - {_stop(scan)}; nothing can be exported."
        steps = _incomplete_steps(scan)
    elif status == "ready":
        verdict = "READY TO EXPORT - no errors remain in the cleaned result"
        verdict += f"; {_n(repaired, 'source problem')} repaired" if repaired else ""
        verdict += f".{notes}"
        written = {a.kind: a.path for a in artifacts if a.status == "written"}
        if mode == "dry-run":
            steps = [
                "Nothing was written. To write the result, run the same command with "
                "--apply --output PATH (add --output-schema PATH to save a profile that "
                "describes the cleaned file)."
            ]
        elif "output CSV" in written:
            recheck = {**source, "path": written["output CSV"], "profile": None}
            if "output profile" in written:
                recheck["profile"] = written["output profile"]
                steps = [f"Re-check the exported file: {_command('check', recheck)}"]
            else:
                steps = [
                    "The cleaned CSV was written. Export again with --output-schema PATH to "
                    "get a profile for re-checking it."
                ]
        else:
            steps = ["The cleaned CSV was not written; see the error above and run again."]
        steps += _profile_steps(source, coverage)
    elif result.header is None:
        verdict = "BLOCKED - the file has no header row; nothing can be exported."
        steps = ["Provide a CSV file whose first row contains the column names."]
    else:
        count = _n(result.output_errors, "error")
        verb = "remains" if result.output_errors == 1 else "remain"
        verdict = f"BLOCKED - {count} {verb} in the cleaned result; nothing can be exported."
        steps = [
            f"Fix the {count} listed under 'Still to fix' in the source file, or select a "
            "transformation that repairs them (--trim COLUMN, --normalize COLUMN, "
            "--deduplicate rows|keys, or the profile's [transform] table), then run clean "
            "again.",
            "Each problem has its own suggestion. Nothing is exported while errors remain.",
        ]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "tool": {"name": "csv-tidy", "version": __version__},
        "command": "clean",
        "mode": mode,
        "verdict": {"state": status, "headline": verdict},
        "source": source,
        "coverage": coverage,
        "output": {
            "delimiter": o.delimiter,
            "encoding": o.encoding,
            "number_format": o.number_format,
            "date_format": o.date_format,
            "line_ending": o.line_ending,
        },
        "transformations": _transformations(result.settings),
        "scan": scan,
        "changes": {
            "changed_fields": len(result.changes),
            "changed_records": changed_records,
            "removed_records": len(result.removed),
            "output_records": len(result.rows),
            "examples": [
                {
                    "record": c.record,
                    "line_start": c.line_start,
                    "column": c.column,
                    "before": c.before,
                    "after": c.after,
                    "steps": list(c.steps),
                }
                for c in result.changes[:max_examples]
            ],
            "removed": [
                {
                    "record": r.record,
                    "line_start": r.line_start,
                    "reason": r.reason,
                    "kept_record": r.kept_record,
                    "key": list(r.key) if r.key else None,
                }
                for r in result.removed[:max_examples]
            ],
            "examples_limit": max_examples,
            "examples_truncated": len(result.changes) > max_examples
            or len(result.removed) > max_examples,
        },
        "source_issues": {
            "errors": _count(src, ERROR),
            "warnings": _count(src, WARNING),
            "fatal": _count(src, FATAL),
            "resolved": sum(i.status == "resolved" for i in src),
            "unresolved": sum(i.status == "unresolved" for i in src),
            "removed": sum(i.status == "removed" for i in src),
            "items": [_issue_dict(i) for i in src_shown],
        },
        "output_issues": {
            "errors": _count(out, ERROR),
            "warnings": _count(out, WARNING),
            "introduced": sum(bool(i.introduced) for i in out),
            "items": [_issue_dict(i) for i in out_shown],
        },
        "details": {
            "limit": max_details,
            "source_total": len(src),
            "output_total": len(out),
            "shown": len(src_shown) + len(out_shown),
            "truncated": len(src_shown) < len(src) or len(out_shown) < len(out),
        },
        "summary": {
            "status": status,
            "export_ready": result.export_ready,
            "output_errors": result.output_errors,
            "exit_code": result.exit_code if exit_code is None else exit_code,
        },
        "next_steps": steps,
        "export": {"artifacts": _artifact_list(artifacts)},
    }


def to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=True) + "\n"


# --------------------------------------------------------------------------- text


def _n(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


def _show(value: str | None, limit: int = 80) -> str:
    if value is None:
        return ""
    return repr(value if len(value) <= limit else value[:limit] + "...")


def _location(issue: dict[str, Any]) -> str:
    parts = []
    if issue["record"] is not None:
        parts.append(f"record {issue['record']}")
    if issue["line_start"] is not None:
        if issue["line_end"] not in (None, issue["line_start"]):
            parts.append(f"lines {issue['line_start']}-{issue['line_end']}")
        else:
            parts.append(f"line {issue['line_start']}")
    location = ", ".join(parts)
    if issue["column"]:
        location += f", column {issue['column']!r}" if location else f"column {issue['column']!r}"
    return location or "file"


def _issue_lines(items: list[dict[str, Any]], tag: str | None = None) -> list[str]:
    """``tag`` replaces the severity for source issues that no longer need action."""
    lines = []
    for item in items:
        extra = " [introduced by transformations]" if item.get("introduced") else ""
        lines.append(
            f"  {tag or item['severity'].upper()} {item['code']} ({_location(item)}){extra}"
        )
        if tag:
            lines.append(f"    Was: {item['message']}")
        else:
            lines.append(f"    {item['message']}")
            lines.append(f"    Suggestion: {item['suggestion']}")
    return lines


def _unresolved_first(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Errors and fatal problems in front of warnings; the order inside each group is kept."""
    return sorted(items, key=lambda item: item["severity"] == WARNING)


def _coverage_lines(coverage: dict[str, Any]) -> list[str]:
    def listed(parts: list[str], limit: int = 8) -> str:
        more = f", and {len(parts) - limit} more" if len(parts) > limit else ""
        return ", ".join(parts[:limit]) + more

    ruled = []
    for column in coverage["declared_columns"]:
        facts = [column["type"]]
        facts += [column["format"]] if column["format"] else []
        facts += ["required"] if column["required"] else []
        if column["type"] != "text" or column["required"]:
            ruled.append(f"{column['column']} ({', '.join(facts)})")
    total = coverage["header_columns"]
    unchecked = coverage["unchecked_columns"]
    checked = ["file structure"]
    if ruled:
        of = f" of {total}" if total is not None else ""
        noun = "column" if (total or len(ruled)) == 1 else "columns"
        checked.append(f"values in {len(ruled)}{of} {noun}: {listed(ruled)}")
    for key in coverage["unique_keys"]:
        checked.append(f"unique key ({' + '.join(key)})")
    if coverage["duplicate_rows"] == "warn":
        checked.append("duplicate rows (warning)")
    lines = ["Checked: " + "; ".join(checked)]
    if unchecked:
        every = "all " if coverage["scope"] == "structure_only" else ""
        noun = "column" if len(unchecked) == 1 else "columns"
        lines.append(
            f"Not checked: values in {every}{len(unchecked)} {noun} without rules "
            f"({listed(unchecked)})"
        )
    return lines


def _transformation_lines(t: dict[str, Any]) -> list[str]:
    normalized = ", ".join(f"{n['column']} ({n['from']} -> {n['to']})" for n in t["normalize"])
    described = {
        "trim": f"trim: {', '.join(t['trim']) or 'none'}",
        "normalize": f"normalize: {normalized or 'none'}",
        "neutralize_formulas": f"neutralize formulas: {', '.join(t['neutralize_formulas'])}",
        "deduplicate": f"deduplicate: {t['deduplicate']}",
    }
    return [f"  {number}. {described[step]}" for number, step in enumerate(t["order"], start=1)]


def _step_lines(steps: list[str]) -> list[str]:
    return ["", "Next steps:", *(f"  - {step}" for step in steps)] if steps else []


def _source_lines(source: dict[str, Any]) -> list[str]:
    lines = [f"Source: {source['path']}"]
    if source["profile"]:
        lines.append(f"Profile: {source['profile']}")
    lines.append(
        f"  delimiter {source['delimiter']!r}, encoding {source['encoding']} "
        f"(BOM {'present' if source['bom'] else 'absent'}), numbers {source['number_format']}, "
        f"dates {source['date_format']}"
    )
    return lines


def _scan_line(scan: dict[str, Any]) -> str:
    state = "complete" if scan["complete"] else "INCOMPLETE (stopped by a fatal error)"
    return (
        f"Scan: {state}; {_n(scan['data_records'], 'data record')}, "
        f"{_n(scan['physical_lines'], 'physical line')}, "
        f"{_n(scan['blank_lines'], 'blank line')}"
    )


def render_check_text(report: dict[str, Any]) -> str:
    s, d = report["summary"], report["details"]
    lines = [
        f"CSV Tidy {report['tool']['version']} - check",
        f"Verdict: {report['verdict']['headline']}",
        *_source_lines(report["source"]),
        _scan_line(report["scan"]),
        *_coverage_lines(report["coverage"]),
        f"Result: {_n(s['errors'], 'error')}, {_n(s['warnings'], 'warning')}"
        + (", 1 fatal error" if s["fatal"] else ""),
    ]
    if d["total"]:
        lines.append("")
        lines.append(f"Issues (showing {d['shown']} of {d['total']}, errors first):")
        lines += _issue_lines(_unresolved_first(report["issues"]))
        if d["truncated"]:
            lines.append(
                f"  ... {d['total'] - d['shown']} more issues not shown "
                "(totals above are complete)."
            )
    lines += _artifact_lines(report["artifacts"])
    lines += _step_lines(report["next_steps"])
    lines.append("")
    verdict = {
        "passed": "source validation passed",
        "passed_structure_only": "structure check passed; values were not checked",
        "failed": "source validation failed",
        "incomplete": "scan incomplete; the file was not fully validated",
    }[report["verdict"]["state"]]
    lines.append(f"Status: {verdict} (exit code {s['exit_code']})")
    return "\n".join(lines) + "\n"


def _artifact_lines(artifacts: list[dict[str, Any]]) -> list[str]:
    return [
        f"  {a['kind']}: {a['path']} - {a['status']}" + (f" ({a['error']})" if a["error"] else "")
        for a in artifacts
    ]


def render_clean_text(report: dict[str, Any]) -> str:
    mode = "dry run, nothing written" if report["mode"] == "dry-run" else "apply"
    o, t, c = report["output"], report["transformations"], report["changes"]
    lines = [
        f"CSV Tidy {report['tool']['version']} - clean ({mode})",
        f"Verdict: {report['verdict']['headline']}",
        *_source_lines(report["source"]),
        f"Output: delimiter {o['delimiter']!r}, encoding {o['encoding']}, "
        f"numbers {o['number_format']}, "
        f"dates {o['date_format']}, line ending {o['line_ending'].upper()}",
        _scan_line(report["scan"]),
        *_coverage_lines(report["coverage"]),
        "",
        "Transformations (applied in this order):",
        *_transformation_lines(t),
        "",
        f"Changes: {_n(c['changed_fields'], 'field')} changed "
        f"in {_n(c['changed_records'], 'record')}; "
        f"{_n(c['removed_records'], 'record')} removed; "
        f"{_n(c['output_records'], 'record')} in the result",
    ]
    for ex in c["examples"]:
        lines.append(
            f"  record {ex['record']} (line {ex['line_start']}), {ex['column']!r}: "
            f"{_show(ex['before'])} -> {_show(ex['after'])} "
            f"[{', '.join(step.replace('_', ' ') for step in ex['steps'])}]"
        )
    for rm in c["removed"]:
        lines.append(
            f"  removed record {rm['record']} (line {rm['line_start']}): {rm['reason']}, "
            f"kept record {rm['kept_record']}"
        )
    if c["examples_truncated"]:
        lines.append(
            f"  ... examples limited to {c['examples_limit']} per list (counts above are complete)."
        )
    si, oi, d = report["source_issues"], report["output_issues"], report["details"]
    lines.append("")
    if report["summary"]["status"] == "incomplete":
        # Nothing was transformed, so the source findings are the open problems.
        lines.append(
            "Still to fix: the problem that stopped the scan, and what was found before it"
        )
        lines += _issue_lines(_unresolved_first(si["items"]))
    elif oi["errors"] or oi["warnings"]:
        lines.append(
            f"Still to fix: {_n(oi['errors'], 'error')}, {_n(oi['warnings'], 'warning')} in "
            f"the cleaned result ({oi['introduced']} introduced by transformations)"
        )
        lines += _issue_lines(_unresolved_first(oi["items"]))
    else:
        lines.append("Still to fix: nothing; the cleaned result has no errors or warnings.")
    for status, tag, title in (
        ("resolved", "FIXED", "Repaired by the selected transformations"),
        ("removed", "REMOVED", "Gone with records removed as duplicates"),
    ):
        if si[status]:
            lines += ["", f"{title}: {si[status]} (no action needed)"]
            lines += _issue_lines([i for i in si["items"] if i.get("status") == status], tag)
    lines += [
        "",
        f"Source issues before cleaning: {_n(si['errors'], 'error')}, "
        f"{_n(si['warnings'], 'warning')} "
        f"({si['resolved']} resolved, {si['unresolved']} unresolved, "
        f"{si['removed']} removed with records)",
    ]
    if d["truncated"]:
        lines.append(
            f"  ... issue details limited to {d['limit']} per list (totals above are complete)."
        )
    s = report["summary"]
    lines.append("")
    if s["status"] == "incomplete":
        lines.append("Export: not possible; the scan is incomplete.")
    elif s["export_ready"]:
        lines.append(
            "Export: ready"
            + (
                " (run with --apply --output PATH to write it)"
                if report["mode"] == "dry-run"
                else ""
            )
        )
    else:
        lines.append(
            f"Export: blocked by {_n(s['output_errors'], 'remaining output error')}; "
            "no CSV is written."
        )
    lines += _artifact_lines(report["export"]["artifacts"])
    lines += _step_lines(report["next_steps"])
    lines.append("")
    lines.append(f"Status: exit code {s['exit_code']}")
    return "\n".join(lines) + "\n"
