from __future__ import annotations

from pathlib import Path

from core.models import (
    TransferFile,
    TransferItemType,
    TransferJob,
    TransferProgress,
    TransferStatus,
)


def test_transfer_job_total_size_single_file() -> None:
    file_item = TransferFile(
        path=Path("a.txt"),
        relative_path=Path("a.txt"),
        item_type=TransferItemType.FILE,
        size_bytes=100,
        checksum="abc",
    )

    job = TransferJob(
        job_id="job1",
        session_id="session1",
        source_peer_id="peer-a",
        target_peer_id="peer-b",
        items=[file_item],
    )

    assert job.compute_total_size() == 100


def test_transfer_job_total_size_multiple_files() -> None:
    files = [
        TransferFile(
            path=Path("a.txt"),
            relative_path=Path("a.txt"),
            item_type=TransferItemType.FILE,
            size_bytes=100,
            checksum="abc",
        ),
        TransferFile(
            path=Path("folder/b.txt"),
            relative_path=Path("folder/b.txt"),
            item_type=TransferItemType.FILE,
            size_bytes=200,
            checksum="def",
        ),
    ]

    job = TransferJob(
        job_id="job1",
        session_id="session1",
        source_peer_id="peer-a",
        target_peer_id="peer-b",
        items=files,
    )

    assert job.compute_total_size() == 300


def test_transfer_job_total_size_ignores_directories() -> None:
    items = [
        TransferFile(
            path=Path("folder"),
            relative_path=Path("folder"),
            item_type=TransferItemType.DIRECTORY,
            size_bytes=9999,
        ),
        TransferFile(
            path=Path("folder/file.txt"),
            relative_path=Path("folder/file.txt"),
            item_type=TransferItemType.FILE,
            size_bytes=120,
            checksum="abc",
        ),
    ]

    job = TransferJob(
        job_id="job1",
        session_id="session1",
        source_peer_id="peer-a",
        target_peer_id="peer-b",
        items=items,
    )

    assert job.compute_total_size() == 120


def test_transfer_job_status_transitions() -> None:
    job = TransferJob(
        job_id="job1",
        session_id="session1",
        source_peer_id="peer-a",
        target_peer_id="peer-b",
        items=[],
    )

    assert job.status == TransferStatus.PENDING

    job.start()
    assert job.status == TransferStatus.RUNNING
    assert job.started_at is not None

    job.complete()
    assert job.status == TransferStatus.COMPLETED
    assert job.completed_at is not None


def test_transfer_job_fail_transition() -> None:
    job = TransferJob(
        job_id="job1",
        session_id="session1",
        source_peer_id="peer-a",
        target_peer_id="peer-b",
        items=[],
    )

    job.start()
    job.fail("checksum mismatch")

    assert job.status == TransferStatus.FAILED
    assert job.error_message == "checksum mismatch"
    assert job.completed_at is not None


def test_transfer_job_cancel_transition() -> None:
    job = TransferJob(
        job_id="job1",
        session_id="session1",
        source_peer_id="peer-a",
        target_peer_id="peer-b",
        items=[],
    )

    job.start()
    job.cancel()

    assert job.status == TransferStatus.CANCELLED
    assert job.completed_at is not None


def test_transfer_job_progress_percent() -> None:
    file_item = TransferFile(
        path=Path("a.txt"),
        relative_path=Path("a.txt"),
        item_type=TransferItemType.FILE,
        size_bytes=400,
        checksum="abc",
    )

    job = TransferJob(
        job_id="job1",
        session_id="session1",
        source_peer_id="peer-a",
        target_peer_id="peer-b",
        items=[file_item],
    )
    job.recompute_total_bytes()
    job.set_transferred_bytes(100)

    assert job.progress_percent == 25.0


def test_transfer_file_progress_percent_from_sent_bytes() -> None:
    file_item = TransferFile(
        path=Path("a.txt"),
        relative_path=Path("a.txt"),
        item_type=TransferItemType.FILE,
        size_bytes=200,
        checksum="abc",
    )

    file_item.set_bytes_sent(50)

    assert file_item.progress_percent == 25.0


def test_transfer_file_progress_percent_from_received_bytes() -> None:
    file_item = TransferFile(
        path=Path("a.txt"),
        relative_path=Path("a.txt"),
        item_type=TransferItemType.FILE,
        size_bytes=200,
        checksum="abc",
    )

    file_item.set_bytes_received(100)

    assert file_item.progress_percent == 50.0


def test_transfer_file_status_transitions() -> None:
    file_item = TransferFile(
        path=Path("a.txt"),
        relative_path=Path("a.txt"),
        item_type=TransferItemType.FILE,
        size_bytes=200,
        checksum="abc",
    )

    assert file_item.status == TransferStatus.PENDING

    file_item.mark_started()
    assert file_item.status == TransferStatus.RUNNING
    assert file_item.started_at is not None

    file_item.mark_completed()
    assert file_item.status == TransferStatus.COMPLETED
    assert file_item.finished_at is not None


def test_transfer_job_build_progress_snapshot() -> None:
    file_item = TransferFile(
        path=Path("a.txt"),
        relative_path=Path("a.txt"),
        item_type=TransferItemType.FILE,
        size_bytes=100,
        checksum="abc",
    )

    job = TransferJob(
        job_id="job1",
        session_id="session1",
        source_peer_id="peer-a",
        target_peer_id="peer-b",
        items=[file_item],
    )
    job.recompute_total_bytes()
    job.set_transferred_bytes(40)

    snapshot = job.build_progress(
        file_name="a.txt",
        file_bytes_done=40,
        file_bytes_total=100,
        speed_bps=2048.0,
        eta_seconds=0.5,
    )

    assert isinstance(snapshot, TransferProgress)
    assert snapshot.job_id == "job1"
    assert snapshot.file_name == "a.txt"
    assert snapshot.bytes_done == 40
    assert snapshot.bytes_total == 100
    assert snapshot.job_bytes_done == 40
    assert snapshot.job_bytes_total == 100
    assert snapshot.progress_percent == 40.0
    assert snapshot.speed_bps == 2048.0
    assert snapshot.eta_seconds == 0.5