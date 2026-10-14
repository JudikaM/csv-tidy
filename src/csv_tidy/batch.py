"""Process several CSV files with one explicit profile.

Each file goes through the same ``check_file``/``clean_file``/``export_clean`` functions as
the single-file commands and gets its own result, outputs and (optionally) report. Files are
handled one after another and only a summary of each is kept, so memory use is that of the
largest file. A failure in one file never removes or blocks the results of the others.

Everything that could make two results overwrite each other, an input, or an existing file is
checked for the whole batch before the first file is read.
"""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from . import __version__
from .api import check_file, clean_file, export_clean
from .errors import CsvTidyError, InputError, OutputError
from .output import ArtifactOutcome, encode_text, write_artifact
from .reporting import (
    REPORT_SCHEMA_VERSION,
    check_report,
    clean_report,
    coverage_dict,
    render_check_text,
    render_clean_text,
    shown_arg,
    to_json,
)
from .schema import Overrides, Profile, load_profile, resolve_settings

DEFAULT_PATTERN = "*.csv"
ACTIONS = ("check", "clean")


@dataclass(frozen=True)
class BatchInput:
    """One selected file. ``relative`` decides where its outputs go below the output folder:
    the file name for a file given directly, the path below the folder for a folder member.
    ``label``, when given, names the file in outcomes and reports instead of ``path`` (the
    local interface uses it to show the original file name instead of a private copy)."""

    path: Path
    relative: Path
    label: str | None = None

    @property
    def shown(self) -> str:
        return self.label or str(self.path)


@dataclass(frozen=True)
class FileOutcome:
    """Summary of one file. ``status`` is ``valid``/``invalid`` (check) or ``ready``/``blocked``
    (clean), ``incomplete`` for a scan stopped by a fatal error, or ``failed`` when the file
    or one of its outputs could not be read or written (``error`` says why)."""

    path: str
    relative: Path
    status: str
    exit_code: int
    data_records: int = 0
    errors: int = 0
    warnings: int = 0
    output_errors: int | None = None
    changed_fields: int = 0
    removed_records: int = 0
    structure_only: bool = False
    artifacts: tuple[ArtifactOutcome, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class BatchResult:
    action: str
    mode: str | None  # "dry-run" or "apply" for clean, None for check
    profile_path: str | None
    files: tuple[FileOutcome, ...]

    @property
    def exit_code(self) -> int:
        """2 if any file failed or was not fully scanned, else 1 if any has data errors."""
        return max((outcome.exit_code for outcome in self.files), default=0)


def select_inputs(
    inputs: Iterable[str | Path], pattern: str = DEFAULT_PATTERN, recursive: bool = False
) -> list[BatchInput]:
    """Expand files and folders into the list of files to process, in a stable order.

    A file is taken as given, whatever its name. A folder contributes the files directly
    inside it whose names match ``pattern`` (case-insensitive), sorted by name; with
    ``recursive`` its subfolders are included too. Selecting nothing, or the same file twice,
    is an error.
    """
    chosen: list[BatchInput] = []
    for item in inputs:
        path = Path(item)
        if not path.is_dir():
            chosen.append(BatchInput(path, Path(path.name)))
            continue
        members = path.rglob("*") if recursive else path.iterdir()
        found = [
            member
            for member in members
            if member.is_file() and fnmatch.fnmatchcase(member.name.lower(), pattern.lower())
        ]
        if not found:
            where = "in or below" if recursive else "directly in"
            raise InputError(
                f"no files matching {pattern!r} {where} the folder {path} "
                "(use --pattern or --recursive to select differently)"
            )
        found.sort(key=lambda member: member.relative_to(path).as_posix().casefold())
        chosen += [BatchInput(member, member.relative_to(path)) for member in found]
    if not chosen:
        raise InputError("no input files were given")
    seen: dict[str, Path] = {}
    for item in chosen:
        key = _key(item.path)
        if key in seen:
            raise InputError(
                f"{item.path} is selected more than once (also as {seen[key]}); list each file once"
            )
        seen[key] = item.path
    return chosen


def _key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def _identity(path: Path) -> tuple[int, int] | None:
    try:
        info = path.stat()
    except OSError:
        return None
    return (info.st_dev, info.st_ino) if info.st_ino else None


def plan_artifacts(
    inputs: Sequence[BatchInput],
    *,
    output_dir: str | Path | None = None,
    output_schemas: bool = False,
    report_dir: str | Path | None = None,
    report_format: str = "json",
) -> list[dict[str, Path]]:
    """The artifact paths of every input, in input order.

    ``NAME.csv`` becomes ``NAME.clean.csv``, ``NAME.output.toml`` and ``NAME.report.json``
    (or ``.txt``), below the given folders at the input's relative location.
    """
    plans = []
    for item in inputs:
        parent, stem = item.relative.parent, item.relative.stem
        plan: dict[str, Path] = {}
        if output_dir is not None:
            plan["output CSV"] = Path(output_dir) / parent / f"{stem}.clean.csv"
            if output_schemas:
                plan["output profile"] = Path(output_dir) / parent / f"{stem}.output.toml"
        if report_dir is not None:
            suffix = "json" if report_format == "json" else "txt"
            plan["report"] = Path(report_dir) / parent / f"{stem}.report.{suffix}"
        plans.append(plan)
    return plans


def check_artifacts(
    protected: Mapping[str, Path], artifacts: Sequence[tuple[str, Path]], overwrite: bool
) -> None:
    """Refuse the whole batch if any artifact would overwrite an input, another artifact, or
    (without ``overwrite``) an existing file. Nothing has been read or written at this point."""
    by_key = {_key(path): label for label, path in protected.items()}
    by_identity = {_identity(path): label for label, path in protected.items()}
    by_identity.pop(None, None)
    planned: dict[str, str] = {}
    for label, path in artifacts:
        key = _key(path)
        source = by_key.get(key) or by_identity.get(_identity(path))
        if source is not None:
            raise OutputError(
                f"the {label} path {path} refers to the {source}; refusing to overwrite it "
                "(choose another output folder)"
            )
        if key in planned:
            raise OutputError(
                f"the {planned[key]} and the {label} would both be written to {path}. "
                "Inputs with the same name need different output locations: select their "
                "common folder with --recursive, rename one, or run them separately"
            )
        planned[key] = label
        if path.is_dir():
            raise OutputError(f"the {label} path {path} is a directory")
        if path.exists() and not overwrite:
            raise OutputError(
                f"the {label} file already exists: {path} (use --overwrite to replace it). "
                "Nothing was written"
            )


def run_batch(
    action: str,
    inputs: Sequence[BatchInput],
    profile: Profile | str | Path | None = None,
    *,
    overrides: Overrides | None = None,
    apply: bool = False,
    output_dir: str | Path | None = None,
    output_schemas: bool = False,
    report_dir: str | Path | None = None,
    report_format: str = "json",
    overwrite: bool = False,
    max_details: int = 100,
    max_examples: int = 10,
    extra_artifacts: Mapping[str, Path] | None = None,
) -> BatchResult:
    """Check or clean every input with the same profile and overrides.

    ``clean`` is a preview unless ``apply`` is true, which requires ``output_dir``. Invalid
    settings and unsafe artifact paths raise before any file is read. Problems of a single
    file (unreadable, incomplete scan, failed write) are recorded in its ``FileOutcome``.
    """
    if action not in ACTIONS:
        raise ValueError(f"action must be one of {ACTIONS}")
    if action == "check" and (apply or output_dir is not None or output_schemas):
        raise OutputError("batch check writes no cleaned files; use batch clean with apply")
    if apply and output_dir is None:
        raise OutputError("apply requires an output folder")
    if not apply and (output_dir is not None or output_schemas):
        raise OutputError("an output folder requires apply (batch clean is a preview by default)")
    loaded = load_profile(profile) if isinstance(profile, (str, Path)) else profile
    resolve_settings(loaded, overrides)

    plans = plan_artifacts(
        inputs,
        output_dir=output_dir,
        output_schemas=output_schemas,
        report_dir=report_dir,
        report_format=report_format,
    )
    protected = {f"input CSV {item.path}": item.path for item in inputs}
    if loaded is not None and loaded.resolved_path:
        protected["input profile"] = Path(loaded.resolved_path)
    labelled = [
        (f"{kind} for {item.path}", path)
        for item, plan in zip(inputs, plans, strict=True)
        for kind, path in plan.items()
    ]
    labelled += list((extra_artifacts or {}).items())
    check_artifacts(protected, labelled, overwrite)

    outcomes = []
    for item, plan in zip(inputs, plans, strict=True):
        try:
            outcomes.append(
                _one(
                    action,
                    item,
                    plan,
                    loaded,
                    overrides,
                    apply,
                    report_format,
                    overwrite,
                    max_details,
                    max_examples,
                )
            )
        except CsvTidyError as exc:
            outcomes.append(FileOutcome(item.shown, item.relative, "failed", 2, error=str(exc)))
    mode = None if action == "check" else ("apply" if apply else "dry-run")
    return BatchResult(action, mode, loaded.path if loaded else None, tuple(outcomes))


def _one(
    action: str,
    item: BatchInput,
    plan: dict[str, Path],
    profile: Profile | None,
    overrides: Overrides | None,
    apply: bool,
    report_format: str,
    overwrite: bool,
    max_details: int,
    max_examples: int,
) -> FileOutcome:
    artifacts: list[ArtifactOutcome] = []
    error = None
    if action == "check":
        result = check_file(item.path, profile, overrides=overrides)
        if item.label:
            result = replace(result, source_path=item.label)
        status = "valid" if result.exit_code == 0 else "invalid"
        facts = {"errors": result.errors, "warnings": result.warnings}
    else:
        result = clean_file(item.path, profile, overrides=overrides)
        if item.label:
            result = replace(result, source_path=item.label)
        status = "ready" if result.export_ready else "blocked"
        facts = {
            "errors": sum(i.severity == "error" for i in result.source_issues),
            "warnings": sum(i.severity == "warning" for i in result.output_issues),
            "output_errors": result.output_errors,
            "changed_fields": len(result.changes),
            "removed_records": len(result.removed),
        }
        if apply and result.export_ready:
            try:
                artifacts += export_clean(
                    result,
                    plan["output CSV"],
                    output_schema=plan.get("output profile"),
                    overwrite=overwrite,
                )
            except OutputError as exc:
                error = str(exc)
                artifacts += exc.outcomes or [
                    ArtifactOutcome("output CSV", str(plan["output CSV"]), "failed", error)
                ]
        elif apply:
            reason = "output errors remain" if result.scan.complete else "the scan is incomplete"
            artifacts += [
                ArtifactOutcome(kind, str(plan[kind]), "not_written", reason)
                for kind in ("output CSV", "output profile")
                if kind in plan
            ]
    exit_code = 2 if error else result.exit_code
    if not result.scan.complete:
        status = "incomplete"
        fatal = result.scan.fatal
        where = f" at line {fatal.line}" if fatal.line is not None else ""
        error = error or f"the scan stopped{where} ({fatal.code}): {fatal.message}"

    if "report" in plan:
        target = plan["report"]

        def text_for(report_outcome: ArtifactOutcome, code: int) -> str:
            listed = [*artifacts, report_outcome]
            if action == "check":
                report = check_report(result, max_details, listed, code)
                return to_json(report) if report_format == "json" else render_check_text(report)
            mode = "apply" if apply else "dry-run"
            report = clean_report(result, mode, max_details, max_examples, listed, code)
            return to_json(report) if report_format == "json" else render_clean_text(report)

        try:
            text = text_for(ArtifactOutcome("report", str(target), "written"), exit_code)
            artifacts.append(
                write_artifact(target, encode_text(text, "utf-8", "report"), overwrite, "report")
            )
        except OutputError as exc:
            exit_code, error = 2, error or str(exc)
            artifacts.append(ArtifactOutcome("report", str(target), "failed", str(exc)))
    if exit_code == 2 and result.scan.complete:
        status = "failed"
    coverage = coverage_dict(result.settings, result.header)
    return FileOutcome(
        item.shown,
        item.relative,
        status,
        exit_code,
        data_records=result.scan.data_records,
        structure_only=coverage["scope"] == "structure_only",
        artifacts=tuple(artifacts),
        error=error,
        **facts,
    )


# --------------------------------------------------------------------------- reports


def batch_report(
    result: BatchResult,
    artifacts: Sequence[ArtifactOutcome] = (),
    exit_code: int | None = None,
) -> dict[str, Any]:
    """The batch summary as a dictionary. ``totals.errors`` counts the errors that decide the
    exit code: source errors for ``check``, errors remaining in the result for ``clean``."""
    files = []
    for outcome in result.files:
        files.append(
            {
                "path": outcome.path,
                "status": outcome.status,
                "exit_code": outcome.exit_code,
                "data_records": outcome.data_records,
                "errors": outcome.errors,
                "warnings": outcome.warnings,
                "output_errors": outcome.output_errors,
                "changed_fields": outcome.changed_fields,
                "removed_records": outcome.removed_records,
                "structure_only": outcome.structure_only,
                "error": outcome.error,
                "artifacts": [
                    {"kind": a.kind, "path": a.path, "status": a.status, "error": a.error}
                    for a in outcome.artifacts
                ],
            }
        )
    decisive = (
        (lambda o: o.errors) if result.action == "check" else (lambda o: o.output_errors or 0)
    )
    totals = {
        "files": len(result.files),
        "ok": sum(o.exit_code == 0 for o in result.files),
        "data_errors": sum(o.exit_code == 1 for o in result.files),
        "failed": sum(o.exit_code == 2 for o in result.files),
        "data_records": sum(o.data_records for o in result.files),
        "errors": sum(decisive(o) for o in result.files),
        "warnings": sum(o.warnings for o in result.files),
        "changed_fields": sum(o.changed_fields for o in result.files),
        "removed_records": sum(o.removed_records for o in result.files),
        "written": sum(
            a.kind == "output CSV" and a.status == "written"
            for o in result.files
            for a in o.artifacts
        ),
    }
    code = result.exit_code if exit_code is None else exit_code
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "tool": {"name": "csv-tidy", "version": __version__},
        "command": "batch",
        "action": result.action,
        "mode": result.mode,
        "profile": result.profile_path,
        "verdict": _verdict(totals, sum(o.structure_only for o in result.files)),
        "files": files,
        "totals": totals,
        "next_steps": _next_steps(result, totals),
        "summary": {"exit_code": code},
        "artifacts": [
            {"kind": a.kind, "path": a.path, "status": a.status, "error": a.error}
            for a in artifacts
        ],
    }


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


def _verdict(totals: dict[str, int], structure_only: int) -> dict[str, str]:
    attention = totals["data_errors"] + totals["failed"]
    if not attention and structure_only:
        return {
            "state": "ok_structure_only",
            "headline": f"All {_plural(totals['files'], 'file')} passed the structure check; "
            f"values were not checked in {structure_only} of them (no column rules).",
        }
    if not attention:
        return {"state": "ok", "headline": f"All {_plural(totals['files'], 'file')} passed."}
    verb = "needs" if attention == 1 else "need"
    parts = []
    if totals["failed"]:
        parts.append(f"{totals['failed']} failed or could not be fully read")
    if totals["data_errors"]:
        parts.append(f"{totals['data_errors']} with data errors")
    return {
        "state": "failed" if totals["failed"] else "data_errors",
        "headline": f"{attention} of {_plural(totals['files'], 'file')} {verb} attention "
        f"({', '.join(parts)}).",
    }


def _next_steps(result: BatchResult, totals: dict[str, int]) -> list[str]:
    schema = f" --schema {shown_arg(result.profile_path)}" if result.profile_path else ""
    steps = []
    if totals["failed"]:
        steps.append(
            "Files marked FAILED or INCOMPLETE were not processed completely; their line "
            "says why. The other files are not affected."
        )
    if totals["data_errors"]:
        word = "INVALID" if result.action == "check" else "BLOCKED"
        steps.append(
            f"For details of a file marked {word}, run it alone: "
            f"csv-tidy {result.action} FILE{schema} (or add --report-dir DIR for one "
            "report per file)."
        )
    if result.mode == "dry-run" and totals["ok"]:
        steps.append(
            "Nothing was written. To write the files that are ready, add "
            "--apply --output-dir DIR (files with remaining errors are skipped)."
        )
    if any(outcome.structure_only for outcome in result.files):
        steps.append(
            "Only the file structure was checked (no column rules). Create a profile with "
            "csv-tidy profile init FILE --output profile.toml and pass it with --schema."
        )
    return steps


def render_batch_text(report: dict[str, Any]) -> str:
    mode = {None: "", "dry-run": " (dry run, nothing written)", "apply": " (apply)"}[report["mode"]]
    totals = report["totals"]
    lines = [
        f"CSV Tidy {report['tool']['version']} - batch {report['action']}{mode}",
        f"Verdict: {report['verdict']['headline']}",
        f"Profile: {report['profile'] or 'none (structure checks only)'}",
        "",
        "Files:",
    ]
    labels = {"valid": "OK"}
    for entry in report["files"]:
        facts = [_plural(entry["data_records"], "record")]
        if report["action"] == "check":
            facts.append(
                f"{_plural(entry['errors'], 'error')}, {_plural(entry['warnings'], 'warning')}"
            )
        else:
            facts.append(f"{_plural(entry['output_errors'] or 0, 'error')} remaining")
            facts.append(f"{_plural(entry['changed_fields'], 'field')} changed")
            facts.append(f"{_plural(entry['removed_records'], 'record')} removed")
        if entry["structure_only"] and entry["exit_code"] == 0:
            facts.append("structure only, values not checked")
        label = labels.get(entry["status"], entry["status"].upper())
        if entry["status"] == "failed" and entry["data_records"] == 0 and not entry["artifacts"]:
            lines.append(f"  {label:<10} {entry['path']}")
        else:
            lines.append(f"  {label:<10} {entry['path']}: {'; '.join(facts)}")
        if entry["error"]:
            lines.append(f"             {entry['error']}")
        for artifact in entry["artifacts"]:
            note = f" ({artifact['error']})" if artifact["error"] else ""
            lines.append(
                f"             {artifact['kind']}: {artifact['path']} - {artifact['status']}{note}"
            )
    good = "ok" if report["action"] == "check" else "ready"
    lines += [
        "",
        f"Totals: {_plural(totals['files'], 'file')}: {totals['ok']} {good}, "
        f"{totals['data_errors']} with data errors, {totals['failed']} failed; "
        f"{_plural(totals['data_records'], 'record')}, {_plural(totals['errors'], 'error')}, "
        f"{_plural(totals['warnings'], 'warning')}"
        + (
            f"; {_plural(totals['changed_fields'], 'field')} changed, "
            f"{_plural(totals['removed_records'], 'record')} removed, "
            f"{_plural(totals['written'], 'CSV file')} written"
            if report["action"] == "clean"
            else ""
        ),
    ]
    lines += [
        f"  {a['kind']}: {a['path']} - {a['status']}" + (f" ({a['error']})" if a["error"] else "")
        for a in report["artifacts"]
    ]
    if report["next_steps"]:
        lines += ["", "Next steps:", *(f"  - {step}" for step in report["next_steps"])]
    lines += ["", f"Status: exit code {report['summary']['exit_code']}"]
    return "\n".join(lines) + "\n"
