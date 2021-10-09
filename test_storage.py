from unittest.mock import MagicMock, patch

import pytest

from swiftclient.service import SwiftService
from btrfs import BtrfsSnapshot
from storage import _compute_common_prefix, with_archived_information


@patch("test_storage.SwiftService.list")
def test_with_archived_information(listMock: MagicMock):
    __configure_list_mock(listMock, "a", "b", "c")
    wsi = with_archived_information(__make_btrfs_snapshots("snap/one", "snap/two"))
    assert all(not b for b in map(lambda x: x.is_archived, wsi))

    __configure_list_mock(listMock, "snap/one", "snap/three", "snap/two")
    wsi = with_archived_information(__make_btrfs_snapshots("snap/one", "snap/two"))
    assert all(b for b in map(lambda x: x.is_archived, wsi))

    __configure_list_mock(listMock, "snap/one")
    wsi = with_archived_information(__make_btrfs_snapshots("snap/one", "snap/two"))
    assert any(b for b in map(lambda x: x.is_archived, wsi))


def test_compute_common_prefix():
    l = ["a", "aaa", "aa"]
    assert "a" == _compute_common_prefix(l)
    l = ["aaaa", "bbbb", "cccc"]
    assert "" == _compute_common_prefix(l)
    l = ["snapshot/toto/1", "snapshot/toto/2", "snapshot/toto/3"]
    assert "snapshot/toto/" == _compute_common_prefix(l)
    l.append("nonono")
    assert "" == _compute_common_prefix(l)


def __configure_list_mock(mock: MagicMock, *names: list[str]):
    """Configure swift list mock for it to return successfully the list of name in parameters"""
    mock.return_value = [{"success": True, "listing": list({"name": x} for x in names)}]


def __make_btrfs_snapshots(*rel_paths):
    """Make list of btrfs snapshots with rel_paths, faking/inferring rest of parameters"""
    return list(BtrfsSnapshot(rel_path=x, abs_path="/", otime=0.0) for x in rel_paths)


if __name__ == "__main__":
    pytest.main()
