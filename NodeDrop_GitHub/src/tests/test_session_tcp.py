from __future__ import annotations

import socket
import sys
import time
import uuid
from pathlib import Path

# Ajoute le dossier src au PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.models import NodeIdentity, Peer, generate_session_id
from network.listener import SessionListener
from network.protocol import MessageType, create_message
from network.session import SessionClient
from utils.config import APP_VERSION, TRANSFER_TCP_PORT
from utils.log_utils import setup_logging


def detect_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def build_test_identity() -> NodeIdentity:
    host_name = socket.gethostname()

    return NodeIdentity(
        node_id=f"{host_name}-{uuid.uuid4().hex[:8]}",
        display_name=host_name,
        host_name=host_name,
        ip_address=detect_local_ip(),
        tcp_port=TRANSFER_TCP_PORT,
        version=APP_VERSION,
    )


def build_loopback_peer() -> Peer:
    now = time.time()

    return Peer(
        peer_id="loopback-peer",
        display_name="Loopback Test Peer",
        host_name="localhost",
        ip_address="127.0.0.1",
        tcp_port=TRANSFER_TCP_PORT,
        version=APP_VERSION,
        last_seen=now,
        is_online=True,
    )


def _session_callback(message: dict, client_address: tuple[str, int]) -> dict | None:
    print()
    print("=== SESSION REQUEST RECEIVED ===")
    print(f"Client address : {client_address}")
    print(f"Message        : {message}")
    print()

    return None


def _auth_handler(message: dict, client_address: tuple[str, int]) -> dict | None:
    print()
    print("=== AUTH RESPONSE RECEIVED ===")
    print(f"Client address : {client_address}")
    print(f"Message        : {message}")
    print()

    session_id = message.get("session_id")
    password = message.get("password")

    if password == "nodepass":
        return create_message(
            MessageType.AUTH_SUCCESS,
            session_id=session_id,
        )

    return create_message(
        MessageType.AUTH_FAILED,
        session_id=session_id,
        reason="Invalid password",
    )


def _transfer_handler(message: dict, chunk_data: bytes | None, session_context: dict, client_address):
    """
    Handler minimal pour les messages de transfert.

    Pour ce test, on ne traite rien réellement,
    on vérifie seulement que le flux post-auth fonctionne.
    """
    print()
    print("=== TRANSFER MESSAGE RECEIVED ===")
    print(f"Type           : {message.get('type')}")
    print(f"Session        : {session_context.get('session_id')}")
    print(f"Client         : {client_address}")

    if chunk_data is not None:
        print(f"Chunk bytes    : {len(chunk_data)}")

    print()


def main() -> None:
    setup_logging(level="DEBUG", enable_console=True)

    local_identity = build_test_identity()
    peer = build_loopback_peer()

    print("=== NodeDrop TCP Session Test ===")
    print(f"Node ID : {local_identity.node_id}")
    print(f"Peer IP : {peer.ip_address}")
    print(f"TCP port: {TRANSFER_TCP_PORT}")
    print()

    listener = SessionListener(
        on_session_requested=_session_callback,
        on_auth_response=_auth_handler,
        on_transfer_message=_transfer_handler,
    )

    listener.start()

    time.sleep(1.0)

    client = SessionClient(local_identity=local_identity)

    try:
        session_id = generate_session_id()

        response = client.request_session(
            peer=peer,
            session_id=session_id,
            password="nodepass",
        )

        print("=== SESSION RESPONSE ===")
        print(response)

        if response.get("type") == "AUTH_SUCCESS":
            print()
            print("[AUTHENTICATION SUCCESS]")
            print(f"Session ID : {response.get('session_id')}")

        elif response.get("type") == "AUTH_FAILED":
            print()
            print("[AUTHENTICATION FAILED]")
            print(f"Reason : {response.get('reason')}")

        else:
            print()
            print("[SESSION RESULT]")
            print(response)

    finally:
        listener.stop()
        print()
        print("Session listener stopped.")


if __name__ == "__main__":
    main()