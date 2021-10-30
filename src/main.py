#!/usr/bin/env python3

import logging
import logging.handlers
from typing import Sequence, TextIO
import coloredlogs
import os
import stat
import sys
import tempfile
import time

import btrfs
import argparse


from exceptions import FileIsTooLarge
from humanize import naturalsize
from humanize import precisedelta
from humanfriendly import parse_size
import pyinputplus as pyin

from contextlib import suppress
from dataclasses import dataclass
from storage import only_stored, upload
from business import (
    UnexpectedSnapshotStorageLayout,
    PrepareContent,
    compute_snapshot_to_upload,
    ContentToUpload,
)

from ansi.print_lines import print_lines as ansi_print_lines
from ansi import colors


_log = logging.getLogger(__name__)
_SYSLOG_SOCKET = "/dev/log"


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
    upload_size_limit: int

    def supports_fancy_output(self) -> bool:
        """Does the script execution context allows for fancy ansi escape code"""
        return self.is_interactive and not self.use_syslog


def _print_line(lines: Sequence[str], ctx: Ctx):
    """Wraps ansi.print_lines with setup specific to the script execution"""
    append_only = not ctx.supports_fancy_output() or ctx.verbose
    return ansi_print_lines(
        lines=lines,
        append_only=append_only,
        file=sys.stderr,
        printfn=lambda line, file: _log.info(line),
    )


def _in_green(s: str, ctx: Ctx):
    if not ctx.supports_fancy_output():
        return s
    return colors.in_green(s)


def _in_red(s: str, ctx: Ctx):
    if not ctx.supports_fancy_output():
        return s
    return colors.in_red(s)


def _look_for_archived_snapshots(ro_snapshots, ctx: Ctx):
    """Look for archived snapshots in storage"""
    lines = [s.rel_path for s in ro_snapshots]
    lines += [f"Requesting Web Archive... ⏳"]
    archived_snapshots = []

    with _print_line(lines, ctx) as printer:

        archived_snapshots = only_stored(ro_snapshots, ctx.container_name)

        in_cloud_str = _in_green("in ☁️", ctx)
        not_in_cloud_str = _in_red("not in ☁️", ctx)
        lines = [
            f"{s.rel_path}... {in_cloud_str if s in archived_snapshots else not_in_cloud_str}"
            for s in ro_snapshots
        ]
        printer.reprint(lines)

    return archived_snapshots


def _prepare_snapshot_to_upload(to_upload, ctx: Ctx):
    """Prepare snapshot to upload in a local file"""
    start = time.time()

    preparator = PrepareContent(to_upload, ctx.temp_dir_name, ctx.age_recipient)
    filepath = preparator.target_path()

    with _print_line(["Initializing preparation ⏳"], ctx) as printer:
        for progress_line in preparator.prepare():
            printer.reprint([progress_line])

        elapsed = precisedelta(time.time() - start)
        size = naturalsize(os.path.getsize(filepath))
        printer.reprint([f"Preparation is {size}, took {elapsed}. Ready to upload 💪"])

    _log.debug(f"Preparation fullpath: {filepath}")
    return filepath


def _ask_yes_no_question(question: str, ctx: Ctx, default: bool = False):
    """
    Prompt a yes/no question to stderr and read/parse user response.
    If script is non-interactive, then it prompt the question
    with the default answer and proceed without user input
    """
    default_str = "yes" if default else "no"
    suffix = "[Y/n]" if default else "[y/N]"

    prompt_str = f"{question} {suffix} "
    answer = default_str
    if ctx.is_interactive:
        print(prompt_str, end="", file=sys.stderr)
        answer = pyin.inputYesNo(blank=True, default=default_str)
    else:
        print(f"{prompt_str} {default_str}", file=sys.stderr)

    answer = answer or default_str

    return answer == "yes"


def _ask_preparing(to_upload: ContentToUpload, ctx: Ctx):
    return _ask_yes_no_question(f"Prepare {str(to_upload)}?", ctx=ctx, default=True)


def _ask_uploading(to_upload: ContentToUpload, filepath: str, ctx: Ctx) -> bool:
    size = naturalsize(os.path.getsize(filepath))
    return _ask_yes_no_question(
        f"Upload backup of {str(to_upload)} ({size}) to container '{ctx.container_name}'?",
        ctx=ctx,
        default=True,
    )


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
    with suppress(BaseException):  # On purpose.
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


def process(args):

    with tempfile.TemporaryDirectory(dir=args.work_dir) as tmpdirname:

        ctx = Ctx(
            path=os.path.abspath(args.path),
            verbose=args.verbose,
            container_name=args.container_name,
            temp_dir_name=tmpdirname,
            age_recipient=args.age_recipient,
            use_syslog=args.syslog,
            is_interactive=(sys.stdin.isatty() and sys.stderr.isatty()),
            dry_run=args.dry_run,
            upload_size_limit=args.upload_size_limit,
        )
        _configure_logging(ctx)

        if ctx.dry_run:
            _log.info("💧 Dry run, nothing will be uploaded 💧")

        if not ctx.age_recipient:
            _log.warning(
                " ⚠ Age recipient is not set. Snapshot will not be encrypted before sending. ⚠ "
            )

        if not ctx.is_interactive:
            _log.debug("Non-interactive mode")

        _log.debug(f"Using storage container name {ctx.container_name}")
        _log.debug(f"path: {ctx.path}")
        _log.debug(f"Using working directory {ctx.temp_dir_name}")

        snapshots = [x for x in btrfs.find_ro_snapshots_of(ctx.path)]

        if not snapshots:
            _log.info(f"No readonly snapshots exists for {ctx.path}")
            return

        archived_snapshots = _look_for_archived_snapshots(snapshots, ctx)
        to_upload = compute_snapshot_to_upload(snapshots, archived_snapshots)
        if to_upload is None:
            _log.info("Everything is already up to date.")
            return

        consent = _ask_preparing(to_upload, ctx=ctx)
        if not consent:
            _log.info("You refused, bybye")
            return

        filepath = _prepare_snapshot_to_upload(to_upload, ctx)
        filesize = os.path.getsize(filepath)

        if filesize > ctx.upload_size_limit:
            limit = naturalsize(ctx.upload_size_limit)
            size = naturalsize(filesize)
            raise FileIsTooLarge(f"File is over the limit of {limit} (file is {size}).")

        if ctx.dry_run:
            return

        consent = _ask_uploading(to_upload, filepath, ctx=ctx)
        if not consent:
            _log.info("You refused, bybye")
            return

        humanized_filesize = naturalsize(filesize)
        msg_prefix = f" ⏳ Uploading {to_upload}."
        with _print_line([f"{msg_prefix} This might take awhile."], ctx) as printer:
            for transferred in upload(filepath=filepath, container_name=ctx.container_name):
                printer.reprint(
                    [f"{msg_prefix} {naturalsize(transferred)}/{humanized_filesize}"]
                )
            printer.reprint([f"Uploaded {to_upload} 💪"])


def main():
    parser = argparse.ArgumentParser(description="List snapshots of subvolume")
    parser.add_argument("path", type=str, help="Path of subvolume")
    parser.add_argument(
        "--container-name",
        dest="container_name",
        type=str,
        help="Container name of the web storage",
        required=True,
    )
    parser.add_argument(
        "--work-dir",
        dest="work_dir",
        type=str,
        help="Directory in which the script will store snapshots before sending",
        required=False,
    )
    parser.add_argument(
        "--upload-size-limit",
        help="Prevent uploading file over this size.",
        dest="upload_size_limit",
        type=parse_size,
        default="1EiB",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode. Do everything except upload.",
    )
    parser.add_argument(
        "--age-recipient",
        help="Enable encryption through age, using provided recipient. see https://github.com/FiloSottile/age.",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--syslog",
        dest="syslog",
        type=bool,
        help=f"Log to local syslogd socket '{_SYSLOG_SOCKET}'",
        const=True,
        default=False,
        nargs="?",
    )
    parser.add_argument(
        "-v",
        dest="verbose",
        action="store_true",
        help="Enable debug messages",
    )
    args = parser.parse_args()

    status = 0
    try:
        process(args)
    except FileIsTooLarge as e:
        _log.error(e)
        status = -1
    except UnexpectedSnapshotStorageLayout as e:
        _log.error(
            f"Layout of files is not a subset of local snapshots. Please read the documentation."
        )
        status = -1
    except:
        _log.exception("Oops, an error occured. Here is what went wrong:")
        status = -1

    sys.exit(status)


if __name__ == "__main__":
    main()