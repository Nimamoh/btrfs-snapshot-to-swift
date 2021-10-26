"""
Module related to business logic.
"""

from typing import Iterator, Optional, Sequence, Union
from btrfs import Snapshot, SnapshotsDifference
from storage import compute_storage_filename
from exceptions import ProgrammingError

import os
import logging
import subprocess
import shutil
import contextlib

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


class PrepareContentEx(Exception):
    """Raised if PrepareContent failed"""

    pass


class PrepareContent:
    """
    Prepare the content to upload to a local file
    Args:
      to_upload (ContentToUpload): describe the content to ultimately upload,
        that we will be turning in a file beforehand
      basedir (basedir): directory in which we will store the file.
        Consider that change to existing files in that directory may happen.
    Returns:
      str: the absolute path in which we stored the file to upload
    Raises:
      PrepareContentEx
    """

    def __init__(self, content: ContentToUpload, dirname: str):

        self.__content = content
        self.__dirname = os.path.abspath(dirname)
        self.__basename = compute_storage_filename(self.__content)
        self.__path = os.path.join(self.__dirname, self.__basename)
        which_btrfs = shutil.which("btrfs")
        which_pv = shutil.which("pv")

        if not os.path.isdir(self.__dirname):
            raise PrepareContentEx(f"{self.__dirname} does not exist.")
        if os.path.exists(self.__path):
            raise PrepareContentEx(f"{self.__path} already exists.")
        if not which_btrfs:
            raise PrepareContentEx(f"btrfs must be in path!")

        self.__which_btrfs: str = which_btrfs
        self.__which_pv = which_pv

    def target_path(self) -> str:
        """Path in which the file is/will be stored in the preparation"""
        return self.__path


    def prepare(self, ratelimit = None) -> Iterator[str]:
        """
        Prepare the content to the target_path.
        It uses btrfs send
        It is a generator which report completion progress if possible (using pv).
        Completion progress is setup at 1 report / second.

        Args:
          ratelimit: ratelimit of transfer speed in quantity per seconds. 
            Accepts input like 100 (100B/s), 1K (1K/s), 1M, 1G...
        """
        #fmt:off
        with open(self.__path, "x") as file, self._send_process(file) as send, self._pv_process(send, file, ratelimit) as pv:
        #fmt:on
            processes = [send]

            if pv is not None:
                processes += [pv]
                for line in pv.stderr:
                    yield line.rstrip()

            ret = [p.wait() for p in processes]
            if any([s != 0 for s in ret]):
                raise PrepareContentEx("Error happened during btrfs send")
    
    def _send_process(self, file):
        content = self.__content
        cmd = [self.__which_btrfs, "send"]
        if isinstance(content, SnapshotsDifference):
            cmd += ["-p", content.parent.abs_path, content.snapshot.abs_path]
        elif isinstance(content, Snapshot):
            cmd += [content.abs_path]
        else:
            raise ProgrammingError

        dest = file if not self.__which_pv else subprocess.PIPE
        return subprocess.Popen(cmd, stderr=subprocess.DEVNULL, stdout=dest)

    def _pv_process(self, send_process, file, ratelimit):
        if not self.__which_pv:
            return contextlib.nullcontext()

        cmd = [self.__which_pv, "-i", "1", "-f"]
        if ratelimit:
            cmd += ["-L", ratelimit]
        return subprocess.Popen(
            cmd,
            stdin=send_process.stdout,
            stderr=subprocess.PIPE,
            stdout=file,
            text=True,
        )
