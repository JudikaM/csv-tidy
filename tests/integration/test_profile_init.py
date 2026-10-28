"""`csv-tidy profile init`: explicit templates, guided answers, and safe writing."""

import io

import pytest
from conftest import EXAMPLES, run_cli, sha256

from csv_tidy import check_file, clean_file, load_profile
from csv_tidy.schema import resolve_settings

FIXABLE = EXAMPLES / "transactions_fixable.csv"


def init(*args):
    return run_cli("profile", "init", *args)


@pytest.fixture
def answers(monkeypatch):
    def _answers(*lines):
        monkeypatch.setattr("sys.stdin", io.StringIO("".join(f"{line}\n" for line in lines)))

    return _answers


@pytest.fixture
def no_stdin(monkeypatch):
    class Closed:
        def readline(self):
            raise AssertionError("a non-interactive run must never read standard input")

        read = __iter__ = readline

    monkeypatch.setattr("sys.stdin", Closed())


def test_template_declares_every_column_as_text_and_guesses_nothing(tmp_path, no_stdin):
    out = tmp_path / "p.toml"
    result = init(str(FIXABLE), "--delimiter", ";", "--output", str(out))
    assert result.code == 0, result.err
    profile = load_profile(out)
    assert profile.source_delimiter == ";" and profile.source_encoding == "utf-8"
    assert [(c.name, c.type, c.required) for c in profile.columns] == [
        ("transaction_id", "text", False),
        ("customer_id", "text", False),
        ("amount", "text", False),
        ("date", "text", False),
        ("note", "text", False),
    ]
    assert profile.duplicate_keys == () and profile.trim == () and profile.normalize == ()
    assert profile.deduplicate == "off"
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# ") and "nothing was inferred" in text
    assert str(out) in result.out and "check" in result.out
    # The template has no value rules yet, and check says so instead of looking successful.
    report = run_cli("check", str(FIXABLE), "--schema", str(out)).out
    assert "PASSED (structure only)" in report and "declares no value rules" in report


def test_values_that_look_like_numbers_or_dates_stay_text(tmp_path, write):
    source = write("n.csv", "id,amount,when\n001,12.50,2026-01-31\n002,13.00,2026-02-01\n")
    out = tmp_path / "p.toml"
    assert init(str(source), "--output", str(out)).code == 0
    assert {c.type for c in load_profile(out).columns} == {"text"}


def test_options_build_a_complete_profile_without_prompting(tmp_path, no_stdin):
    out = tmp_path / "p.toml"
    result = init(
        str(FIXABLE),
        "--output",
        str(out),
        "--delimiter",
        ";",
        "--number-format",
        "id",
        "--date-format",
        "DD/MM/YYYY",
        "--decimal",
        "amount",
        "--date",
        "date",
        "--required",
        "transaction_id",
        "--required",
        "amount",
        "--key",
        "transaction_id",
        "--key",
        "customer_id",
        "date",
        "--trim",
        "customer_id",
        "--trim",
        "amount",
        "--trim",
        "date",
        "--normalize",
        "amount",
        "--normalize",
        "date",
        "--output-number-format",
        "canonical",
        "--output-date-format",
        "YYYY-MM-DD",
    )
    assert result.code == 0, result.err
    profile = load_profile(out)
    assert profile.duplicate_keys == (("transaction_id",), ("customer_id", "date"))
    assert profile.source_number_format == "id" and profile.output_date_format == "YYYY-MM-DD"
    check = check_file(FIXABLE, profile)
    assert [(i.code, i.record) for i in check.issues] == [
        ("invalid_number", 2),
        ("invalid_date", 3),
    ]
    assert clean_file(FIXABLE, profile).export_ready


def test_special_column_names_round_trip(tmp_path, write):
    header = ["a.b", "x y", 'quo"te', "ünï", "[k]", "#c", " padded "]
    line = ",".join('"' + name.replace('"', '""') + '"' for name in header)
    source = write("s.csv", line + "\n1,2,3,4,5,6,7\n")
    out = tmp_path / "p.toml"
    result = init(str(source), "--output", str(out), "--decimal", "ünï", "--required", 'quo"te')
    assert result.code == 0, result.err
    profile = load_profile(out)
    assert [c.name for c in profile.columns] == header
    assert profile.columns[3].type == "decimal" and profile.columns[2].required
    assert check_file(source, profile).errors == 0


def test_existing_destination_and_inputs_are_protected(tmp_path, write):
    source = write("in.csv", "a,b\n1,2\n")
    out = write("p.toml", "keep me")
    refused = init(str(source), "--output", str(out))
    assert refused.code == 2 and "already exists" in refused.err
    assert out.read_text(encoding="utf-8") == "keep me"
    assert init(str(source), "--output", str(out), "--overwrite").code == 0
    assert load_profile(out).columns[0].name == "a"
    digest = sha256(source)
    onto_input = init(str(source), "--output", str(source), "--overwrite")
    assert onto_input.code == 2 and "input CSV" in onto_input.err
    assert sha256(source) == digest


@pytest.mark.parametrize(
    "extra, message",
    [
        (["--decimal", "nope"], "'nope' is not a column of this file"),
        (["--normalize", "a"], "cannot normalize column 'a'"),
        (["--deduplicate", "keys"], "requires at least one key"),
        (["--date-format", "dd/mm/yyyy"], "--date-format"),
        (["--decimal", "a", "--date", "a"], "both --decimal and --date"),
        (["--encoding", "rot_13"], "not a text encoding"),
    ],
)
def test_invalid_configuration_writes_nothing(tmp_path, write, extra, message):
    source = write("in.csv", "a,b\n1,2\n")
    out = tmp_path / "p.toml"
    result = init(str(source), "--output", str(out), *extra)
    assert result.code == 2 and message in result.err, result.err
    assert "Traceback" not in result.err and not out.exists()


def test_unusable_headers_are_refused_with_the_reason(tmp_path, write):
    out = tmp_path / "p.toml"
    wrong = init(str(FIXABLE), "--output", str(out))  # the file uses ';'
    assert wrong.code == 2 and "--delimiter" in wrong.err and "';'" in wrong.err
    duplicate = init(str(write("d.csv", "a,a\n1,2\n")), "--output", str(out))
    assert duplicate.code == 2 and "duplicate_header" in duplicate.err
    empty = init(str(write("e.csv", b"")), "--output", str(out))
    assert empty.code == 2 and "no header row" in empty.err
    missing = init(str(tmp_path / "none.csv"), "--output", str(out))
    assert missing.code == 2 and "input file not found" in missing.err
    undecodable = init(str(write("u.csv", b"\xff\xfe\n1\n")), "--output", str(out))
    assert undecodable.code == 2 and "decode_error" in undecodable.err
    assert not out.exists()


def test_guided_answers_produce_the_same_profile(tmp_path, answers):
    out = tmp_path / "p.toml"
    answers(
        "2",  # delimiter: semicolon
        "",  # encoding: utf-8
        "3",  # decimal columns
        "1",  # number format: id
        "date",  # date columns, by name
        "DD/MM/YYYY",
        "1-4",  # required
        "1",  # key 1
        "",  # no more keys
        "2,3,4",  # trim
        "all",  # normalize every decimal/date column
        "3",  # output numbers: canonical
        "YYYY-MM-DD",  # output dates
        "1",  # deduplicate: off
        "y",
    )
    result = init(str(FIXABLE), "--output", str(out), "--interactive")
    assert result.code == 0, result.err
    made = resolve_settings(load_profile(out))
    example = resolve_settings(load_profile(EXAMPLES / "profiles" / "transactions-id.toml"))
    assert (made.source, made.output) == (example.source, example.output)
    assert made.columns[:4] == example.columns and made.columns[4].type == "text"
    assert (made.duplicate_keys, made.trim, made.normalize, made.deduplicate) == (
        example.duplicate_keys,
        example.trim,
        example.normalize,
        example.deduplicate,
    )
    assert "1. transaction_id" in result.err  # questions go to stderr, stdout stays short


def test_guided_mode_reprompts_after_an_invalid_answer(tmp_path, answers, write):
    source = write("in.csv", "a,b\n1,2\n")
    out = tmp_path / "p.toml"
    answers("", "", "9", "x-y", "2", "7", "2", "", "", "", "", "", "", "y")
    result = init(str(source), "--output", str(out), "--interactive")
    assert result.code == 0, result.err
    assert result.err.count("Please answer") == 3
    profile = load_profile(out)
    assert [(c.name, c.type) for c in profile.columns] == [("a", "text"), ("b", "decimal")]
    assert profile.source_number_format == "us"


@pytest.mark.parametrize(
    "given",
    [
        ("", "", "q"),  # explicit quit
        ("", ""),  # input ends early (EOF)
        ("", "", "", "", "", "", "", "", "n"),  # declines the final confirmation
    ],
)
def test_guided_mode_can_be_cancelled_without_writing(tmp_path, answers, write, given):
    source = write("in.csv", "a,b\n1,2\n")
    out = tmp_path / "p.toml"
    answers(*given)
    result = init(str(source), "--output", str(out), "--interactive")
    assert result.code == 130 and "cancelled; nothing was written" in result.err
    assert not out.exists() and list(tmp_path.iterdir()) == [source]


def test_help_lists_the_new_command():
    assert "profile" in run_cli("--help").out
    text = run_cli("profile", "init", "--help").out
    assert "--interactive" in text and "never" in text


MIXED = "id;amount;usd;day;us_day\n1;1.250,50;1,250.50;31/12/2026;12/31/2026\n"


def test_per_column_formats_are_written_and_used(tmp_path, write, no_stdin):
    source = write("mixed.csv", MIXED)
    out = tmp_path / "p.toml"
    result = init(
        str(source), "--delimiter", ";", "--output", str(out),
        "--decimal", "amount", "--decimal", "usd", "--date", "day", "--date", "us_day",
        "--number-format", "id", "--date-format", "DD/MM/YYYY",
        "--column-number-format", "usd=us", "--column-date-format", "us_day=MM/DD/YYYY",
    )  # fmt: skip
    assert result.code == 0, result.err
    columns = {c.name: c for c in load_profile(out).columns}
    assert (columns["usd"].number_format, columns["amount"].number_format) == ("us", None)
    assert (columns["us_day"].date_format, columns["day"].date_format) == ("MM/DD/YYYY", None)
    assert check_file(source, load_profile(out)).exit_code == 0


def test_column_names_may_contain_an_equals_sign(tmp_path, write, no_stdin):
    source = write("eq.csv", 'id,a=b\n1,"1,5"\n')
    out = tmp_path / "p.toml"
    result = init(
        str(source), "--output", str(out), "--decimal", "a=b",
        "--column-number-format", "a=b=id",
    )  # fmt: skip
    assert result.code == 0, result.err
    assert {c.name: c.number_format for c in load_profile(out).columns}["a=b"] == "id"


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (["--column-number-format", "usd=us"], "--decimal usd"),
        (["--decimal", "usd", "--column-date-format", "usd=MM/DD/YYYY"], "--date usd"),
        (["--column-number-format", "nope=us"], "not a column of this file"),
        (["--decimal", "usd", "--column-number-format", "usd=xx"], "'xx'"),
        (["--date", "day", "--column-date-format", "day=YYYY-MM"], "YYYY-MM"),
        (
            [
                "--decimal",
                "usd",
                "--column-number-format",
                "usd=us",
                "--column-number-format",
                "usd=id",
            ],
            "more than once",
        ),
        (["--column-number-format", "usd"], "COLUMN=FORMAT"),
    ],
)
def test_per_column_format_mistakes_are_refused_before_writing(
    tmp_path, write, no_stdin, options, message
):
    out = tmp_path / "p.toml"
    result = init(
        str(write("mixed.csv", MIXED)), "--delimiter", ";", "--output", str(out), *options
    )
    assert result.code == 2 and message in result.err, result.err
    assert not out.exists()
