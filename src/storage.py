"""
storage module is about archive storage routines
"""
import logging
from typing import Union

from swiftclient.service import SwiftService

from btrfs import Snapshot, SnapshotsDifference
from exceptions import ProgrammingError

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


def compute_storage_filename(
    snapshot_or_diff: Union[Snapshot, SnapshotsDifference]
) -> str:
    """
    Compute unique filename of a btrfs snapshot for storage.
    Basically fs_uuid/relpath. Uniquely identifies a btrfs snapshot.
    """
    s = None
    if isinstance(snapshot_or_diff, Snapshot):
        s = snapshot_or_diff
    elif isinstance(snapshot_or_diff, SnapshotsDifference):
        s = snapshot_or_diff.snapshot
    else:
        raise ProgrammingError

    return _sanitize_storage_filename(f"{s.fs_uuid}/{s.rel_path}")


def _sanitize_storage_filename(name: str):
    """
    Sanitize name for it to be a valid unix filename.
    Raises:
      ValueError if we cannot sanitize filename garanteeing collision free
    """
    slash_surrogate='\\x2f'
    if "\x00" in name:
        raise ValueError("Null character is forbidden in unix filename")
    if slash_surrogate in name:
        raise ValueError("We do not support filename with '\\x2f' in it.")
    name = name.replace("/", slash_surrogate)
    return name


def only_stored(ro_snapshots: list[Snapshot], container_name: str) -> list[Snapshot]:
    """
    Args:
      ro_snapshots(list[Snapshot]): snapshots to check against storage

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

    log.debug(f"Found {len(container_item_names)} files.")
    result = [
        s for s in ro_snapshots if compute_storage_filename(s) in container_item_names
    ]
    log.debug(
        f"Filtering... Found {len(result)} files corresponding to actual snapshots."
    )
    return result
