"""
Constants for ansi color
"""

from . import _prefix
from . import _reset

black = f"{_prefix}[30m"
red = f"{_prefix}[31m"
green = f"{_prefix}[32m"
yellow = f"{_prefix}[33m"
# 'bright' colors, on 16 bits, append ;1
bright_black = f"{_prefix}[30;1m"
bright_red = f"{_prefix}[31;1m"
bright_green = f"{_prefix}[32;1m"
bright_yellow = f"{_prefix}[33;1m"
reset = _reset

def in_green(s: str):
    """Color input in green"""
    return f'{green}{s}{reset}'

def in_red(s: str):
    """Color input in green"""
    return f'{red}{s}{reset}'

def color256(id: int):
    """Return color ID from 256 color palette"""
    return f"\u001b[38;5;{id}m"