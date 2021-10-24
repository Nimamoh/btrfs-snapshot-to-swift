"""
Module related to business logic.
"""

from typing import Optional, Sequence, Union
from btrfs import Snapshot, SnapshotsDifference
from storage import compute_storage_filename

import os
import logging

_log = logging.getLogger(__name__)


class UnexpectedSnapshotStorageLayout(Exception):
    """Raised when local snapshots and distant stored snapshots differs too much to be reliable"""

    pass


def unequal_snapshots_ex(s1, s2) -> UnexpectedSnapshotStorageLayout:
    raise UnexpectedSnapshotStorageLayout(f"{s1} should equals {s2}")


ContentToUpload = Union[Snapshot, SnapshotsDifference]


def compute_snapshot_to_upload(
    snapshots: Sequence[Snapshot], archived_snapshots: Sequence[Snapshot]
) -> Optional[ContentToUpload]:
    """
    Compute snapshots to save and upload,

    Returns:
      ContentToUpload
    Raises:
      UnexpectedSnapshotStorageLayout: If stored snapshot is not
         consistent with local ones.
      ValueError: If snapshots contains duplicates, none...
    """

    def sane_check(snapshots):
        if len(snapshots) != len(set(snapshots)):
            raise ValueError("We shouldn't have duplicate snapshots")
        if None in snapshots:
            raise ValueError("snapshots should not contains None values")

    sane_check(snapshots)
    sane_check(archived_snapshots)

    if len(snapshots) == 0:
        return None
    if len(archived_snapshots) == 0:
        return snapshots[0]

    corresponding_archives = tuple(
        archived_snapshots[i] if i < len(archived_snapshots) else None
        for i in range(len(snapshots))
    )
    assert len(snapshots) == len(corresponding_archives)

    previous = None
    parent = archived_snapshots[0]
    current = None
    z = zip(snapshots, corresponding_archives)
    for s, a in z:
        if previous == s:
            raise ValueError(f"Should not have duplicate in snapshots")
        previous = s
        if a is not None and s != a:
            raise unequal_snapshots_ex(s, a)
        if a is not None:
            parent = a
        if a is None:
            current = s
            break

    if current is None:
        return None
    else:
        return SnapshotsDifference(parent=parent, snapshot=current)


def prepare_content_to_upload_to_file(to_upload: ContentToUpload, basedir: str):
    """Prepare the content to upload to a local file"""
    filename = compute_storage_filename(to_upload)
    filepath = os.path.join(basedir, filename)
    _log.info(f"Preparing {to_upload} into {filepath}")
    _log.warning("Not implemented yet")
