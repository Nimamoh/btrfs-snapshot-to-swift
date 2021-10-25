#!/usr/bin/env python3

import logging
import logging.handlers
import coloredlogs
import os
import stat
import sys
import tempfile

import btrfs
import argparse

import pyinputplus as pyin

from storage import only_stored, upload
from business import (
    SnapshotsDifference,
    UnexpectedSnapshotStorageLayout,
    prepare_content_to_upload_to_file,
    compute_snapshot_to_upload,
    ContentToUpload,
)

from ansi.advanced import print_lines
from ansi import colors

from exceptions import ProgrammingError


_log = logging.getLogger(__name__)
_interactive = sys.stdin.isatty()
_syslog_socket = "/dev/log"


def _look_for_archived_snapshots(ro_snapshots, container_name, verbose):
    """Look for archived snapshots in storage"""
    lines = [s.rel_path for s in ro_snapshots]
    archived_snapshots = []
    with print_lines(lines, append_only=verbose, printfn=_log.info) as printer:
        lines.append(f"Requesting Web Archive... ⏳")
        printer.reprint(lines)

        archived_snapshots = only_stored(ro_snapshots, container_name)

        in_cloud_str = f'{colors.in_green("in ☁️")}'
        not_in_cloud_str = f'{colors.in_red("not in ☁️")}'
        lines = [
            f"{s.rel_path}... {in_cloud_str if s in archived_snapshots else not_in_cloud_str}"
            for s in ro_snapshots
        ]
        printer.reprint(lines)
    return archived_snapshots


def _ask_preparing(to_upload: ContentToUpload):

    if not _interactive:
        return True

    question = ""
    if to_upload == None:
        return True
    if isinstance(to_upload, btrfs.Snapshot):
        question = f"Prepare whole snapshot {to_upload}? [y/N]"
    elif isinstance(to_upload, SnapshotsDifference):
        question = f"Prepare changes between {to_upload.parent} and {to_upload.snapshot}? [y/N] "
    else:
        raise ProgrammingError

    response = pyin.inputYesNo(prompt=question, blank=True, default="no")
    return response == "yes"


def _ask_uploading(filepath: str) -> bool:

    if not _interactive:
        return True

    question = f"Upload file {filepath} of size {os.path.getsize(filepath)}B? [y/N] "
    response = pyin.inputYesNo(prompt=question, blank=True, default="no")
    return response == "yes"


def _ask_press_enter():

    if not _interactive:
        return

    _log.info("Press enter to finish")
    next(sys.stdin)


def _configure_logging(verbose: bool, use_syslog: bool):

    level = logging.INFO if not verbose else logging.DEBUG
    syslog_socket_ok = True
    try:
        stat.S_ISSOCK(os.stat(_syslog_socket).st_mode)
    except:
        syslog_socket_ok = False

    handler = None
    if use_syslog and syslog_socket_ok:
        handler = logging.handlers.SysLogHandler(address=_syslog_socket)
    else:
        format = "%(message)s"
        formatter = coloredlogs.ColoredFormatter(format)
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        handler = stream  # type: ignore

    handler.setLevel(level)  # type: ignore
    logging.root.setLevel(level)
    logging.root.addHandler(handler)  # type: ignore

    # Disabling component which are too verbose
    logging.getLogger("keystoneclient").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)  #
    logging.getLogger("swiftclient").setLevel(logging.WARNING)  #

    if use_syslog and not syslog_socket_ok:
        _log.warning(
            f"Impossible to use syslogd daemon (using '{_syslog_socket} socket'). Falling back to stdout logging."
        )


def process(path_, container, tmpdirname, verbose):

    snapshots = [x for x in btrfs.find_ro_snapshots_of(path_)]

    if not snapshots:
        _log.info(f"No readonly snapshots exists for {path_}")
        return

    archived_snapshots = _look_for_archived_snapshots(snapshots, container, verbose)
    to_upload = compute_snapshot_to_upload(snapshots, archived_snapshots)
    if to_upload is None:
        _log.info("Everything is already up to date.")
        return

    consent = _ask_preparing(to_upload)
    if not consent:
        _log.info("You refused, bybye")
        return

    filepath = prepare_content_to_upload_to_file(to_upload, tmpdirname)

    consent = _ask_uploading(filepath)
    if not consent:
        _log.info("Okay, bybye")
        return

    upload(filepath=filepath, container_name=container)
    _log.info(f"Uploaded {filepath}")


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
        "--syslog",
        dest="syslog",
        type=bool,
        help=f"Log to local syslogd socket '{_syslog_socket}'",
        const=True,
        default=False,
        nargs="?",
    )
    parser.add_argument(
        "-v",
        dest="verbose",
        type=bool,
        help="Enable debug messages",
        const=True,
        default=False,
        nargs="?",
    )
    args = parser.parse_args()

    path = os.path.abspath(args.path)
    verbose = args.verbose
    container_name = args.container_name
    work_dir = args.work_dir
    use_syslog = args.syslog

    _configure_logging(verbose=verbose, use_syslog=use_syslog)

    if not _interactive:
        _log.debug(f"Uninteractive mode")

    _log.debug(f"Using storage container name {container_name}")
    _log.debug(f"path: {path}")

    with tempfile.TemporaryDirectory(dir=work_dir) as tmpdirname:
        _log.debug(f"Using working directory {tmpdirname}")
        process(path, container=container_name, tmpdirname=tmpdirname, verbose=verbose)
        _ask_press_enter()


if __name__ == "__main__":
    status = 0
    try:
        main()
    except UnexpectedSnapshotStorageLayout as e:
        _log.error(
            f"Layout of files is not a subset of local snapshots. Please read the documentation."
        )
        status = -1
    except:
        _log.exception("Oops, an error occured. Here is what went wrong:")
        status = -1

    sys.exit(status)
