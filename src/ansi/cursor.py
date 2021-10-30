"""
Manipulate terminal cursor through ansi escape code
"""

from . import _prefix
from . import _print

import sys

def up(n=1, file=None):
    """Move cursor n upward"""
    file = file or sys.stdout
    _move_cursor("A", n, file=file)


def down(n=1, file=None):
    """Move cursor n downward"""
    file = file or sys.stdout
    _move_cursor("B", n, file=file)


def right(n=1, file=None):
    """Move cursor n right"""
    file = file or sys.stdout
    _move_cursor("C", n, file=file)


def left(n=1, file=None):
    """Move cursor n left"""
    file = file or sys.stdout
    _move_cursor("D", n, file=file)


def savepos(file=None):
    file = file or sys.stdout
    _print(f"{_prefix}[s", file=file)


def loadpos(file=None):
    file = file or sys.stdout
    _print(f"{_prefix}[u", file=file)


def lineup(n=0, file=None):
    file = file or sys.stdout
    _print(f"{_prefix}[{n}F", file=file)


def linedown(n=0, file=None):
    file = file or sys.stdout
    _print(f"{_prefix}[{n}E", file=file)


def _move_cursor(dir: str, n=1, file=None):
    file = file or sys.stdout
    _print(f"{_prefix}[{n}{dir}", file=file)