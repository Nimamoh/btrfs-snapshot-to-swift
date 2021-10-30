from btrfs import Snapshot

import pytest
from itertools import repeat
from uuid import uuid4
from tempfile import TemporaryDirectory

from business import PrepareContent, SnapshotsDifference, compute_snapshot_to_upload
from business import UnexpectedSnapshotStorageLayout


_static_uuids = tuple(u() for u in repeat(uuid4, 10))


def _snapshot_gen():
    yield Snapshot(
        fs_uuid=_static_uuids[0],
        rel_path="/snapshots/1",
        abs_path="/fs/snapshots/1",
        otime=0.0,
    )
    yield Snapshot(
        fs_uuid=_static_uuids[1],
        rel_path="/snapshots/2",
        abs_path="/fs/snapshots/2",
        otime=1.0,
    )
    yield Snapshot(
        fs_uuid=_static_uuids[2],
        rel_path="/snapshots/3",
        abs_path="/fs/snapshots/3",
        otime=2.0,
    )
    yield Snapshot(
        fs_uuid=_static_uuids[3],
        rel_path="/snapshots/4",
        abs_path="/fs/snapshots/4",
        otime=3.0,
    )


def _snapshot_diff_gen():
    snapshots_gen = _snapshot_gen()
    previous = None
    for snap in snapshots_gen:
        current = snap
        if current and previous:
            yield SnapshotsDifference(parent=previous, snapshot=current)


@pytest.mark.parametrize(
    "snapshots,archived",
    [
        (
            [s for s in _snapshot_gen()],
            [s for (i, s) in enumerate(_snapshot_gen()) if i > 0],
        ),
        (
            [s for s in _snapshot_gen()],
            [s for (i, s) in enumerate(_snapshot_gen()) if i > 1],
        ),
    ],
)
def test_compute_snapshots_to_upload_unexpected_storage_layout(snapshots, archived):
    with pytest.raises(UnexpectedSnapshotStorageLayout):
        compute_snapshot_to_upload(snapshots, archived)


@pytest.mark.parametrize(
    "snapshots,archived",
    [
        ([next(_snapshot_gen()), next(_snapshot_gen())], []),  # Same snapshots
        (
            [next(_snapshot_gen()), next(_snapshot_gen())],  # Same snapshots
            [next(_snapshot_gen())],
        ),
    ],
)
def test_compute_snapshots_to_upload_value_error(snapshots, archived):
    with pytest.raises(ValueError):
        compute_snapshot_to_upload(snapshots, archived)


@pytest.mark.parametrize(
    "snapshots,archived",
    [
        (
            [s for s in _snapshot_gen()],
            [s for s in _snapshot_gen()],
        ),
        (
            [s for s in _snapshot_gen()],
            [s for (i, s) in enumerate(_snapshot_gen()) if i < 2],
        ),
    ],
)
def test_compute_snapshots_to_upload_no_exception(snapshots, archived):
    compute_snapshot_to_upload(snapshots, archived)


def test_compute_snapshots_to_upload():
    assert compute_snapshot_to_upload([], []) == None

    snapshots = tuple(s for s in _snapshot_gen())

    archived = ()
    to_be_uploaded = compute_snapshot_to_upload(snapshots, archived)
    assert to_be_uploaded == snapshots[0]

    archived = tuple(s for (i, s) in enumerate(snapshots) if i < 2)
    to_be_uploaded = compute_snapshot_to_upload(snapshots, archived)
    assert to_be_uploaded == SnapshotsDifference(snapshots[1], snapshots[2])

    archived = snapshots
    to_be_uploaded = compute_snapshot_to_upload(snapshots, archived)
    assert to_be_uploaded == None


def test_prepare_content():

    """Test initialization of PrepareContent."""
    with TemporaryDirectory() as tmpdirname:
        snapshot = next(_snapshot_gen())
        preparator = PrepareContent(snapshot, tmpdirname, None)
        assert preparator.target_path() is not None


if __name__ == "__main__":
    pytest.main(["-s", __file__])
