from __future__ import annotations

from pathlib import Path

from core.app_manager import AppManager
from core.models import NodeIdentity, Peer, TransferStatus
from network.protocol import MessageType, create_message
from network.session import SessionCancelledError, SessionClient
from core.transfer_manager import TransferManager


class FakeSocket:
    def close(self) -> None:
        pass

    def shutdown(self, _how=None) -> None:
        pass


class CancelAfterOneChunkSessionClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self.sent_bytes: list[bytes] = []

    def open_authenticated_session(self, peer, session_id: str, password: str):
        return FakeSocket(), create_message(
            MessageType.AUTH_SUCCESS,
            session_id=session_id,
        )

    def send_message(self, sock, message: dict, **kwargs) -> None:
        self.sent_messages.append(message)

    def send_bytes(self, sock, data: bytes, **kwargs) -> None:
        self.sent_bytes.append(data)

    def receive_message(self, sock):
        raise AssertionError("receive_message() should not be called after cancellation.")


def make_identity() -> NodeIdentity:
    return NodeIdentity(
        node_id="node-local",
        display_name="Local Node",
        host_name="localhost",
        ip_address="127.0.0.1",
        tcp_port=48556,
        version="1.0",
    )


def make_peer() -> Peer:
    return Peer(
        peer_id="peer-1",
        display_name="Remote Peer",
        host_name="remote-host",
        ip_address="127.0.0.1",
        tcp_port=48556,
        version="1.0",
    )


def register_test_peer(app: AppManager, peer: Peer) -> None:
    app._peer_manager.register_peer(
        {
            "node_id": peer.peer_id,
            "display_name": peer.display_name,
            "host_name": peer.host_name,
            "ip_address": peer.ip_address,
            "tcp_port": peer.tcp_port,
            "version": peer.version,
        }
    )


def test_transfer_manager_build_transfer_cancel_message(tmp_path) -> None:
    source_file = tmp_path / "hello.txt"
    source_file.write_text("hello world", encoding="utf-8")

    manager = TransferManager(downloads_dir=tmp_path / "downloads")

    job = manager.start_transfer(
        session_id="session-1",
        source_peer_id="peer-a",
        target_peer_id="peer-b",
        source_path=source_file,
        job_id="job-cancel-1",
    )

    cancel_message = manager.build_transfer_cancel_message(
        job.job_id,
        "User cancelled transfer.",
    )

    assert cancel_message["type"] == "TRANSFER_CANCEL"
    assert cancel_message["job_id"] == "job-cancel-1"
    assert cancel_message["reason"] == "User cancelled transfer."
    assert manager.get_job(job.job_id).status == TransferStatus.CANCELLED


def test_transfer_manager_handle_transfer_cancel_marks_job_cancelled(tmp_path) -> None:
    manager = TransferManager(downloads_dir=tmp_path / "downloads")

    job = manager.handle_transfer_init(
        message=create_message(
            MessageType.TRANSFER_INIT,
            session_id="session-1",
            job_id="job-cancel-2",
            item_count=1,
            total_bytes=10,
        ),
        source_peer_id="peer-a",
        target_peer_id="peer-b",
    )

    cancelled_job = manager.handle_transfer_cancel(
        create_message(
            MessageType.TRANSFER_CANCEL,
            session_id="session-1",
            job_id="job-cancel-2",
            reason="Remote cancellation.",
        )
    )

    assert cancelled_job.job_id == job.job_id
    assert cancelled_job.status == TransferStatus.CANCELLED
    assert cancelled_job.error_message == "Remote cancellation."


def test_app_manager_send_transfer_can_cancel_after_first_chunk(tmp_path) -> None:
    started = []
    failed = []

    source_file = tmp_path / "big.txt"
    source_file.write_bytes(b"a" * 70000)

    app = AppManager(
        local_identity=make_identity(),
        shared_password="secret",
        on_transfer_started=lambda job: started.append(job.job_id),
        on_transfer_failed=lambda job, reason: failed.append((job.job_id, reason)),
    )

    peer = make_peer()
    register_test_peer(app, peer)

    fake_client = CancelAfterOneChunkSessionClient()
    app._session_client = fake_client

    job_id = app.send_transfer(
        peer_id=peer.peer_id,
        source_paths=source_file,
        cancel_after_chunks=1,
    )

    assert started == [job_id]
    assert failed == [(job_id, "Transfer cancelled by sender.")]
    assert any(msg["type"] == "TRANSFER_CANCEL" for msg in fake_client.sent_messages)

class InterruptibleFakeSocket:
    def __init__(self) -> None:
        self._timeout = None
        self.send_calls = 0

    def gettimeout(self):
        return self._timeout

    def settimeout(self, value) -> None:
        self._timeout = value

    def send(self, data) -> int:
        self.send_calls += 1
        return min(8192, len(data))

    def close(self) -> None:
        pass


def test_session_client_send_bytes_can_be_interrupted_mid_send() -> None:
    client = SessionClient(local_identity=make_identity())
    fake_socket = InterruptibleFakeSocket()

    cancellation_state = {"triggered": False}

    def cancellation_check() -> bool:
        if fake_socket.send_calls >= 2:
            cancellation_state["triggered"] = True
        return cancellation_state["triggered"]

    try:
        client.send_bytes(
            fake_socket,
            b"a" * 200000,
            cancellation_check=cancellation_check,
        )
    except SessionCancelledError:
        pass
    else:
        raise AssertionError("SessionCancelledError was expected.")

    assert fake_socket.send_calls >= 2
