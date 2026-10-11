"""Command-line interface. Reports go to stdout; operational errors go to stderr."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .api import check_file, clean_file, export_clean
from .errors import CsvTidyError, OutputError
from .formats import NUMBER_FORMATS
from .output import ArtifactOutcome, encode_text, validate_artifact_paths, write_artifact
from .reporting import check_report, clean_report, render_check_text, render_clean_text, to_json
from .schema import DEDUPLICATE_MODES, DELIMITERS, LINE_ENDINGS, Overrides, load_profile

MAIN_EPILOG = """\
examples:
  csv-tidy check data.csv --schema profile.toml
  csv-tidy check data.csv --schema profile.toml --format json --report output/report.json
  csv-tidy clean data.csv --schema profile.toml            (dry run, writes nothing)
  csv-tidy clean data.csv --schema profile.toml --apply --output output/clean.csv \\
      --output-schema output/clean.output.toml

exit codes: 0 no blocking errors, 1 data errors (check: source; clean: remaining output),
            2 usage, configuration, decoding/parsing, read or write failure
"""

CHECK_EPILOG = """\
check validates the source file and never modifies it. Exit code 1 means the source has
errors; warnings alone do not fail. Transformations in the profile are ignored by check.
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
    sub = parser.add_subparsers(dest="command", required=True, metavar="{check,clean}")

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
    return parser


def _list_option(args: argparse.Namespace, name: str) -> tuple[str, ...] | None:
    """``--no-NAME`` clears the list, ``--NAME`` replaces it, neither keeps the profile's."""
    if getattr(args, f"no_{name}", False):
        return ()
    values = getattr(args, name, None)
    return tuple(values) if values is not None else None


def _overrides(args: argparse.Namespace) -> Overrides:
    get = lambda name: getattr(args, name, None)  # noqa: E731
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


def _publish(build, render, args: argparse.Namespace, outcomes: list, exit_code: int) -> int:
    """Save the requested report first, then print the final report to stdout.

    The printed (and saved) report lists every artifact outcome and the final exit code, so a
    failed report write is never hidden behind a successful-looking summary.
    """

    def text_for(items: list, code: int) -> str:
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

    def build(items: list, code: int) -> dict:
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

    def build(items: list, code: int) -> dict:
        return clean_report(result, mode, args.max_details, args.max_examples, items, code)

    return _publish(build, render_clean_text, args, outcomes, exit_code)


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "clean":
            return run_clean(args, parser)
        return run_check(args)
    except CsvTidyError as exc:
        print(f"csv-tidy: error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("csv-tidy: interrupted", file=sys.stderr)
        return 130
