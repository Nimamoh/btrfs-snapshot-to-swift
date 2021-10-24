from unittest.mock import MagicMock, patch

import uuid
import pytest

from swiftclient.service import SwiftService
from btrfs import Snapshot
from storage import (
    _compute_common_prefix,
    compute_storage_filename,
    only_stored,
)


@patch("test_storage.SwiftService.list")
def test_only_stored(listMock: MagicMock):
    snapshots = _make_btrfs_snapshots("snap/one", "snap/two")
    _configure_list_mock(
        listMock, "whatever/snap/three", compute_storage_filename(snapshots[0])
    )

    stored_snapshots = only_stored(snapshots, "whatever_container_name")

    assert len(stored_snapshots) == 1
    assert stored_snapshots == snapshots[0:1]


def test_compute_common_prefix():
    l = ["a", "aaa", "aa"]
    assert "a" == _compute_common_prefix(l)
    l = ["aaaa", "bbbb", "cccc"]
    assert "" == _compute_common_prefix(l)
    l = ["snapshot/toto/1", "snapshot/toto/2", "snapshot/toto/3"]
    assert "snapshot/toto/" == _compute_common_prefix(l)
    l.append("nonono")
    assert "" == _compute_common_prefix(l)


def _configure_list_mock(mock: MagicMock, *names: str):
    """Configure swift list mock for it to return successfully the list of name in parameters"""
    mock.return_value = [{"success": True, "listing": list({"name": x} for x in names)}]


def _make_btrfs_snapshots(*rel_paths: str):
    """Make list of btrfs snapshots with rel_paths, faking/inferring rest of parameters"""
    return list(
        Snapshot(fs_uuid=uuid.uuid4(), rel_path=x, abs_path="/", otime=0.0)
        for x in rel_paths
    )


if __name__ == "__main__":
    pytest.main(["-s", __file__])
