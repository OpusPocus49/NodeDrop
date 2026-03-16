from __future__ import annotations

from pathlib import Path

from core.transfer_manager import TransferManager
from network.protocol import MessageType, create_message


def test_start_transfer_with_multiple_files(tmp_path) -> None:
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"

    file_a.write_text("hello", encoding="utf-8")
    file_b.write_text("world!", encoding="utf-8")

    manager = TransferManager(downloads_dir=tmp_path / "downloads")

    job = manager.start_transfer(
        session_id="session-1",
        source_peer_id="peer-a",
        target_peer_id="peer-b",
        source_path=[file_a, file_b],
        job_id="job-1",
    )

    assert job.job_id == "job-1"
    assert len(job.items) == 2
    assert job.total_bytes == 11
    assert job.transferred_bytes == 0


def test_start_transfer_with_directory(tmp_path) -> None:
    root = tmp_path / "root"
    sub = root / "sub"
    sub.mkdir(parents=True)

    file_a = root / "a.txt"
    file_b = sub / "b.txt"

    file_a.write_text("abc", encoding="utf-8")
    file_b.write_text("defg", encoding="utf-8")

    manager = TransferManager(downloads_dir=tmp_path / "downloads")

    job = manager.start_transfer(
        session_id="session-1",
        source_peer_id="peer-a",
        target_peer_id="peer-b",
        source_path=root,
        job_id="job-2",
    )

    assert len(job.items) == 2
    assert job.total_bytes == 7

    relative_paths = sorted(item.relative_path.as_posix() for item in job.items)
    assert relative_paths == ["a.txt", "sub/b.txt"]


def test_iter_file_chunks_updates_progress(tmp_path) -> None:
    file_a = tmp_path / "a.txt"
    file_a.write_text("abcdefghij", encoding="utf-8")

    manager = TransferManager(downloads_dir=tmp_path / "downloads")

    job = manager.start_transfer(
        session_id="session-1",
        source_peer_id="peer-a",
        target_peer_id="peer-b",
        source_path=file_a,
        job_id="job-3",
    )

    chunks = list(manager.iter_file_chunks(job.job_id, chunk_size=4))

    assert len(chunks) == 3
    assert job.transferred_bytes == 10
    assert job.items[0].bytes_sent == 10


def test_incoming_multi_file_flow(tmp_path) -> None:
    downloads_dir = tmp_path / "downloads"
    manager = TransferManager(downloads_dir=downloads_dir)

    init_message = create_message(
        MessageType.TRANSFER_INIT,
        session_id="session-1",
        job_id="job-4",
        item_count=2,
        total_bytes=9,
    )

    job = manager.handle_transfer_init(
        message=init_message,
        source_peer_id="peer-a",
        target_peer_id="peer-b",
    )

    assert job.job_id == "job-4"
    assert job.total_bytes == 9

    # file 1
    info_1 = create_message(
        MessageType.FILE_INFO,
        session_id="session-1",
        job_id="job-4",
        relative_path="a.txt",
        item_type="FILE",
        size_bytes=4,
        checksum="8d777f385d3dfec8815d20f7496026dc9c2f0bff4f6b8d4f9d5d6f4e6f4b8b6f",  # intentionally ignored if mismatch? no
    )
    # We need a correct checksum for "test"
    info_1["checksum"] = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

    manager.handle_file_info(info_1)

    chunk_1 = create_message(
        MessageType.FILE_CHUNK,
        session_id="session-1",
        job_id="job-4",
        relative_path="a.txt",
        chunk_size=4,
    )
    manager.handle_file_chunk(chunk_1, b"test")

    complete_1 = create_message(
        MessageType.FILE_COMPLETE,
        session_id="session-1",
        job_id="job-4",
        relative_path="a.txt",
    )
    manager.handle_file_complete(complete_1)

    # file 2
    info_2 = create_message(
        MessageType.FILE_INFO,
        session_id="session-1",
        job_id="job-4",
        relative_path="sub/b.txt",
        item_type="FILE",
        size_bytes=5,
        checksum="2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
    )

    manager.handle_file_info(info_2)

    chunk_2 = create_message(
        MessageType.FILE_CHUNK,
        session_id="session-1",
        job_id="job-4",
        relative_path="sub/b.txt",
        chunk_size=5,
    )
    manager.handle_file_chunk(chunk_2, b"hello")

    complete_2 = create_message(
        MessageType.FILE_COMPLETE,
        session_id="session-1",
        job_id="job-4",
        relative_path="sub/b.txt",
    )
    manager.handle_file_complete(complete_2)

    transfer_complete = create_message(
        MessageType.TRANSFER_COMPLETE,
        session_id="session-1",
        job_id="job-4",
    )
    final_job = manager.handle_transfer_complete(transfer_complete)

    assert final_job.transferred_bytes == 9
    assert final_job.total_bytes == 9
    assert final_job.progress_percent == 100.0

    file_1 = downloads_dir / "a.txt"
    file_2 = downloads_dir / "sub" / "b.txt"

    assert file_1.exists()
    assert file_2.exists()
    assert file_1.read_bytes() == b"test"
    assert file_2.read_bytes() == b"hello"


def test_cleanup_finished_transfers_removes_completed_jobs(tmp_path) -> None:
    file_a = tmp_path / "a.txt"
    file_a.write_text("hello", encoding="utf-8")

    manager = TransferManager(downloads_dir=tmp_path / "downloads")

    job = manager.start_transfer(
        session_id="session-1",
        source_peer_id="peer-a",
        target_peer_id="peer-b",
        source_path=file_a,
        job_id="job-5",
    )

    ack_message = create_message(
        MessageType.TRANSFER_ACK,
        session_id="session-1",
        job_id="job-5",
    )
    manager.handle_transfer_ack(ack_message)

    removed = manager.cleanup_finished_transfers()

    assert removed == ["job-5"]
    assert manager.get_jobs() == []