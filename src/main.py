#!/usr/bin/env python3

import logging
import coloredlogs
import os
import sys

import btrfs
import argparse

import pyinputplus as pyin

from storage import only_stored
from business import SnapshotsDifference, compute_snapshot_to_upload, ContentToUpload

from ansi.advanced import print_lines
from ansi import colors

from exceptions import ProgrammingError


_log = logging.getLogger(__name__)


def _look_for_archived_snapshots(ro_snapshots, container_name, verbose):
    """Look for archived snapshots in storage"""
    snapshot_paths = [s.rel_path for s in ro_snapshots]
    archived_snapshots = []
    with print_lines(snapshot_paths, append_only=verbose, printfn=_log.info) as printer:
        snapshot_paths.append(f"Requesting Web Archive... ⏳")
        printer.reprint(snapshot_paths)

        archived_snapshots = only_stored(ro_snapshots, container_name)

        in_cloud_str = f'{colors.in_green("in ☁️")}'
        not_in_cloud_str = f'{colors.in_red("not in ☁️")}'
        snapshot_paths = [
            f"{s.rel_path}... {in_cloud_str if s in archived_snapshots else not_in_cloud_str}"
            for s in ro_snapshots
        ]
        printer.reprint(snapshot_paths)
    return archived_snapshots


def _ask_uploading(to_upload: ContentToUpload):
    """
    Ask user for uploading snapshot
    Args:
      to_send: snapshot to send
    Returns:
      True if user accept, False otherwise
    """
    question = ""
    if to_upload == None:
        return True
    if isinstance(to_upload, btrfs.Snapshot):
        question = f"Uploading whole snapshot {to_upload}? [y/N]"
    elif isinstance(to_upload, SnapshotsDifference):
        question = f"Uploading changes between {to_upload.parent} and {to_upload.snapshot}? [y/N]"
    else:
        raise ProgrammingError

    response = pyin.inputYesNo(prompt=question, blank=True, default="no")
    return response == "yes"


def main(path_, container, verbose):

    snapshots = [x for x in btrfs.find_ro_snapshots_of(path_)]

    if not snapshots:
        _log.info(f"No readonly snapshots exists for {path_}")
        sys.exit()

    archived_snapshots = _look_for_archived_snapshots(snapshots, container, verbose)

    to_upload = compute_snapshot_to_upload(snapshots, archived_snapshots)
    consent = _ask_uploading(to_upload)
    if consent:
        _log.warning("Not implemented yet")
    else:
        _log.info("You refused, bybye")


if __name__ == "__main__":

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

    path = os.path.abspath(args.path)
    _log.debug(f"path: {path}")

    main(path, container=args.container_name, verbose=args.verbose)
