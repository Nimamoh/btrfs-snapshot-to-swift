"""
storage module is about archive storage routines
"""
import logging

from swiftclient.service import SwiftService

from btrfs import BtrfsSnapshot

log = logging.getLogger(__name__)


def _compute_common_prefix(str_list: list[str]):
    """Compute common prefix of a list of string"""
    rest = ""
    zipped = zip(*str_list)
    for letters in zipped:
        equals = all(letters[0] == letter for letter in letters)
        if equals:
            rest += letters[0]
        else:
            break
    return rest


def _parse_list_page_gen(list_parts_gen):
    """Parse pages from list request"""
    names = []
    for page in list_parts_gen:

        if not page["success"]:
            raise page["error"]

        for item in page["listing"]:
            names.append(item["name"])

    return names


def compute_storage_filename(snapshot: BtrfsSnapshot) -> str:
    """
    Compute unique filename of a btrfs snapshot for storage.
    Basically fs_uuid/relpath. Uniquely identifies a btrfs snapshot.
    """
    return f"{snapshot.fs_uuid}/{snapshot.rel_path}"


def only_stored(
    ro_snapshots: list[BtrfsSnapshot], container_name: str
) -> list[BtrfsSnapshot]:
    """
    Args:
      ro_snapshots(list[BtrfsSnapshot]): snapshots to check against storage

    Returns:
      Filtered list of btrfs snapshots, conserving only the ones present in storage
    """
    storage_filename_of_snapshots = [compute_storage_filename(s) for s in ro_snapshots]
    prefix = _compute_common_prefix(storage_filename_of_snapshots)
    log.debug(f'Search storage for files with prefix "{prefix}"')

    container_item_names = []
    with SwiftService() as swift:
        list_page_gen = swift.list(container=container_name, options={"prefix": prefix})
        container_item_names = _parse_list_page_gen(list_page_gen)

    log.debug(f'Found {len(container_item_names)} files.')
    result = [
        s for s in ro_snapshots if compute_storage_filename(s) in container_item_names
    ]
    log.debug(f'Filtering... Found {len(result)} files corresponding to actual snapshots.')
    return result
