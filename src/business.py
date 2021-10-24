"""
Module related to business logic.
"""

from typing import Sequence, Union
from btrfs import Snapshot

import dataclasses


class UnexpectedSnapshotStorageLayout(Exception):
    """Raised when local snapshots and distant stored snapshots differs too much to be reliable"""

    pass


def unequal_snapshots_ex(s1, s2) -> UnexpectedSnapshotStorageLayout:
    raise UnexpectedSnapshotStorageLayout(f"{s1} should equals {s2}")


@dataclasses.dataclass
class SnapshotsDifference:
    """Represents the difference between two snapshots"""
    parent: Snapshot
    snapshot: Snapshot

    def __str__(self) -> str:
        return f"changes between {self.parent} and {self.snapshot}"

ContentToUpload = Union[None, Snapshot, SnapshotsDifference]

def compute_snapshot_to_upload(
    snapshots: Sequence[Snapshot], archived_snapshots: Sequence[Snapshot]
) -> ContentToUpload:
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
