"""
Module holding operation directly related to btrfs.
"""
import logging
import os
from dataclasses import dataclass
from uuid import UUID

import btrfsutil

TOP_LEVEL_SUBVOL_ID = 5

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Snapshot:
    """Represents a local btrfs snapshot"""

    parent_uuid: str
    """UUID string of parent subvolume. (which subvolume is represented by this snapshots)"""
    rel_path: str
    """relative path from btrfs filesystem"""
    abs_path: str
    """absolute path of the snapshot is on the host filesystem"""
    otime: float
    """Creation time of the snapshot"""

    def __str__(self) -> str:
        return f"<FS_TREE>/{self.rel_path}"


@dataclass(frozen=True)
class SnapshotsDifference:
    """Represents the difference between two snapshots"""

    parent: Snapshot
    snapshot: Snapshot

    def __str__(self) -> str:
        return f"changes between {self.parent} and {self.snapshot}"


def _compute_root_path(path):
    """Compute the path of the root filesystem from subvolume path given in argument"""
    norm_path = os.path.normpath(path)
    rel_path = btrfsutil.subvolume_path(norm_path)
    root_path = os.path.normpath(norm_path.removesuffix(rel_path))
    _log.debug(
        f'Given path "{norm_path}" with its relative part "{rel_path}". root filesystem path is "{root_path}"'
    )
    return root_path


def find_ro_snapshots_of(path) -> list[Snapshot]:
    """
    Look for read only snapshots of subvolume designated by 'path'.
    Returns list of paths (relative to rootfs) of RO snapshots sorted chronologically based on creation time.
    """
    path = os.path.abspath(path)
    ro_snapshots: list[Snapshot] = []
    root_fs_path = _compute_root_path(path)
    uuid = UUID(bytes=btrfsutil.subvolume_info(path).uuid)
    uuid_str = str(uuid)
    _log.debug(f'Looking for readonly snapshot of "{path}" which has uuid "{uuid_str}"')

    with btrfsutil.SubvolumeIterator(path, TOP_LEVEL_SUBVOL_ID) as it:
        for curr_path_, id_ in it:
            curr_fullpath_ = os.path.normpath(os.path.join(root_fs_path, curr_path_))
            info = btrfsutil.subvolume_info(path, id_)
            curr_parent_uuid = UUID(bytes=info.parent_uuid)
            otime = info.otime
            ro = btrfsutil.get_subvolume_read_only(curr_fullpath_)
            # debug(f'Checking if "{curr_fullpath_}" is readonly: "{ro}"')
            if curr_parent_uuid == uuid and ro:
                snapshot = Snapshot(
                    parent_uuid=str(curr_parent_uuid),
                    rel_path=curr_path_,
                    abs_path=curr_fullpath_,
                    otime=otime,
                )
                ro_snapshots.append(snapshot)

    _log.debug(f"ro_snapshots: {ro_snapshots}")
    ro_snapshots = sorted(ro_snapshots, key=lambda x: x.otime)
    _log.debug(f"ro_snapshots: {ro_snapshots}")
    return ro_snapshots
