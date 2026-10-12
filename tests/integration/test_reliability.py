"""Reliability regressions (RF-RI): decode-error locations, partial-scan counts, per-read
field limits, and the reason given when an export is refused."""

import csv
import threading
from pathlib import Path

import pytest

from csv_tidy import InputError, OutputError, check_file, clean_file, export_clean
from csv_tidy.reader import read_csv


def read(path, delimiter=",", encoding="utf-8", max_field_chars=131072):
    return read_csv(path, delimiter, encoding, max_field_chars)


# --------------------------------------------------------------------------- RF / RG


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_rf_decode_error_line_is_accurate_for_every_newline(write, newline):
    data = newline.join([b"a,b", b"1,ok", b"2,caf\xe9", b"3,x"]) + newline
    table = read(write("d.csv", data))
    assert table.fatal.code == "decode_error"
    assert table.fatal.line == 3
    assert "near line 3" in table.fatal.message


def test_rf_decode_error_line_counts_lines_inside_quoted_fields(write):
    table = read(write("q.csv", b'a,b\r1,"x\ry"\r2,\xff\r'))
    assert table.fatal.line == 4
    assert [(r.index, r.line_start, r.line_end) for r in table.records] == [(1, 2, 3)]


def test_rf_decode_error_line_for_a_multibyte_encoding(write):
    good = "a,b\r\n1,ok\r\n2,".encode("utf-16-le")
    table = read(
        write("u.csv", good + b"\x00\xd8\x00\x00" + "\r\n".encode("utf-16-le")), ",", "utf-16-le"
    )
    assert table.fatal.code == "decode_error" and table.fatal.line == 3


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_rg_partial_scan_counts_what_was_read_before_a_decode_error(write, newline):
    data = newline.join([b"a,b", b"1,ok", b"", b"2,ok", b"3,caf\xe9", b"4,x"]) + newline
    table = read(write("d.csv", data))
    assert not table.complete
    assert table.header == ("a", "b")
    assert [r.fields for r in table.records] == [("1", "ok"), ("2", "ok")]
    assert table.blank_lines == [3]
    assert table.physical_lines == 4


def test_rg_partial_scan_counts_in_a_file_larger_than_one_read_buffer(write):
    lines = [b"id,name"] + [b"%d,row" % i for i in range(1, 5001)] + [b"5001,\xff", b"5002,x"]
    path = write("big.csv", b"\n".join(lines) + b"\n")
    result = check_file(path)
    assert result.exit_code == 2 and not result.scan.complete
    assert result.scan.data_records == 5000 and result.scan.physical_lines == 5001
    assert result.scan.fatal.line == 5002


def test_rg_earlier_malformed_quoting_wins_over_a_later_decode_error(write):
    table = read(write("m.csv", b'a,b\n1,"bad"x\n2,ok\n3,\xff\n'))
    assert table.fatal.code == "malformed_csv" and table.fatal.line == 2
    assert table.records == []


def test_rg_decode_error_inside_an_open_quoted_field_is_a_decode_error(write):
    table = read(write("o.csv", b'a,b\n1,ok\n2,"open\nstill \xff open"\n'))
    assert table.fatal.code == "decode_error" and table.fatal.line == 4
    assert [r.index for r in table.records] == [1]


# --------------------------------------------------------------------------- RH


class _Gate:
    """Pause a read after the header line so that two reads overlap deterministically."""

    def __init__(self, handle, reached, resume):
        self._handle, self._reached, self._resume = handle, reached, resume

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._handle.close()

    def __iter__(self):
        lines = iter(self._handle)
        yield next(lines)
        self._reached.set()
        assert self._resume.wait(10), "the test did not resume this read"
        yield from lines


@pytest.fixture
def gated(monkeypatch):
    """gated(path) -> (reached, resume): text reads of ``path`` pause after the header."""
    gates = {}
    real_open = Path.open

    def fake_open(self, mode="r", *args, **kwargs):
        handle = real_open(self, mode, *args, **kwargs)
        if "b" not in mode and self in gates:
            return _Gate(handle, *gates[self])
        return handle

    monkeypatch.setattr(Path, "open", fake_open)

    def gate(path):
        gates[Path(path)] = (threading.Event(), threading.Event())
        return gates[Path(path)]

    return gate


def _start(path, limit, results, key):
    def run():
        results[key] = read(path, max_field_chars=limit)

    thread = threading.Thread(target=run)
    thread.start()
    return thread


@pytest.mark.parametrize("first, second", [(10, 100), (100, 10)])
def test_rh_overlapping_reads_each_keep_their_own_field_limit(write, gated, first, second):
    original = csv.field_size_limit()
    path_a = write("a.csv", "v\n" + "x" * 50 + "\n")
    path_b = write("b.csv", "v\n" + "y" * 50 + "\n")
    reached_a, resume_a = gated(path_a)
    reached_b, resume_b = gated(path_b)
    results = {}
    thread_a = _start(path_a, first, results, first)
    assert reached_a.wait(10)
    thread_b = _start(path_b, second, results, second)
    assert reached_b.wait(10)
    resume_a.set()
    thread_a.join(10)
    resume_b.set()
    thread_b.join(10)

    assert results[10].fatal is not None and results[10].fatal.code == "field_too_large"
    assert "10 characters" in results[10].fatal.message
    assert results[100].complete and len(results[100].records[0].fields[0]) == 50
    assert csv.field_size_limit() == original


def test_rh_field_limit_boundary_is_unchanged(write):
    path = write("edge.csv", 'v,w\n"' + "x" * 10 + '",ok\n')
    assert read(path, max_field_chars=10).complete
    table = read(path, max_field_chars=9)
    assert table.fatal.code == "field_too_large" and table.fatal.line == 2
    assert table.records == []


def test_rh_global_field_limit_is_restored_after_failures(write, monkeypatch, tmp_path):
    original = csv.field_size_limit()
    with pytest.raises(InputError):
        read(tmp_path / "missing.csv", max_field_chars=7)
    assert read(write("bad.csv", b"a\n\xff\n"), max_field_chars=7).fatal.code == "decode_error"
    assert read(write("big.csv", "a\n" + "x" * 50 + "\n"), max_field_chars=7).fatal is not None

    path = write("io.csv", "a\n1\n")
    real_open = Path.open

    def failing_open(self, mode="r", *args, **kwargs):
        if self == path and "b" not in mode:
            raise RuntimeError("unexpected failure while reading")
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing_open)
    with pytest.raises(RuntimeError):
        read(path, max_field_chars=7)
    assert csv.field_size_limit() == original


# --------------------------------------------------------------------------- RI


def test_ri_export_of_an_incomplete_scan_explains_the_real_reason(write, tmp_path):
    result = clean_file(write("bad.csv", b"a,b\n1,2\n3,\xff\n"))
    assert not result.export_ready and result.output_errors == 0
    with pytest.raises(OutputError) as excinfo:
        export_clean(result, tmp_path / "out.csv")
    message = str(excinfo.value)
    assert "0 output error" not in message
    assert "scan is incomplete" in message and "decode_error" in message and "line 3" in message
    assert "run" in message  # tells the user what to do next
    assert result.export_blocked_reason == message.removeprefix("export blocked: ")
    assert not (tmp_path / "out.csv").exists()


def test_ri_export_of_an_empty_file_explains_the_missing_header(write, tmp_path):
    result = clean_file(write("empty.csv", b""))
    with pytest.raises(OutputError, match="no header row"):
        export_clean(result, tmp_path / "out.csv")


def test_ri_export_with_remaining_errors_keeps_its_message(write, tmp_path):
    profile = write("p.toml", 'schema_version = 1\n[columns.v]\ntype = "decimal"\n')
    result = clean_file(write("v.csv", "v\nabc\n"), profile)
    with pytest.raises(OutputError, match=r"1 output error\(s\) remain"):
        export_clean(result, tmp_path / "out.csv")
    assert clean_file(write("ok.csv", "v\n1\n"), profile).export_blocked_reason is None
