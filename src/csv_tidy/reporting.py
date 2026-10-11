"""English text and JSON reports. Totals are always complete even when details are truncated."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from . import __version__
from .api import CheckResult, CleanResult, ScanInfo
from .output import ArtifactOutcome
from .schema import Settings
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
        "value": value[:VALUE_LIMIT] if truncated else value,
        "value_truncated": truncated,
        "message": issue.message,
        "suggestion": issue.suggestion,
        "related_record": issue.related_record,
        "related_line": issue.related_line,
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
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "tool": {"name": "csv-tidy", "version": __version__},
        "command": "check",
        "source": _source_dict(
            result.source_path, result.profile_path, result.settings, result.scan.bom
        ),
        "scan": _scan_dict(result.scan),
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
        "artifacts": _artifact_list(artifacts),
    }


def _transformations(settings: Settings) -> dict[str, Any]:
    normalize = []
    for name in settings.normalize:
        column = settings.column(name)
        normalize.append(
            {
                "column": name,
                "type": column.type,
                "from": settings.source_format(column),
                "to": settings.output_format(column),
            }
        )
    return {
        "order": ["trim", "normalize", "deduplicate"],
        "trim": list(settings.trim),
        "normalize": normalize,
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
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "tool": {"name": "csv-tidy", "version": __version__},
        "command": "clean",
        "mode": mode,
        "source": _source_dict(
            result.source_path, result.profile_path, result.settings, result.scan.bom
        ),
        "output": {
            "delimiter": o.delimiter,
            "encoding": o.encoding,
            "number_format": o.number_format,
            "date_format": o.date_format,
            "line_ending": o.line_ending,
        },
        "transformations": _transformations(result.settings),
        "scan": _scan_dict(result.scan),
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


def _issue_lines(items: list[dict[str, Any]]) -> list[str]:
    lines = []
    for item in items:
        tag = item["severity"].upper()
        extra = f" [{item['status']}]" if "status" in item else ""
        extra += " [introduced by transformations]" if item.get("introduced") else ""
        lines.append(f"  {tag} {item['code']} ({_location(item)}){extra}")
        lines.append(f"    {item['message']}")
        lines.append(f"    Suggestion: {item['suggestion']}")
    return lines


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
        *_source_lines(report["source"]),
        _scan_line(report["scan"]),
        f"Result: {_n(s['errors'], 'error')}, {_n(s['warnings'], 'warning')}"
        + (", 1 fatal error" if s["fatal"] else ""),
    ]
    if d["total"]:
        lines.append("")
        lines.append(f"Issues (showing {d['shown']} of {d['total']}):")
        lines += _issue_lines(report["issues"])
        if d["truncated"]:
            lines.append(
                f"  ... {d['total'] - d['shown']} more issues not shown "
                "(totals above are complete)."
            )
    lines += _artifact_lines(report["artifacts"])
    lines.append("")
    verdict = {
        "valid": "source validation passed",
        "invalid": "source validation failed",
        "incomplete": "scan incomplete; the file was not fully validated",
    }[s["status"]]
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
        *_source_lines(report["source"]),
        f"Output: delimiter {o['delimiter']!r}, encoding {o['encoding']}, "
        f"numbers {o['number_format']}, "
        f"dates {o['date_format']}, line ending {o['line_ending'].upper()}",
        _scan_line(report["scan"]),
        "",
        "Transformations (applied in this order):",
        f"  1. trim: {', '.join(t['trim']) or 'none'}",
        "  2. normalize: "
        + (
            ", ".join(f"{n['column']} ({n['from']} -> {n['to']})" for n in t["normalize"]) or "none"
        ),
        f"  3. deduplicate: {t['deduplicate']}",
        "",
        f"Changes: {_n(c['changed_fields'], 'field')} changed "
        f"in {_n(c['changed_records'], 'record')}; "
        f"{_n(c['removed_records'], 'record')} removed; "
        f"{_n(c['output_records'], 'record')} in the result",
    ]
    for ex in c["examples"]:
        lines.append(
            f"  record {ex['record']} (line {ex['line_start']}), {ex['column']!r}: "
            f"{_show(ex['before'])} -> {_show(ex['after'])} [{', '.join(ex['steps'])}]"
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
    lines += [
        "",
        f"Source issues: {_n(si['errors'], 'error')}, {_n(si['warnings'], 'warning')} "
        f"({si['resolved']} resolved, {si['unresolved']} unresolved, "
        f"{si['removed']} removed with records)",
    ]
    lines += _issue_lines(si["items"])
    lines += [
        "",
        f"Remaining output issues: {_n(oi['errors'], 'error')}, {_n(oi['warnings'], 'warning')} "
        f"({oi['introduced']} introduced by transformations)",
    ]
    lines += _issue_lines(oi["items"])
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
    lines.append(f"Status: exit code {s['exit_code']}")
    return "\n".join(lines) + "\n"
