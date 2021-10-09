"""
storage module is about archive storage routines
"""
import logging
from dataclasses import dataclass

from swiftclient.service import SwiftService

from btrfs import BtrfsSnapshot


@dataclass
class BtrfsSnapshotWithArchivedInformation(BtrfsSnapshot):
    is_archived: bool


__CONTAINER_NAME = "helios"

log = logging.getLogger(__name__)


def _compute_common_prefix(str_list: list[str]):
    rest = ""
    zipped = zip(*str_list)
    for letters in zipped:
        equals = all(letters[0] == letter for letter in letters)
        if equals:
            rest += letters[0]
        else:
            break
    return rest


def _parse_list_parts_gen(list_parts_gen):
    names = []
    for page in list_parts_gen:

        if not page["success"]:
            raise page["error"]

        for item in page["listing"]:
            names.append(item["name"])

    return names


def with_archived_information(
    ro_snapshots: list[BtrfsSnapshot],
) -> list[BtrfsSnapshotWithArchivedInformation]:
    """
    Accept a list of path of RO snapshot
    and return a list of tuple (path, is_saved)
    where is_saved is true if the RO snapshot if found in object storage
    """
    rel_paths = [x.rel_path for x in ro_snapshots]
    prefix = _compute_common_prefix(rel_paths)
    log.debug(f'Search storage for files with prefix "{prefix}"')

    container_item_names = []
    with SwiftService() as swift:
        list_parts_gen = swift.list(
            container=__CONTAINER_NAME, options={"prefix": prefix}
        )
        container_item_names = _parse_list_parts_gen(list_parts_gen)

    result = [BtrfsSnapshotWithArchivedInformation(
                rel_path=x.rel_path,
                abs_path=x.abs_path,
                otime=x.otime,
                is_archived=bool(x.rel_path in container_item_names),
            ) for x in ro_snapshots]
    return result
