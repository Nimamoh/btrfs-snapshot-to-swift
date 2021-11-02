"""
Module related to business logic.
"""

from typing import Iterator, Sequence
from btrfs import Snapshot, SnapshotsDifference
from storage import compute_storage_filename, ContentToArchive
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


def compute_snapshot_to_archive(snapshots: Sequence[Snapshot], archived: Sequence[Snapshot]) -> Iterator[ContentToArchive]:
    """
    Compute snapshots to archive,

    Returns:
      generator of content to archive
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

    def snapshot_or_diff(parent, snapshot):
        if parent is None:
            return snapshot
        else:
            return SnapshotsDifference(parent, snapshot)

    def chain_of(snapshots: Sequence[Snapshot]):
        chain = []
        parent = None
        for s in snapshots:
            chain.append(snapshot_or_diff(parent, s))
            parent = s
        return chain
    

    sane_check(snapshots)
    sane_check(archived)

    if not snapshots:
        return
    if not archived:
        yield from chain_of(snapshots)
        return
    if len(snapshots) == len(archived):
        return
    
    corresponding_archives = tuple(
        archived[i] if i < len(archived) else None
        for i in range(len(snapshots))
    )
    assert len(snapshots) == len(corresponding_archives)

    chain = []
    for i, (s, a) in enumerate(zip(snapshots, corresponding_archives)):
        if a is not None and s != a:
            raise unequal_snapshots_ex(s, a)

        if a is not None:
            chain = [a]
            continue
        chain += snapshots[i:]
        break

    yield from (chain_of(chain)[1:])


class PrepareContentEx(Exception):
    """Raised if PrepareContent failed"""

    pass


class PrepareContent:
    """
    Prepare the content to upload to a local file
    Args:
      content (ContentToArchive): describe the content to ultimately upload,
        that we will be turning in a file beforehand.
      dirname (str): directory in which we will store the file.
        Consider that arbitrary change to existing files in that directory may happen.
    Raises:
      PrepareContentEx
    """

    def __init__(self, content: ContentToArchive, dirname: str, age_recipient: str):

        self.__content = content
        self.__dirname = os.path.abspath(dirname)
        self.__basename = compute_storage_filename(self.__content)
        self.__path = os.path.join(self.__dirname, self.__basename)
        self.__age_recipient = age_recipient
        which_btrfs = shutil.which("btrfs")
        which_pv = shutil.which("pv")
        which_age = shutil.which("age")

        if not os.path.isdir(self.__dirname):
            raise PrepareContentEx(f"{self.__dirname} does not exist.")
        if os.path.exists(self.__path):
            raise PrepareContentEx(f"{self.__path} already exists.")
        if not which_btrfs:
            raise PrepareContentEx(f"btrfs must be in path!")
        if self.__age_recipient and not which_age:
            raise PrepareContentEx(f"age must be in path!")

        self.__which_btrfs: str = which_btrfs
        self.__which_pv = which_pv
        self.__which_age = which_age

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
        with open(self.__path, "x") as file, \
             self._send_process(stdout= \
                 (subprocess.PIPE if (self.__which_pv or self.__age_recipient) else file)\
             ) as send, \
             self._age_process(stdin=send.stdout, stdout=subprocess.PIPE) as age, \
             self._pv_process(stdin=(age.stdout if age else send.stdout), stdout=file, ratelimit=ratelimit) as pv:
        #fmt:on
            processes = [send]

            if pv is not None:
                processes += [pv]
                for line in pv.stderr:
                    yield line.rstrip()

            ret = [p.wait() for p in processes]
            if any([s != 0 for s in ret]):
                raise PrepareContentEx("Error happened during btrfs send")
    
    def _send_process(self, stdout):
        content = self.__content
        cmd = [self.__which_btrfs, "send"]
        if isinstance(content, SnapshotsDifference):
            cmd += ["-p", content.parent.abs_path, content.snapshot.abs_path]
        elif isinstance(content, Snapshot):
            cmd += [content.abs_path]
        else:
            raise ProgrammingError

        _log.debug("Send command:")
        _log.debug(cmd)
        return subprocess.Popen(cmd, stderr=subprocess.DEVNULL, stdout=stdout)
    
    def _age_process(self, stdin, stdout):
        if not self.__age_recipient:
            return contextlib.nullcontext()

        recipient = self.__age_recipient
        cmd = [self.__which_age, "-r", recipient]

        _log.debug("Age command:")
        _log.debug(cmd)
        return subprocess.Popen(cmd, stdin=stdin, stdout=stdout)

    def _pv_process(self, stdin, stdout, ratelimit):
        if not self.__which_pv:
            return contextlib.nullcontext()

        cmd = [self.__which_pv, "-i", "1", "-f"]
        if ratelimit:
            cmd += ["-L", ratelimit]

        _log.debug("pv command:")
        _log.debug(cmd)
        return subprocess.Popen(
            cmd,
            stdin=stdin,
            stderr=subprocess.PIPE,
            stdout=stdout,
            text=True,
        )
