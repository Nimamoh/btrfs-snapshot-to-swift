import os
from contextlib import contextmanager
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from btrfs import find_ro_snapshots_of


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
    # Rootfs in a regular folder
    model = _make_model("/fs")
    mock_subvolume_info.side_effect = __subvolume_info(model)
    mock_subvolume_path.side_effect = __subvolume_path(model)
    mock_get_subvolume_readonly.side_effect = __get_subvolume_read_only(model)
    mock_subvolume_iterator.side_effect = __subvolume_iterator(model)

    snapshots = find_ro_snapshots_of("/fs/subvol")
    assert len(snapshots) == 3
    assert snapshots[0].rel_path == "snapshots/subvol.0"
    assert snapshots[1].rel_path == "snapshots/subvol.1"
    assert snapshots[2].rel_path == "snapshots/subvol.2"

    # Rootfs in /
    model = _make_model("/")
    mock_subvolume_info.side_effect = __subvolume_info(model)
    mock_subvolume_path.side_effect = __subvolume_path(model)
    mock_get_subvolume_readonly.side_effect = __get_subvolume_read_only(model)
    mock_subvolume_iterator.side_effect = __subvolume_iterator(model)

    snapshots = find_ro_snapshots_of("/subvol")
    assert len(snapshots) == 3
    assert snapshots[0].rel_path == "snapshots/subvol.0"
    assert snapshots[1].rel_path == "snapshots/subvol.1"
    assert snapshots[2].rel_path == "snapshots/subvol.2"
    pass


@dataclass
class __FakeBtrfsSubvol:
    relpath: str
    abspath: str
    id: int
    uuid: bytes
    parent_uuid: bytes
    ro: bool = False
    otime: float = 0.0


def __subvolume_info(model: list[__FakeBtrfsSubvol]):
    """Generate mocked version of btrfs.subvolume_info(path, <id>)"""

    def inner(path, id_=0):
        if id_ > 0:
            return next(x for x in model if id_ == x.id)
        else:
            return next(x for x in model if path == x.abspath)

    return inner


def __subvolume_path(model: list[__FakeBtrfsSubvol]):
    """Generate mocked version of btrfs.subvolume_path(path, <id>)"""

    def inner(fullpath):
        return next(x.relpath for x in model if x.abspath == fullpath)

    return inner


def __get_subvolume_read_only(model: list[__FakeBtrfsSubvol]):
    """Generate mocked version of btrfs.get_subvolume_read_only(path)"""

    def inner(fullpath: str):
        fullpath = os.path.normpath(fullpath)
        return next(x.ro for x in model if x.abspath == fullpath)

    return inner


def __subvolume_iterator(model: list[__FakeBtrfsSubvol]):
    """Generate mocked version of btrfs.SubvolumeIterator"""

    @contextmanager
    def inner(*args):
        if len(args) != 2 or args[1] != 5:
            raise ValueError("Only supports call with (path, 5)")
        # Since we expect listing subvol from rootfs, we list all
        yield list((x.relpath, x.id) for x in model)

    return inner


def _make_model(rootfs: str) -> list[__FakeBtrfsSubvol]:
    """Quick and dirty model for a btrfs subvolume tree"""
    rootfs = rootfs if rootfs == "/" else rootfs.removesuffix("/")
    prefix_rootfs = rootfs if rootfs[-1] == "/" else rootfs + "/"
    return [
        __FakeBtrfsSubvol(
            relpath="",
            abspath=f"{rootfs}",
            id=5,
            uuid=b"root",
            parent_uuid=b"",
        ),
        __FakeBtrfsSubvol(
            relpath="subvol",
            abspath=f"{prefix_rootfs}subvol",
            id=6,
            uuid=b"subvol",
            parent_uuid=b"root",
        ),
        __FakeBtrfsSubvol(
            relpath="snapshots/subvol.1",
            abspath=f"{prefix_rootfs}snapshots/subvol.1",
            id=7,
            uuid=b"snapshots/subvol.1",
            parent_uuid=b"subvol",
            ro=True,
            otime=1.0,
        ),
        __FakeBtrfsSubvol(
            relpath="snapshots/subvol.2",
            abspath=f"{prefix_rootfs}snapshots/subvol.2",
            id=8,
            uuid=b"snapshots/subvol.2",
            parent_uuid=b"subvol",
            ro=True,
            otime=2.0,
        ),
        __FakeBtrfsSubvol(
            relpath="snapshots/subvol.0",
            abspath=f"{prefix_rootfs}snapshots/subvol.0",
            id=11,
            uuid=b"snapshots/subvol.0",
            parent_uuid=b"subvol",
            ro=True,
            otime=0.0,
        ),
        __FakeBtrfsSubvol(
            relpath="snapshots/subvol.3",
            abspath=f"{prefix_rootfs}snapshots/subvol.3",
            id=10,
            uuid=b"snapshots/subvol.3",
            parent_uuid=b"subvol",
        ),
        __FakeBtrfsSubvol(
            relpath="snapshots/subvol.1.1",
            abspath=f"{prefix_rootfs}snapshots/subvol.1.1",
            id=1,
            uuid=b"snapshots/subvol.1.1",
            parent_uuid=b"snapshots/subvol.1",
        ),
    ]
