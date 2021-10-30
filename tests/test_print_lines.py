import pytest
import tempfile
import sys
from pytest import CaptureFixture
from ansi.print_lines import print_lines


def test_lines_printer_internal_seq_is_immutable():
    """Sane checking that internal representation cannot be mutated."""
    with print_lines() as printer:
        seq = printer._internal_seq()

        with pytest.raises(TypeError, match=r".*item assignment.*"):
            seq[0] = "hello"


def test_lines_printer_split_on_newlines():
    """Checks that internal representation does not keep newlines"""
    with print_lines(["a\nb", "\n"]) as printer:
        internal_seq = printer._internal_seq()
        assert len(internal_seq) == 3
        assert internal_seq[0] == "a"
        assert internal_seq[1] == "b"
        assert internal_seq[2] == ""


def test_lines_printer_outputs_with_line_end(capsys: CaptureFixture[str]):
    """Check that line_printer outputs passed lines"""
    lines = ["a\nb", "c", "d"]
    with print_lines(lines) as _:
        pass
    captured = capsys.readouterr()
    assert captured.out == "a\nb\nc\nd\n"


def test_lines_printer_append_only(capsys: CaptureFixture[str]):
    with print_lines(["one", "two", "three"], append_only=True) as printer:
        printer.reprint(["eno", "owt", "eerht"])

    captured = capsys.readouterr()
    assert captured.out == "one\ntwo\nthree\neno\nowt\neerht\n"


def test_lines_printer_stdout_not_a_tty():
    """Check that when stdout is not a tty the appendonly mode defaults to ON"""
    orig = sys.stdout
    lines = []
    with tempfile.TemporaryFile(mode="w+") as file:
        sys.stdout = file  # type: ignore
        with print_lines(["one", "two"]) as printer:
            printer.reprint(["two", "three"])
        sys.stdout = orig

        file.seek(0)
        lines = file.readlines()

    assert lines == [
        "one\n",
        "two\n",
        "two\n",
        "three\n",
    ]


def test_lines_printer():
    """More advanced example of lines_printer"""

    def loading_bar(n):
        width = 10
        acc = "["
        for _ in range(n):
            acc += "="
        for _ in range(width - n):
            acc += " "
        acc += "]"
        return acc

    def loading_bars(n, j):
        return [loading_bar(n) for _ in range(j)]

    print()  # empty line
    with print_lines(loading_bars(0, 5)) as printer:
        for i in range(10):
            printer.reprint(loading_bars(i + 1, 5))
            # time.sleep(0.1) # enable to see the progress


if "__main__" == __name__:
    pytest.main(["-s", "-vv", __file__])
