#!/usr/bin/env python3

import logging
import logging.handlers
from typing import Sequence
import os
import sys
import tempfile
import time

import btrfs
import argparse

from humanize import naturalsize
from humanize import precisedelta
import pyinputplus as pyin

from storage import only_stored, upload
from business import (
    UnexpectedSnapshotStorageLayout,
    PrepareContent,
    compute_snapshot_to_archive,
    ContentToArchive,
)


from _main_commons import Ctx, print_lines, in_green, in_red, _configure_logging


from _main_commons import _SYSLOG_SOCKET

_log = logging.getLogger(__name__)


def _look_for_archived_snapshots(ro_snapshots, ctx: Ctx) -> Sequence[btrfs.Snapshot]:
    """
    Look for archived snapshots in storage

    Returns:
      sequence of archived snapshots
    """
    lines = [s.rel_path for s in ro_snapshots]
    lines += [f"Requesting Web Archive... ⏳"]
    archived_snapshots: Sequence = []

    with print_lines(lines, ctx) as printer:

        archived_snapshots = only_stored(ro_snapshots, ctx.container_name)

        in_cloud_str = in_green("in ☁️", ctx)
        not_in_cloud_str = in_red("not in ☁️", ctx)
        lines = [
            f"{s.rel_path}... {in_cloud_str if s in archived_snapshots else not_in_cloud_str}"
            for s in ro_snapshots
        ]
        printer.reprint(lines)

    return archived_snapshots


def _prepare_snapshot_to_archive(to_archive, ctx: Ctx) -> str:
    """
    Prepare snapshot to archive in a local file

    Returns:
      fullpath of the file to archive
    """
    start = time.time()

    preparator = PrepareContent(to_archive, ctx.temp_dir_name, ctx.age_recipient)
    filepath = preparator.target_path()

    with print_lines(["Initializing preparation ⏳"], ctx) as printer:
        for progress_line in preparator.prepare():
            if ctx.is_interactive:
                printer.reprint([progress_line])

        elapsed = precisedelta(time.time() - start)
        size = naturalsize(os.path.getsize(filepath))
        printer.reprint([f"Preparation is {size}, took {elapsed}. Ready to upload 💪"])

    _log.debug(f"Preparation fullpath: {filepath}")
    return filepath


def _ask_yes_no_question(question: str, ctx: Ctx, default: bool = False) -> bool:
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


def _ask_preparing(to_archive: ContentToArchive, ctx: Ctx):
    return _ask_yes_no_question(f"Prepare {str(to_archive)}?", ctx=ctx, default=True)


def _ask_archiving(to_archive: ContentToArchive, filepath: str, ctx: Ctx) -> bool:
    size = naturalsize(os.path.getsize(filepath))
    return _ask_yes_no_question(
        f"Upload backup of {str(to_archive)} ({size}) to container '{ctx.container_name}'?",
        ctx=ctx,
        default=True,
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
        content_to_archive_list = [
            x for x in compute_snapshot_to_archive(snapshots, archived_snapshots)
        ]

        if not content_to_archive_list:
            _log.info("Everything is already up to date.")

        for content_to_archive in content_to_archive_list:

            consent = _ask_preparing(content_to_archive, ctx=ctx)
            if not consent:
                _log.info("You refused, bybye")
                return

            filepath = _prepare_snapshot_to_archive(content_to_archive, ctx)
            filesize = os.path.getsize(filepath)

            if ctx.dry_run:
                continue

            consent = _ask_archiving(content_to_archive, filepath, ctx=ctx)
            if not consent:
                _log.info("You refused, bybye")
                return

            humanized_filesize = naturalsize(filesize)
            msg_prefix = f" ⏳ Uploading {content_to_archive}."
            with print_lines([f"{msg_prefix} This might take awhile."], ctx) as printer:
                for transferred in upload(filepath, ctx.container_name):
                    if ctx.is_interactive:
                        msg = f"{msg_prefix}"
                        msg += f" {naturalsize(transferred)}/{humanized_filesize}"
                        printer.reprint([msg])
                printer.reprint([f"Uploaded {content_to_archive} 💪"])


def main():
    parser = argparse.ArgumentParser(description="List snapshots of subvolume")
    parser.add_argument("path", type=str, help="Path of subvolume.")
    parser.add_argument(
        "--container-name",
        dest="container_name",
        type=str,
        help="Container name of your swift service.",
        required=True,
    )
    parser.add_argument(
        "--work-dir",
        dest="work_dir",
        type=str,
        help="Directory in which the script will store snapshots before sending.",
        required=False,
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
        help=f"Log to local syslogd socket '{_SYSLOG_SOCKET}'.",
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
    except KeyboardInterrupt:
        _log.info("You cancelled. Bybye")
        status = -1
    except UnexpectedSnapshotStorageLayout:
        msg = "Layout of files is not a subset of local snapshots. Please read the documentation."
        _log.error(msg)
        status = -1
    except:
        _log.exception("Oops, an error occured. Here is what went wrong:")
        status = -1

    sys.exit(status)


if __name__ == "__main__":
    main()
