from __future__ import annotations

import time

from core.models import NodeIdentity, Peer
from network.listener import SessionListener
from network.protocol import MessageType
from network.session import SessionClient
from utils.config import TRANSFER_TCP_PORT


def test_tcp_session_auth_success() -> None:
    listener_identity = NodeIdentity(
        node_id="listener-node-001",
        display_name="Listener Node",
        host_name="LISTENER-PC",
        ip_address="127.0.0.1",
        tcp_port=TRANSFER_TCP_PORT,
        version="1.0",
    )

    client_identity = NodeIdentity(
        node_id="client-node-001",
        display_name="Client Node",
        host_name="CLIENT-PC",
        ip_address="127.0.0.1",
        tcp_port=TRANSFER_TCP_PORT,
        version="1.0",
    )

    def on_auth_response(message: dict, client_address: tuple[str, int]) -> dict:
        password = message["password"]
        session_id = message["session_id"]

        if password == "nodepass":
            return {
                "type": MessageType.AUTH_SUCCESS.value,
                "protocol_version": "1.0",
                "session_id": session_id,
            }

        return {
            "type": MessageType.AUTH_FAILED.value,
            "protocol_version": "1.0",
            "session_id": session_id,
            "reason": "INVALID_PASSWORD",
        }

    listener = SessionListener(on_auth_response=on_auth_response)
    listener.start()

    time.sleep(0.3)

    try:
        peer = Peer(
            peer_id=listener_identity.node_id,
            display_name=listener_identity.display_name,
            host_name=listener_identity.host_name,
            ip_address=listener_identity.ip_address,
            tcp_port=TRANSFER_TCP_PORT,
            version=listener_identity.version,
        )

        client = SessionClient(local_identity=client_identity)
        response = client.request_session(
            peer=peer,
            session_id="auth-session-001",
            password="nodepass",
        )

        assert response["type"] == MessageType.AUTH_SUCCESS.value
        assert response["session_id"] == "auth-session-001"

    finally:
        listener.stop()


def test_tcp_session_auth_failed() -> None:
    client_identity = NodeIdentity(
        node_id="client-node-001",
        display_name="Client Node",
        host_name="CLIENT-PC",
        ip_address="127.0.0.1",
        tcp_port=TRANSFER_TCP_PORT,
        version="1.0",
    )

    def on_auth_response(message: dict, client_address: tuple[str, int]) -> dict:
        session_id = message["session_id"]
        return {
            "type": MessageType.AUTH_FAILED.value,
            "protocol_version": "1.0",
            "session_id": session_id,
            "reason": "INVALID_PASSWORD",
        }

    listener = SessionListener(on_auth_response=on_auth_response)
    listener.start()

    time.sleep(0.3)

    try:
        peer = Peer(
            peer_id="listener-node-001",
            display_name="Listener Node",
            host_name="LISTENER-PC",
            ip_address="127.0.0.1",
            tcp_port=TRANSFER_TCP_PORT,
            version="1.0",
        )

        client = SessionClient(local_identity=client_identity)
        response = client.request_session(
            peer=peer,
            session_id="auth-session-002",
            password="wrongpass",
        )

        assert response["type"] == MessageType.AUTH_FAILED.value
        assert response["session_id"] == "auth-session-002"
        assert response["reason"] == "INVALID_PASSWORD"

    finally:
        listener.stop()