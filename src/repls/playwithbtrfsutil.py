#!/usr/bin/env python3

import logging
import coloredlogs
import os
import sys

import btrfs
import argparse

from storage import compute_storage_filename, only_stored

from ansi.advanced import print_lines
from ansi import colors

log = logging.getLogger(__name__)


def main(path_, container_name, verbose):

    ro_snapshots = [x for x in btrfs.find_ro_snapshots_of(path_)]

    if not ro_snapshots:
        log.info(f"No readonly snapshots exists for {path_}")
        sys.exit()

    snapshot_path_lines = [compute_storage_filename(s) for s in ro_snapshots]
    with print_lines(
        snapshot_path_lines, append_only=verbose, printfn=log.info
    ) as printer:
        snapshot_path_lines.append(f"Requesting Web Archive... ⏳")
        printer.reprint(snapshot_path_lines)

        archived_snapshots = only_stored(ro_snapshots, container_name)

        in_cloud_str = f'{colors.in_green("in ☁️")}'
        not_in_cloud_str = f'{colors.in_red("not in ☁️")}'
        snapshot_path_lines = [
            f"{compute_storage_filename(s)}... {in_cloud_str if s in archived_snapshots else not_in_cloud_str}"
            for s in ro_snapshots
        ]
        printer.reprint(snapshot_path_lines)


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
    log.debug(f"path: {path}")

    main(path, container_name=args.container_name, verbose=args.verbose)
