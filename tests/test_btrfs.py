import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Hashable
from unittest.mock import MagicMock, patch
import uuid

from btrfs import Snapshot, find_ro_snapshots_of


@patch("btrfsutil.SubvolumeIterator")
@patch("btrfsutil.get_subvolume_read_only")
@patch("btrfsutil.subvolume_info")
@patch("btrfsutil.subvolume_path")
def test_find_ro_snapshots_of(
    mock_subvolume_path: MagicMock,
    mock_subvolume_info: MagicMock,
    mock_get_subvolume_readonly: MagicMock,
    mock_subvolume_iterator: MagicMock,
):
    def test_with_model(fs_path):
        model = _make_model(fs_path)

        mock_subvolume_info.side_effect = _subvolume_info(model.subvols())
        mock_subvolume_path.side_effect = _subvolume_path(model.subvols())
        mock_get_subvolume_readonly.side_effect = _get_subvolume_read_only(
            model.subvols()
        )
        mock_subvolume_iterator.side_effect = _subvolume_iterator(model.subvols())

        snapshots = find_ro_snapshots_of(os.path.join(fs_path, "subvol"))
        assert len(snapshots) == 3
        assert snapshots[0].rel_path == "snapshots/subvol.0"
        assert snapshots[1].rel_path == "snapshots/subvol.1"
        assert snapshots[2].rel_path == "snapshots/subvol.2"

        for snapshot in snapshots:
            model_subvol = model.subvol(snapshot.rel_path)
            parent_uuid_str = str(uuid.UUID(bytes=model_subvol.parent_uuid))
            assert snapshot.parent_uuid == parent_uuid_str

    test_with_model("/fs")
    test_with_model("/")


def test_snapshot_is_hashable():
    snapshot = Snapshot("", "", "", 0.0)
    assert isinstance(snapshot, Hashable)


def test_shapshot_uuid():
    uuid_str = str(uuid.uuid4())
    s = Snapshot(parent_uuid=uuid_str, rel_path="", abs_path="", otime=0.0)
    l = []
    l.append(s)


@dataclass
class _FakeSubvol:
    """Information holder for faking btrfsutil calls"""
    relpath: str
    abspath: str
    id: int
    uuid: bytes
    parent_uuid: bytes
    ro: bool = False
    otime: float = 0.0

    def uuid_as_str(self):
        return str(uuid.UUID(bytes=self.uuid))


def _subvolume_info(model: list[_FakeSubvol]):
    """Generate mocked version of btrfs.subvolume_info(path, <id>)"""

    def inner(path, id_=0):
        if id_ > 0:
            return next(x for x in model if id_ == x.id)
        else:
            return next(x for x in model if path == x.abspath)

    return inner


def _subvolume_path(model: list[_FakeSubvol]):
    """Generate mocked version of btrfs.subvolume_path(path, <id>)"""

    def inner(fullpath):
        return next(x.relpath for x in model if x.abspath == fullpath)

    return inner


def _get_subvolume_read_only(model: list[_FakeSubvol]):
    """Generate mocked version of btrfs.get_subvolume_read_only(path)"""

    def inner(fullpath: str):
        fullpath = os.path.normpath(fullpath)
        return next(x.ro for x in model if x.abspath == fullpath)

    return inner


def _subvolume_iterator(model: list[_FakeSubvol]):
    """Generate mocked version of btrfs.SubvolumeIterator"""

    @contextmanager
    def inner(*args):
        if len(args) != 2 or args[1] != 5:
            raise ValueError("Only supports call with (path, 5)")
        # Since we expect listing subvol from rootfs, we list all
        yield list((x.relpath, x.id) for x in model)

    return inner


class _TestModel:
    def __init__(self, model: list[_FakeSubvol]) -> None:
        self._model = model

    def subvol(self, relpath: str) -> _FakeSubvol:
        """Finds first subvol in test model having specified relpath"""
        return next(s for s in self._model if s.relpath == relpath)

    def subvols(self) -> tuple[_FakeSubvol, ...]:
        return tuple(self._model)


def _make_model(rootfs: str) -> _TestModel:
    """Quick and dirty model for a btrfs subvolume tree"""
    rootfs = rootfs if rootfs == "/" else rootfs.removesuffix("/")
    prefix_rootfs = rootfs if rootfs[-1] == "/" else rootfs + "/"
    rootfs_uuid = uuid.uuid4().bytes

    subvol_uuid = uuid.uuid4().bytes
    subvol_1_uuid = uuid.uuid4().bytes
    subvols = [
        _FakeSubvol(
            relpath="",
            abspath=f"{rootfs}",
            id=5,
            uuid=uuid.uuid4().bytes,
            parent_uuid=b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
        ),
        _FakeSubvol(
            relpath="subvol",
            abspath=f"{prefix_rootfs}subvol",
            id=6,
            uuid=subvol_uuid,
            parent_uuid=rootfs_uuid,
        ),
        _FakeSubvol(
            relpath="snapshots/subvol.1",
            abspath=f"{prefix_rootfs}snapshots/subvol.1",
            id=7,
            uuid=subvol_1_uuid,
            parent_uuid=subvol_uuid,
            ro=True,
            otime=1.0,
        ),
        _FakeSubvol(
            relpath="snapshots/subvol.2",
            abspath=f"{prefix_rootfs}snapshots/subvol.2",
            id=8,
            uuid=uuid.uuid4().bytes,
            parent_uuid=subvol_uuid,
            ro=True,
            otime=2.0,
        ),
        _FakeSubvol(
            relpath="snapshots/subvol.0",
            abspath=f"{prefix_rootfs}snapshots/subvol.0",
            id=11,
            uuid=uuid.uuid4().bytes,
            parent_uuid=subvol_uuid,
            ro=True,
            otime=0.0,
        ),
        _FakeSubvol(
            relpath="snapshots/subvol.3",
            abspath=f"{prefix_rootfs}snapshots/subvol.3",
            id=10,
            uuid=uuid.uuid4().bytes,
            parent_uuid=subvol_uuid,
        ),
        _FakeSubvol(
            relpath="snapshots/subvol.1.1",
            abspath=f"{prefix_rootfs}snapshots/subvol.1.1",
            id=1,
            uuid=uuid.uuid4().bytes,
            parent_uuid=subvol_1_uuid,
        ),
    ]
    return _TestModel(subvols)
