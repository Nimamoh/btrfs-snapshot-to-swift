"""
Manipulate entire line through ansi escape code
"""

from . import _prefix, _print
import enum
import sys

@enum.unique
class ClearLineType(enum.Enum):
    RIGHT = 0
    LEFT = 1
    ENTIRE = 2


def clearline(type: ClearLineType = ClearLineType.ENTIRE, file = None):
    file = file or sys.stdout
    _print(f"{_prefix}[{type.value}K", file=file)