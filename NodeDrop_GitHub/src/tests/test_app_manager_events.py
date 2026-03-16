from __future__ import annotations

from core.app_manager import AppManager
from core.models import NodeIdentity, Peer
from network.protocol import MessageType, create_message


class FakeSocket:
    def close(self) -> None:
        pass


class FakeSessionClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self.sent_bytes: list[bytes] = []
        self.responses: list[dict] = []

    def open_authenticated_session(self, peer, session_id: str, password: str):
        return FakeSocket(), create_message(
            MessageType.AUTH_SUCCESS,
            session_id=session_id,
        )

    def send_message(self, sock, message: dict) -> None:
        self.sent_messages.append(message)

    def send_bytes(self, sock, data: bytes) -> None:
        self.sent_bytes.append(data)

    def receive_message(self, sock):
        if self.responses:
            return self.responses.pop(0)

        transfer_complete_message = next(
            msg
            for msg in reversed(self.sent_messages)
            if msg.get("type") == MessageType.TRANSFER_COMPLETE.value
        )

        return create_message(
            MessageType.TRANSFER_ACK,
            session_id=transfer_complete_message["session_id"],
            job_id=transfer_complete_message["job_id"],
        )


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
    """
    Register a peer through the real PeerManager protocol-facing contract.
    """
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


def test_send_transfer_emits_started_progress_completed(tmp_path) -> None:
    started: list[str] = []
    progress: list[float] = []
    completed: list[str] = []
    failed: list[tuple[str, str]] = []

    source_file = tmp_path / "hello.txt"
    source_file.write_text("hello world", encoding="utf-8")

    app = AppManager(
        local_identity=make_identity(),
        shared_password="secret",
        on_transfer_started=lambda job: started.append(job.job_id),
        on_transfer_progress=lambda snapshot: progress.append(snapshot.progress_percent),
        on_transfer_completed=lambda job: completed.append(job.job_id),
        on_transfer_failed=lambda job, reason: failed.append((job.job_id, reason)),
    )

    peer = make_peer()
    register_test_peer(app, peer)

    app._session_client = FakeSessionClient()

    job_id = app.send_transfer(
        peer_id=peer.peer_id,
        source_paths=source_file,
    )

    assert started == [job_id]
    assert completed == [job_id]
    assert failed == []
    assert len(progress) >= 1
    assert max(progress) == 100.0


def test_handle_incoming_transfer_complete_emits_completed(tmp_path) -> None:
    completed: list[str] = []

    app = AppManager(
        local_identity=make_identity(),
        shared_password="secret",
        on_transfer_completed=lambda job: completed.append(job.job_id),
    )

    class RecordingSessionClient:
        def __init__(self) -> None:
            self.sent_messages: list[dict] = []

        def send_message(self, sock, message: dict) -> None:
            self.sent_messages.append(message)

    app._session_client = RecordingSessionClient()

    session_context = {
        "session_id": "session-1",
        "sender_id": "peer-1",
        "sender_name": "Remote Peer",
        "client_socket": object(),
    }
    client_address = ("127.0.0.1", 50000)

    app._handle_transfer_message(
        create_message(
            MessageType.TRANSFER_INIT,
            session_id="session-1",
            job_id="job-1",
            item_count=1,
            total_bytes=4,
        ),
        None,
        session_context,
        client_address,
    )

    app._handle_transfer_message(
        create_message(
            MessageType.FILE_INFO,
            session_id="session-1",
            job_id="job-1",
            relative_path="a.txt",
            item_type="FILE",
            size_bytes=4,
            checksum="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        ),
        None,
        session_context,
        client_address,
    )

    app._handle_transfer_message(
        create_message(
            MessageType.FILE_CHUNK,
            session_id="session-1",
            job_id="job-1",
            relative_path="a.txt",
            chunk_size=4,
        ),
        b"test",
        session_context,
        client_address,
    )

    app._handle_transfer_message(
        create_message(
            MessageType.FILE_COMPLETE,
            session_id="session-1",
            job_id="job-1",
            relative_path="a.txt",
        ),
        None,
        session_context,
        client_address,
    )

    app._handle_transfer_message(
        create_message(
            MessageType.TRANSFER_COMPLETE,
            session_id="session-1",
            job_id="job-1",
        ),
        None,
        session_context,
        client_address,
    )

    assert completed == ["job-1"]


def test_handle_transfer_error_emits_failed(tmp_path) -> None:
    failed: list[tuple[str, str]] = []

    app = AppManager(
        local_identity=make_identity(),
        shared_password="secret",
        on_transfer_failed=lambda job, reason: failed.append((job.job_id, reason)),
    )

    session_context = {
        "session_id": "session-1",
        "sender_id": "peer-1",
        "sender_name": "Remote Peer",
        "client_socket": object(),
    }
    client_address = ("127.0.0.1", 50000)

    app._handle_transfer_message(
        create_message(
            MessageType.TRANSFER_INIT,
            session_id="session-1",
            job_id="job-err",
            item_count=1,
            total_bytes=0,
        ),
        None,
        session_context,
        client_address,
    )

    app._handle_transfer_message(
        create_message(
            MessageType.TRANSFER_ERROR,
            session_id="session-1",
            job_id="job-err",
            error_message="remote failure",
        ),
        None,
        session_context,
        client_address,
    )

    assert failed == [("job-err", "remote failure")]