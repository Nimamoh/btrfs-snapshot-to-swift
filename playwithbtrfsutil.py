#!/usr/bin/env python3

import logging
import os
import sys

import btrfs
import argparse

import storage

log = logging.getLogger(__name__)


def main(path_):

    ro_snapshots = [x for x in btrfs.find_ro_snapshots_of(path_)]

    if not ro_snapshots:
        log.info(f"No readonly snapshots exists for {path_}")
        sys.exit()

    ro_snapshots_str = str.join("\n", [x.rel_path for x in ro_snapshots])
    log.info(f"{ro_snapshots_str}")
    ro_snapshots = storage.with_archived_information(ro_snapshots)
    ro_snapshots_str = str.join("\n", [x.rel_path for x in ro_snapshots])
    log.info(f"{ro_snapshots_str}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="List snapshots of subvolume")
    parser.add_argument("path", type=str, help="Path of subvolume")
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
    if args.verbose:
        level = logging.DEBUG

    logging.basicConfig(format="%(message)s", level=level)

    path = os.path.abspath(args.path)
    log.debug(f"path: {path}")

    main(path)
