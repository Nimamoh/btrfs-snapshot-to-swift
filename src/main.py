#!/usr/bin/env python3

import logging
import coloredlogs
import os
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
    question = ""
    if to_upload == None:
        return True
    if isinstance(to_upload, btrfs.Snapshot):
        question = f"Prepare whole snapshot {to_upload}? [y/N]"
    elif isinstance(to_upload, SnapshotsDifference):
        question = f"Prepare changes between {to_upload.parent} and {to_upload.snapshot}? [y/N]"
    else:
        raise ProgrammingError

    response = pyin.inputYesNo(prompt=question, blank=True, default="no")
    return response == "yes"


def _ask_uploading(filepath: str) -> bool:
    question = f"Upload file {filepath} of size {os.path.getsize(filepath)}B? [y/N]"
    response = pyin.inputYesNo(prompt=question, blank=True, default="no")
    return response == "yes"


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
        "-v",
        dest="verbose",
        type=bool,
        help="Enable debug messages",
        const=True,
        default=False,
        nargs="?",
    )
    args = parser.parse_args()

    level = logging.INFO
    format = "%(message)s"

    path = os.path.abspath(args.path)
    verbose = args.verbose
    container_name = args.container_name
    work_dir = args.work_dir

    if args.verbose:
        level = logging.DEBUG
        format = "%(asctime)s - %(name)-12s %(levelname)-8s %(message)s"
    formatter = coloredlogs.ColoredFormatter(format)
    stream = logging.StreamHandler()
    stream.setLevel(level)
    stream.setFormatter(formatter)
    logging.root.setLevel(level)
    logging.root.addHandler(stream)
    logging.getLogger("keystoneclient").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)  #
    logging.getLogger("swiftclient").setLevel(logging.WARNING)  #

    _log.debug(f"Using storage container name {container_name}")
    _log.debug(f"path: {path}")

    with tempfile.TemporaryDirectory(dir=work_dir) as tmpdirname:
        _log.debug(f"Using working directory {tmpdirname}")
        process(path, container=container_name, tmpdirname=tmpdirname, verbose=verbose)

        _log.info("Press enter to finish")
        next(sys.stdin)


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
