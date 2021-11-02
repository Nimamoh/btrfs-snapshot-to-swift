"""
Contains secondary function for the main command line.
"""

import sys
import stat
import os
import logging
import logging.handlers
from dataclasses import dataclass
from typing import Sequence, TextIO
from contextlib import suppress

from ansi.print_lines import print_lines as ansi_print_lines
from ansi import colors

import coloredlogs

_SYSLOG_SOCKET = "/dev/log"
_log = logging.getLogger(__name__)


@dataclass
class Ctx:
    """Context of script execution"""

    path: str
    verbose: bool
    container_name: str
    temp_dir_name: str
    age_recipient: str
    use_syslog: bool
    is_interactive: bool
    dry_run: bool

    def supports_fancy_output(self) -> bool:
        """Does the script execution context allows for fancy ansi escape code"""
        return self.is_interactive and not self.use_syslog


def print_lines(lines: Sequence[str], ctx: Ctx):
    """Wraps ansi.print_lines with setup specific to the script execution"""
    append_only = not ctx.supports_fancy_output() or ctx.verbose
    return ansi_print_lines(
        lines=lines,
        append_only=append_only,
        file=sys.stderr,
        printfn=lambda line, file: _log.info(line),
    )


def in_green(s: str, ctx: Ctx):
    if not ctx.supports_fancy_output():
        return s
    return colors.in_green(s)


def in_red(s: str, ctx: Ctx):
    if not ctx.supports_fancy_output():
        return s
    return colors.in_red(s)


def _configure_logging(context: Ctx):
    verbose = context.verbose
    use_syslog = context.use_syslog

    def _formatter(stream: TextIO):
        return (
            coloredlogs.ColoredFormatter("%(message)s")
            if stream.isatty()
            else logging.Formatter("%(levelname)s - %(message)s")
        )

    level = logging.DEBUG if verbose else logging.INFO
    syslog_socket_ok = False
    with suppress(BaseException):
        syslog_socket_ok = stat.S_ISSOCK(os.stat(_SYSLOG_SOCKET).st_mode)

    handler = None
    if use_syslog and syslog_socket_ok:
        handler = logging.handlers.SysLogHandler(address=_SYSLOG_SOCKET)
    else:
        stream_handler = logging.StreamHandler()
        formatter = _formatter(stream_handler.stream)  # type: ignore
        stream_handler.setFormatter(formatter)
        handler = stream_handler  # type: ignore

    handler.setLevel(level)  # type: ignore
    logging.root.setLevel(level)
    logging.root.addHandler(handler)  # type: ignore

    # Disabling component which are too verbose
    logging.getLogger("keystoneclient").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)  #
    logging.getLogger("swiftclient").setLevel(logging.WARNING)  #

    if use_syslog and not syslog_socket_ok:
        _log.warning(
            f"Impossible to use syslogd daemon (using '{_SYSLOG_SOCKET} socket'). Falling back to stdout logging."
        )
