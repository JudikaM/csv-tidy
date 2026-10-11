"""AC-01 to AC-05: reading, structure, line tracking, and fatal parsing failures."""

import pytest

from csv_tidy import InputError, check_file
from csv_tidy.reader import read_csv


def read(path, delimiter=",", encoding="utf-8", max_field_chars=131072):
    return read_csv(path, delimiter, encoding, max_field_chars)


@pytest.mark.parametrize("delimiter", [",", ";"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_delimiters_and_line_endings(write, delimiter, newline):
    text = newline.join([f"a{delimiter}b", f"1{delimiter}Zoë 日本", f"3{delimiter}4"]) + newline
    table = read(write("x.csv", text), delimiter)
    assert table.header == ("a", "b")
    assert [r.fields for r in table.records] == [("1", "Zoë 日本"), ("3", "4")]
    assert [(r.index, r.line_start, r.line_end) for r in table.records] == [(1, 2, 2), (2, 3, 3)]
    assert table.complete and not table.bom


def test_utf8_bom_is_detected_and_not_part_of_header(write):
    table = read(write("bom.csv", b"\xef\xbb\xbfid,name\n1,A\n"))
    assert table.bom
    assert table.header == ("id", "name")


def test_explicit_encoding(write):
    table = read(write("latin.csv", "name\nJosé\n", encoding="cp1252"), encoding="cp1252")
    assert table.records[0].fields == ("José",)


def test_quoting_multiline_and_line_ranges(write):
    text = 'id,note\n1,"a, b"\n2,"say ""hi"""\n3,"line one\nline two\nline three"\n4,end\n'
    table = read(write("q.csv", text))
    assert [r.fields for r in table.records] == [
        ("1", "a, b"),
        ("2", 'say "hi"'),
        ("3", "line one\nline two\nline three"),
        ("4", "end"),
    ]
    multiline = table.records[2]
    assert (multiline.index, multiline.line_start, multiline.line_end) == (3, 4, 6)
    assert (table.records[3].line_start, table.records[3].index) == (7, 4)


def test_crlf_inside_quoted_field_is_preserved(write):
    table = read(write("crlf.csv", b'id,note\r\n1,"a\r\nb"\r\n'))
    assert table.records[0].fields == ("1", "a\r\nb")


def test_empty_header_only_and_blank_lines(write):
    assert read(write("empty.csv", b"")).header is None
    header_only = read(write("h.csv", "a,b\n"))
    assert header_only.header == ("a", "b") and header_only.records == []
    blanks = read(write("b.csv", "\na,b\n1,2\n\n3,4\n"))
    assert blanks.blank_lines == [1, 4]
    assert [(r.index, r.line_start) for r in blanks.records] == [(1, 3), (2, 5)]


def test_fields_are_text_and_never_converted(write):
    table = read(write("t.csv", "id,phone,amount\n00123,081234567890,1e5\n"))
    assert table.records[0].fields == ("00123", "081234567890", "1e5")


def test_wrong_field_counts_are_kept_not_dropped(write):
    table = read(write("w.csv", "a,b,c\n1,2\n1,2,3,4\n1,2,3\n"))
    assert [len(r.fields) for r in table.records] == [2, 4, 3]


def test_malformed_quotes_are_fatal_with_partial_scan(write):
    table = read(write("m.csv", 'a,b\n1,2\n3,"bad"x\n5,6\n'))
    assert not table.complete
    assert table.fatal.code == "malformed_csv"
    assert table.fatal.line == 3
    assert len(table.records) == 1


def test_unterminated_quote_is_fatal(write):
    table = read(write("u.csv", 'a,b\n1,"never closed\n2,3\n'))
    assert table.fatal is not None and table.fatal.code == "malformed_csv"


def test_strict_decoding_reports_line_and_does_not_replace(write):
    path = write("d.csv", b"a,b\n1,ok\n2,caf\xe9\n3,x\n")
    table = read(path)
    assert table.fatal.code == "decode_error"
    assert table.fatal.line == 3
    result = check_file(path)
    assert result.exit_code == 2 and not result.scan.complete
    assert any(i.severity == "fatal" for i in result.issues)


def test_field_size_limit(write):
    path = write("big.csv", "a\n" + "x" * 50 + "\n")
    table = read(path, max_field_chars=10)
    assert table.fatal.code == "field_too_large"
    assert "10 characters" in table.fatal.message
    assert read(path, max_field_chars=50).complete


def test_missing_input_and_directory(tmp_path):
    with pytest.raises(InputError):
        read(tmp_path / "missing.csv")
    with pytest.raises(InputError):
        read(tmp_path)
