"""Command-line interface. Reports go to stdout; operational errors go to stderr."""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import __version__, batch, profile_init, update
from .api import check_file, clean_file, export_clean
from .errors import CsvTidyError, OutputError, ProfileError
from .formats import NUMBER_FORMATS
from .output import ArtifactOutcome, encode_text, validate_artifact_paths, write_artifact
from .reporting import (
    check_report,
    clean_report,
    render_check_text,
    render_clean_text,
    shown_arg,
    to_json,
)
from .schema import (
    DEDUPLICATE_MODES,
    DEFAULT_DELIMITER,
    DEFAULT_ENCODING,
    DELIMITERS,
    LINE_ENDINGS,
    Overrides,
    load_profile,
    resolve_settings,
)

if TYPE_CHECKING:
    _Subparsers = argparse._SubParsersAction[argparse.ArgumentParser]
    # Builds a report from the artifact outcomes and the final exit code.
    _ReportBuilder = Callable[[list[ArtifactOutcome], int], dict[str, Any]]

MAIN_EPILOG = """\
examples:
  csv-tidy profile init data.csv --output profile.toml     (starting profile, all text)
  csv-tidy check data.csv --schema profile.toml
  csv-tidy check data.csv --schema profile.toml --format json --report output/report.json
  csv-tidy clean data.csv --schema profile.toml            (dry run, writes nothing)
  csv-tidy batch clean exports/ --schema profile.toml      (many files, one profile)
  csv-tidy ui                                              (local browser interface)
  csv-tidy shortcut install                                (icons that start it)
  csv-tidy update --check                                  (the only command that goes online)
  csv-tidy clean data.csv --schema profile.toml --apply --output output/clean.csv \\
      --output-schema output/clean.output.toml

exit codes: 0 no blocking errors, 1 data errors (check: source; clean: remaining output),
            2 usage, configuration, decoding/parsing, read or write failure
"""

CHECK_EPILOG = """\
check validates the source file and never modifies it. Exit code 1 means the source has
errors; warnings alone do not fail. Transformations in the profile are ignored by check.
"""

PROFILE_INIT_EPILOG = """\
profile init reads only the header of INPUT and writes a starting profile in which every
column is text. Nothing is inferred from the values or the column names: choose decimal and
date columns, required columns, keys and transformations with the options below, with
--interactive, or by editing the file afterwards.

Without --interactive the command never prompts and never reads standard input, so it is
safe in scripts and CI. With --interactive, questions are written to stderr; answer q (or
press Ctrl+C) to cancel without writing anything (exit code 130).

examples:
  csv-tidy profile init data.csv --delimiter ";" --output profile.toml
  csv-tidy profile init data.csv --output profile.toml --interactive
  csv-tidy profile init data.csv --output profile.toml --decimal amount --date date \\
      --number-format id --date-format DD/MM/YYYY --required id --key id --trim amount
"""

BATCH_EPILOG = """\
Every file is processed on its own with the same profile and options, through the same
pipeline as the single-file commands. batch clean is a preview unless --apply is given.

selection: a file is taken as given. A folder selects the files directly inside it whose
names match --pattern (default *.csv, case-insensitive), sorted by name; --recursive also
selects files in subfolders. Selecting no file, or the same file twice, is an error.

outputs: for an input NAME.csv the cleaned file is DIR/NAME.clean.csv, its output profile
DIR/NAME.output.toml and its report REPORTDIR/NAME.report.json. Files found in subfolders
keep their subfolder below DIR. If two inputs would produce the same path, or a path is an
input or an existing file (without --overwrite), the batch stops before reading anything.

One file failing never removes the results of other files. --report saves the batch summary.

exit codes: 2 if any file failed, could not be fully read, or could not be written; otherwise
            1 if any file has data errors (check: in the source; clean: remaining in the
            result); otherwise 0

examples:
  csv-tidy batch check exports/ --schema profile.toml
  csv-tidy batch clean exports/ --schema profile.toml            (preview)
  csv-tidy batch clean exports/ jan.csv --schema profile.toml --apply --output-dir cleaned/ \\
      --output-schemas --report-dir reports/ --format json
"""

SHORTCUT_EPILOG = """\
Windows: "CSV Tidy" on the Desktop and in the Start Menu starts the local interface without a
console window (the csv-tidy-ui program); it stops by itself 10 minutes after its page was
closed. "Update CSV Tidy" in the Start Menu runs `csv-tidy update`. Linux: the same entries
in the applications menu, and "CSV Tidy" on the Desktop if that folder exists. macOS is not
supported yet; start the csv-tidy-ui program instead.

Run it once per user after installing CSV Tidy; the icons keep working after updates. Icons
with the same names that belong to other programs are never changed or removed.

examples:
  csv-tidy shortcut install
  csv-tidy shortcut install --no-desktop
  csv-tidy shortcut remove
"""

UPDATE_EPILOG = """\
update asks the GitHub API for the latest release of CSV Tidy (or the one given with
--version), and, if it is newer than the installed version, runs pip to install the wheel
attached to that release. pip checks the SHA-256 that GitHub publishes for the wheel and
refuses a file that does not match. This is the only command that connects to the internet,
and it does so only when you run it. Profiles keep working after an update.

Close CSV Tidy before updating, and start it again afterwards to use the new version.

exit codes: 0 updated, already up to date, or --check; 2 GitHub or pip failed
"""

UI_EPILOG = """\
ui starts a small web server on this computer only (127.0.0.1) and opens a page with the
same check and clean pipeline as the commands: choose one file or several files, set the
separator and encoding, describe the columns or load a profile, check, preview the cleaning,
and save the results as downloads (one file at a time, or every result of several files as a
ZIP). "More settings" holds the output settings, max_field_chars, and how many problems,
changed values, and preview rows are listed.

The chosen files are copied to a private temporary folder that is removed when the server
stops; the originals are never written to. The page loads nothing from the internet. The
printed address contains a one-time key; other programs and web pages cannot use the server
without it.

Stop it with the Quit button on the page or Ctrl+C in this window.
"""

CLEAN_EPILOG = """\
clean applies only the transformations you select, in this order: trim, normalize,
deduplicate (keep first). It is a dry run unless --apply is given; --apply requires --output.
The exit code reflects errors that remain in the cleaned result. Source errors repaired by
the selected transformations are reported as resolved.

--trim and --normalize replace the profile's lists when given (repeat them for several
columns). Output settings default to the resolved source settings.
"""


def _source_options(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("source options (override the profile)")
    group.add_argument("--schema", metavar="PROFILE", help="TOML profile (schema_version = 1)")
    group.add_argument("--delimiter", choices=DELIMITERS, help="source delimiter (default ',')")
    group.add_argument(
        "--encoding", help="source encoding (default utf-8; a UTF-8 BOM is accepted)"
    )
    group.add_argument(
        "--number-format",
        choices=NUMBER_FORMATS,
        help="default grammar for decimal columns (default canonical)",
    )
    group.add_argument(
        "--date-format",
        metavar="FORMAT",
        help="default format for date columns, e.g. DD/MM/YYYY (default YYYY-MM-DD)",
    )


def _report_options(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("report options")
    group.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="report format on stdout and in --report (default text)",
    )
    group.add_argument("--report", metavar="PATH", help="also save the report to PATH")
    group.add_argument(
        "--max-details",
        type=_non_negative,
        default=100,
        metavar="N",
        help="maximum issues listed per list (totals stay complete; default 100)",
    )
    group.add_argument(
        "--overwrite",
        action="store_true",
        help="allow replacing existing output files (never the input files)",
    )


def _transform_options(clean: argparse.ArgumentParser) -> None:
    out = clean.add_argument_group("output options (default: follow the resolved source settings)")
    out.add_argument("--output-delimiter", choices=DELIMITERS)
    out.add_argument("--output-encoding", metavar="ENCODING")
    out.add_argument("--output-number-format", choices=NUMBER_FORMATS)
    out.add_argument("--output-date-format", metavar="FORMAT")
    out.add_argument(
        "--line-ending", choices=LINE_ENDINGS, help="output line ending (default crlf)"
    )
    tr = clean.add_argument_group("transformations (explicit; replace the profile's lists)")
    tr.add_argument(
        "--trim",
        action="append",
        metavar="COLUMN",
        help="strip leading/trailing whitespace in COLUMN (repeatable)",
    )
    tr.add_argument(
        "--normalize",
        action="append",
        metavar="COLUMN",
        help="rewrite decimal/date COLUMN in the output format (repeatable)",
    )
    tr.add_argument(
        "--no-trim", action="store_true", help="disable the profile's trim list for this run"
    )
    tr.add_argument(
        "--no-normalize",
        action="store_true",
        help="disable the profile's normalize list for this run",
    )
    tr.add_argument(
        "--deduplicate",
        choices=DEDUPLICATE_MODES,
        help="remove later duplicates, keeping the first record (default off)",
    )


def _non_negative(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer") from None
    if value < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="csv-tidy",
        description=(
            "Validate and explicitly clean CSV files with declared number and date formats."
        ),
        epilog=MAIN_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"csv-tidy {__version__}")
    sub = parser.add_subparsers(
        dest="command", required=True, metavar="{check,clean,batch,profile,ui,shortcut,update}"
    )

    check = sub.add_parser(
        "check",
        help="validate a CSV file (never modifies it)",
        epilog=CHECK_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    check.add_argument("input", metavar="INPUT", help="CSV file to validate")
    _source_options(check)
    _report_options(check)

    clean = sub.add_parser(
        "clean",
        help="preview or apply selected transformations",
        epilog=CLEAN_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    clean.add_argument("input", metavar="INPUT", help="CSV file to clean (never modified)")
    _source_options(clean)
    _transform_options(clean)
    mode = clean.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview only (the default)")
    mode.add_argument("--apply", action="store_true", help="write the cleaned CSV to --output")
    clean.add_argument("--output", metavar="PATH", help="cleaned CSV path (requires --apply)")
    clean.add_argument(
        "--output-schema",
        metavar="PATH",
        help="save the effective output profile (requires --apply)",
    )
    clean.add_argument(
        "--max-examples",
        type=_non_negative,
        default=10,
        metavar="N",
        help="maximum before/after examples shown (default 10)",
    )
    _report_options(clean)
    _batch_parser(sub)
    _profile_parser(sub)
    sc = sub.add_parser(
        "shortcut",
        help="add or remove CSV Tidy icons (Desktop and Start Menu)",
        description="Add or remove icons that start CSV Tidy without a command line.",
        epilog=SHORTCUT_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scs = sc.add_subparsers(dest="shortcut_command", required=True, metavar="{install,remove}")
    for name, text in (
        ("install", "create or refresh the icons"),
        ("remove", "remove the icons that CSV Tidy created"),
    ):
        cmd = scs.add_parser(
            name,
            help=text,
            epilog=SHORTCUT_EPILOG,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        cmd.add_argument(
            "--folder",
            metavar="DIR",
            help="put the icons in DIR instead of the Desktop and the Start Menu",
        )
        if name == "install":
            cmd.add_argument(
                "--no-desktop", action="store_true", help="only add the Start Menu entries"
            )
    upd = sub.add_parser(
        "update",
        help="install the latest release from GitHub (the only command that goes online)",
        epilog=UPDATE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    upd.add_argument(
        "--check", action="store_true", help="only report whether a newer release exists"
    )
    upd.add_argument(
        "--version",
        dest="target_version",
        metavar="X.Y.Z",
        help="install this release instead of the latest (also older ones)",
    )
    upd.add_argument(
        "--pause",
        action="store_true",
        help="wait for Enter before exiting (used by the Update CSV Tidy shortcut)",
    )
    ui = sub.add_parser(
        "ui",
        help="open the local browser interface (for people who prefer forms)",
        epilog=UI_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ui.add_argument(
        "--port",
        type=_port,
        default=0,
        metavar="N",
        help="loopback port to listen on (default: a free port chosen automatically)",
    )
    ui.add_argument(
        "--idle-minutes",
        type=_non_negative,
        default=0,
        metavar="N",
        help="stop by itself after N minutes without an open page (default 0: never; the "
        "csv-tidy-ui program uses 10)",
    )
    ui.add_argument(
        "--no-browser",
        action="store_true",
        help="only print the address instead of opening the default browser",
    )
    ui.add_argument(
        "--max-file-mb",
        type=_positive,
        default=200,
        metavar="N",
        help="largest file, and largest total of several files chosen together, in MB "
        "(default 200; results are built in memory)",
    )
    return parser


def _port(text: str) -> int:
    value = _non_negative(text)
    if value > 65535:
        raise argparse.ArgumentTypeError("must be between 0 and 65535")
    return value


def _positive(text: str) -> int:
    value = _non_negative(text)
    if value == 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return value


def _batch_parser(sub: _Subparsers) -> None:
    parent = sub.add_parser(
        "batch",
        help="check or clean many files with one profile",
        description="Process many files with one profile. Subcommands: check, clean.",
    )
    bsub = parent.add_subparsers(dest="batch_command", required=True, metavar="{check,clean}")
    for name in ("check", "clean"):
        cmd = bsub.add_parser(
            name,
            help=f"{name} every selected file",
            epilog=BATCH_EPILOG,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        cmd.add_argument(
            "inputs",
            nargs="+",
            metavar="INPUT",
            help="CSV files and/or folders (a folder selects the files directly inside it)",
        )
        sel = cmd.add_argument_group("selection inside folders")
        sel.add_argument(
            "--pattern",
            default=batch.DEFAULT_PATTERN,
            metavar="GLOB",
            help="file-name pattern for folder members, case-insensitive (default *.csv)",
        )
        sel.add_argument("--recursive", action="store_true", help="also select files in subfolders")
        _source_options(cmd)
        if name == "clean":
            _transform_options(cmd)
            mode = cmd.add_mutually_exclusive_group()
            mode.add_argument("--dry-run", action="store_true", help="preview only (the default)")
            mode.add_argument(
                "--apply", action="store_true", help="write cleaned files to --output-dir"
            )
            cmd.add_argument(
                "--output-dir",
                metavar="DIR",
                help="folder for NAME.clean.csv files (requires --apply)",
            )
            cmd.add_argument(
                "--output-schemas",
                action="store_true",
                help="also write NAME.output.toml next to each cleaned file (requires --apply)",
            )
            cmd.add_argument(
                "--max-examples",
                type=_non_negative,
                default=10,
                metavar="N",
                help="maximum before/after examples in per-file reports (default 10)",
            )
        cmd.add_argument(
            "--report-dir",
            metavar="DIR",
            help="write one full report per file as NAME.report.json (or .txt with --format text)",
        )
        _report_options(cmd)


def _profile_parser(sub: _Subparsers) -> None:
    profile = sub.add_parser(
        "profile",
        help="create a starting profile from a CSV header",
        description="Create profiles. Subcommand: init.",
    )
    psub = profile.add_subparsers(dest="profile_command", required=True, metavar="{init}")
    init = psub.add_parser(
        "init",
        help="write a starting profile for INPUT (all columns text; nothing is guessed)",
        epilog=PROFILE_INIT_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    init.add_argument("input", metavar="INPUT", help="CSV file whose header is read")
    init.add_argument("--output", required=True, metavar="PROFILE", help="profile file to write")
    init.add_argument(
        "--overwrite", action="store_true", help="allow replacing an existing profile file"
    )
    init.add_argument(
        "--interactive",
        action="store_true",
        help="answer guided questions instead of (or in addition to) the options below",
    )
    src = init.add_argument_group("how to read the file (written into the profile)")
    src.add_argument("--delimiter", choices=DELIMITERS, help="delimiter (default ',')")
    src.add_argument("--encoding", help="encoding (default utf-8)")
    src.add_argument(
        "--number-format",
        choices=NUMBER_FORMATS,
        help="grammar of decimal columns (default canonical)",
    )
    src.add_argument(
        "--date-format", metavar="FORMAT", help="format of date columns (default YYYY-MM-DD)"
    )
    cols = init.add_argument_group("column rules (repeat an option for several columns)")
    cols.add_argument("--decimal", action="append", default=[], metavar="COLUMN")
    cols.add_argument("--date", action="append", default=[], metavar="COLUMN")
    cols.add_argument("--required", action="append", default=[], metavar="COLUMN")
    cols.add_argument(
        "--key",
        action="append",
        default=[],
        nargs="+",
        metavar="COLUMN",
        help="uniqueness key; several columns after one --key form a combined key",
    )
    tr = init.add_argument_group("transformations to record in the profile")
    tr.add_argument("--trim", action="append", default=[], metavar="COLUMN")
    tr.add_argument("--normalize", action="append", default=[], metavar="COLUMN")
    tr.add_argument("--deduplicate", choices=DEDUPLICATE_MODES)
    tr.add_argument("--output-number-format", choices=NUMBER_FORMATS)
    tr.add_argument("--output-date-format", metavar="FORMAT")


def _list_option(args: argparse.Namespace, name: str) -> tuple[str, ...] | None:
    """``--no-NAME`` clears the list, ``--NAME`` replaces it, neither keeps the profile's."""
    if getattr(args, f"no_{name}", False):
        return ()
    values = getattr(args, name, None)
    return tuple(values) if values is not None else None


def _overrides(args: argparse.Namespace) -> Overrides:
    def get(name: str) -> Any:
        return getattr(args, name, None)

    return Overrides(
        delimiter=args.delimiter,
        encoding=args.encoding,
        number_format=args.number_format,
        date_format=args.date_format,
        output_delimiter=get("output_delimiter"),
        output_encoding=get("output_encoding"),
        output_number_format=get("output_number_format"),
        output_date_format=get("output_date_format"),
        line_ending=get("line_ending"),
        trim=_list_option(args, "trim"),
        normalize=_list_option(args, "normalize"),
        deduplicate=get("deduplicate"),
    )


def _protected(args: argparse.Namespace) -> dict[str, Path]:
    protected = {"input CSV": Path(args.input)}
    if args.schema:
        protected["input profile"] = Path(args.schema)
    return protected


def _publish(
    build: _ReportBuilder,
    render: Callable[[dict[str, Any]], str],
    args: argparse.Namespace,
    outcomes: list[ArtifactOutcome],
    exit_code: int,
) -> int:
    """Save the requested report first, then print the final report to stdout.

    The printed (and saved) report lists every artifact outcome and the final exit code, so a
    failed report write is never hidden behind a successful-looking summary.
    """

    def text_for(items: list[ArtifactOutcome], code: int) -> str:
        report = build(items, code)
        return to_json(report) if args.format == "json" else render(report)

    if args.report:
        planned = [*outcomes, ArtifactOutcome("report", args.report, "written")]
        text = text_for(planned, exit_code)
        try:
            write_artifact(
                Path(args.report), encode_text(text, "utf-8", "report"), args.overwrite, "report"
            )
        except OutputError as exc:
            exit_code = 2
            failed = [*outcomes, ArtifactOutcome("report", args.report, "failed", str(exc))]
            text = text_for(failed, exit_code)
            print(f"csv-tidy: error: {exc}", file=sys.stderr)
        else:
            print(f"csv-tidy: report written to {args.report}", file=sys.stderr)
    else:
        text = text_for(outcomes, exit_code)
    sys.stdout.write(text)
    sys.stdout.flush()
    return exit_code


def run_check(args: argparse.Namespace) -> int:
    if args.report:
        validate_artifact_paths(_protected(args), {"report": Path(args.report)}, args.overwrite)
    profile = load_profile(args.schema) if args.schema else None
    result = check_file(args.input, profile, overrides=_overrides(args))

    def build(items: list[ArtifactOutcome], code: int) -> dict[str, Any]:
        return check_report(result, args.max_details, items, code)

    return _publish(build, render_check_text, args, [], result.exit_code)


def run_clean(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.trim and args.no_trim:
        parser.error("--trim cannot be combined with --no-trim")
    if args.normalize and args.no_normalize:
        parser.error("--normalize cannot be combined with --no-normalize")
    if args.apply and not args.output:
        parser.error("--apply requires --output PATH")
    if not args.apply and (args.output or args.output_schema):
        parser.error("--output and --output-schema require --apply (clean is a dry run by default)")
    artifacts = {
        "output CSV": args.output,
        "output profile": args.output_schema,
        "report": args.report,
    }
    validate_artifact_paths(
        _protected(args), {k: Path(v) if v else None for k, v in artifacts.items()}, args.overwrite
    )
    profile = load_profile(args.schema) if args.schema else None
    result = clean_file(args.input, profile, overrides=_overrides(args))

    outcomes: list[ArtifactOutcome] = []
    exit_code = result.exit_code
    failure = None
    if args.apply:
        if result.export_ready:
            try:
                outcomes = list(
                    export_clean(
                        result,
                        args.output,
                        output_schema=args.output_schema,
                        overwrite=args.overwrite,
                    )
                )
            except OutputError as exc:
                failure = exc
                outcomes = list(exc.outcomes) or [
                    ArtifactOutcome("output CSV", args.output, "failed", str(exc))
                ]
                exit_code = 2
        else:
            outcomes.append(
                ArtifactOutcome("output CSV", args.output, "not_written", "output errors remain")
            )
            if args.output_schema:
                outcomes.append(
                    ArtifactOutcome(
                        "output profile", args.output_schema, "not_written", "output errors remain"
                    )
                )
    mode = "apply" if args.apply else "dry-run"
    if failure is not None:
        print(f"csv-tidy: error: {failure}", file=sys.stderr)

    def build(items: list[ArtifactOutcome], code: int) -> dict[str, Any]:
        return clean_report(result, mode, args.max_details, args.max_examples, items, code)

    return _publish(build, render_clean_text, args, outcomes, exit_code)


def run_batch_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    action = args.batch_command
    apply = bool(getattr(args, "apply", False))
    output_dir = getattr(args, "output_dir", None)
    output_schemas = bool(getattr(args, "output_schemas", False))
    if action == "clean":
        if args.trim and args.no_trim:
            parser.error("--trim cannot be combined with --no-trim")
        if args.normalize and args.no_normalize:
            parser.error("--normalize cannot be combined with --no-normalize")
        if apply and not output_dir:
            parser.error("--apply requires --output-dir DIR")
        if not apply and (output_dir or output_schemas):
            parser.error(
                "--output-dir and --output-schemas require --apply "
                "(batch clean is a dry run by default)"
            )
    profile = load_profile(args.schema) if args.schema else None
    inputs = batch.select_inputs(args.inputs, args.pattern, args.recursive)
    result = batch.run_batch(
        action,
        inputs,
        profile,
        overrides=_overrides(args),
        apply=apply,
        output_dir=output_dir,
        output_schemas=output_schemas,
        report_dir=args.report_dir,
        report_format=args.format,
        overwrite=args.overwrite,
        max_details=args.max_details,
        max_examples=getattr(args, "max_examples", 10),
        extra_artifacts={"batch report": Path(args.report)} if args.report else None,
    )

    def build(items: list[ArtifactOutcome], code: int) -> dict[str, Any]:
        return batch.batch_report(result, items, code)

    return _publish(build, batch.render_batch_text, args, [], result.exit_code)


def run_shortcut(args: argparse.Namespace) -> int:
    from . import shortcuts

    if args.shortcut_command == "install":
        outcomes = shortcuts.install(args.folder, desktop=not args.no_desktop)
    else:
        outcomes = shortcuts.remove(args.folder)
    for outcome in outcomes:
        note = " (belongs to another program; left as it is)" if outcome.status == "skipped" else ""
        print(f"{outcome.status}: {outcome.path}{note}")
    if args.shortcut_command == "install" and any(o.status != "skipped" for o in outcomes):
        print("Start CSV Tidy with the CSV Tidy icon; it opens in your browser.")
    return 0


def run_update(args: argparse.Namespace) -> int:
    code = _update(args)
    if args.pause:
        with contextlib.suppress(EOFError, KeyboardInterrupt):
            input("\nPress Enter to close this window. ")
    return code


def _update(args: argparse.Namespace) -> int:
    try:
        release = update.find_release(args.target_version)
    except CsvTidyError as exc:
        print(f"csv-tidy: error: {exc}", file=sys.stderr)
        return 2
    current = __version__
    newer = update.version_key(release.version) > update.version_key(current)
    if args.check:
        print(f"Installed: CSV Tidy {current}. Latest release: {release.version}.")
        if newer:
            print(f"CSV Tidy {release.version} is available ({release.page_url}).")
            print("Install it with: csv-tidy update")
        else:
            print("CSV Tidy is up to date.")
        return 0
    if release.version == current or (not newer and args.target_version is None):
        print(f"CSV Tidy {current} is up to date (latest release: {release.version}).")
        return 0
    print(f"Updating CSV Tidy from {current} to {release.version} ({release.page_url}).")
    print("Close CSV Tidy if it is open; start it again after the update.")
    print(
        f"Downloading {release.wheel_name} from GitHub; pip verifies its SHA-256 "
        f"({release.sha256[:12]}...)."
    )
    sys.stdout.flush()
    code = update.run_pip(update.pip_command(release, sys.executable))
    if code != 0:
        print(
            f"csv-tidy: error: pip could not install CSV Tidy {release.version} (exit code "
            f"{code}); see pip's messages above. CSV Tidy {current} is still installed.",
            file=sys.stderr,
        )
        return 2
    print(f"Updated to {release.version}. Start CSV Tidy again to use the new version.")
    return 0


def _ask(prompt: str) -> str:
    """Prompt on stderr (stdout stays free for results) and read one line from stdin."""
    sys.stderr.write(prompt)
    sys.stderr.flush()
    line = sys.stdin.readline()
    if not line:
        raise EOFError
    return line.rstrip("\r\n")


def _say(text: str) -> None:
    print(text, file=sys.stderr)


def run_profile_init(args: argparse.Namespace) -> int:
    output = Path(args.output)
    validate_artifact_paths({"input CSV": Path(args.input)}, {"profile": output}, args.overwrite)
    # Validate option values before reading anything or asking any question.
    resolve_settings(
        None,
        Overrides(
            encoding=args.encoding,
            date_format=args.date_format,
            output_date_format=args.output_date_format,
        ),
    )
    choices = profile_init.Choices(
        number_format=args.number_format,
        date_format=args.date_format,
        decimal=tuple(args.decimal),
        date=tuple(args.date),
        required=tuple(args.required),
        keys=tuple(tuple(key) for key in args.key),
        trim=tuple(args.trim),
        normalize=tuple(args.normalize),
        deduplicate=args.deduplicate,
        output_number_format=args.output_number_format,
        output_date_format=args.output_date_format,
    )
    try:
        if args.interactive:
            delimiter, encoding = profile_init.ask_source(_ask, _say, args.delimiter, args.encoding)
        else:
            delimiter = args.delimiter or DEFAULT_DELIMITER
            encoding = args.encoding or DEFAULT_ENCODING
        header = profile_init.read_header(args.input, delimiter, encoding)
        if not args.interactive:
            profile = profile_init.build_profile(header, choices)
        while args.interactive:
            try:
                profile = profile_init.build_profile(
                    header, profile_init.guided_choices(header, choices, _ask, _say)
                )
            except ProfileError as exc:
                _say(f"\nThat combination is not valid: {exc}\nLet us go through it again.")
                continue
            _say("\n" + profile_init.render_profile(profile, Path(args.input).name))
            if not profile_init.confirm(_ask, _say, f"Write this profile to {output}?"):
                raise profile_init.Cancelled("the profile was not confirmed")
            break
    except (profile_init.Cancelled, KeyboardInterrupt) as exc:
        reason = str(exc) or "interrupted"
        print(
            f"\ncsv-tidy: profile init cancelled; nothing was written ({reason})",
            file=sys.stderr,
        )
        return 130
    text = profile_init.render_profile(profile, Path(args.input).name)
    write_artifact(output, encode_text(text, "utf-8", "profile"), args.overwrite, "profile")
    kinds = [column.type for column in profile.columns]
    counts = ", ".join(f"{kinds.count(kind)} {kind}" for kind in ("text", "decimal", "date"))
    command = f"{shown_arg(args.input)} --schema {shown_arg(args.output)}"
    print(f"Profile written: {output} ({len(kinds)} columns: {counts})")
    print("Next steps:")
    if not (
        set(kinds) - {"text"}
        or profile.duplicate_keys
        or any(column.required for column in profile.columns)
    ):
        print(
            "  - Every column is text, so values are not checked yet. Edit the profile (or "
            "run again with --interactive) to declare decimal, date and required columns."
        )
    print(f"  - Check the file:   csv-tidy check {command}")
    print(f"  - Preview a clean:  csv-tidy clean {command}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "clean":
            return run_clean(args, parser)
        if args.command == "batch":
            return run_batch_command(args, parser)
        if args.command == "profile":
            return run_profile_init(args)
        if args.command == "update":
            return run_update(args)
        if args.command == "shortcut":
            return run_shortcut(args)
        if args.command == "ui":
            from .ui import run_ui  # imported on demand: check/clean do not need a server

            return run_ui(args.port, not args.no_browser, args.max_file_mb, args.idle_minutes)
        return run_check(args)
    except CsvTidyError as exc:
        print(f"csv-tidy: error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("csv-tidy: interrupted", file=sys.stderr)
        return 130
