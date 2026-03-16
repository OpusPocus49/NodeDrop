from __future__ import annotations

from typing import Any

import pytest

from core.models import NodeIdentity


class FakeDiscoveryService:
    """
    Test double for DiscoveryService.

    It stores the callback given by AppManager and exposes a helper
    to simulate a discovered peer without using the real network.
    """

    def __init__(
        self,
        local_identity: NodeIdentity,
        on_peer_discovered,
    ) -> None:
        self.local_identity = local_identity
        self.on_peer_discovered = on_peer_discovered
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def emit_peer(self, message: dict[str, Any]) -> None:
        self.on_peer_discovered(message)


class FakeSessionListener:
    """
    Test double for SessionListener.

    It stores both callbacks used by AppManager:
    - on_session_requested
    - on_auth_response
    """

    def __init__(
        self,
        on_session_requested=None,
        on_auth_response=None,
    ) -> None:
        self.on_session_requested = on_session_requested
        self.on_auth_response = on_auth_response
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def emit_session_request(
        self,
        message: dict[str, Any],
        client_address: tuple[str, int],
    ) -> dict[str, Any] | None:
        if self.on_session_requested is None:
            return None
        return self.on_session_requested(message, client_address)

    def emit_auth_response(
        self,
        message: dict[str, Any],
        client_address: tuple[str, int],
    ) -> dict[str, Any] | None:
        if self.on_auth_response is None:
            return None
        return self.on_auth_response(message, client_address)


class FakeSessionClient:
    """
    Test double for SessionClient.

    It records outgoing requests and returns a deterministic
    AUTH_SUCCESS final response.
    """

    def __init__(self, local_identity: NodeIdentity) -> None:
        self.local_identity = local_identity
        self.calls: list[dict[str, Any]] = []

    def request_session(self, peer, session_id: str, password: str) -> dict[str, Any]:
        self.calls.append(
            {
                "peer": peer,
                "session_id": session_id,
                "password": password,
            }
        )
        return {
            "type": "AUTH_SUCCESS",
            "protocol_version": "1.0",
            "session_id": session_id,
        }


@pytest.fixture
def local_identity() -> NodeIdentity:
    return NodeIdentity(
        node_id="local-node-001",
        display_name="Local Node",
        host_name="LOCAL-PC",
        ip_address="127.0.0.1",
        tcp_port=50001,
        version="1.0",
    )


@pytest.fixture
def app_manager_module(monkeypatch):
    """
    Import app_manager module and replace its network dependencies
    with test doubles before AppManager instances are created.
    """
    import core.app_manager as app_manager_module

    monkeypatch.setattr(app_manager_module, "DiscoveryService", FakeDiscoveryService)
    monkeypatch.setattr(app_manager_module, "SessionListener", FakeSessionListener)
    monkeypatch.setattr(app_manager_module, "SessionClient", FakeSessionClient)

    return app_manager_module


def test_app_manager_start_and_stop(local_identity: NodeIdentity, app_manager_module) -> None:
    AppManager = app_manager_module.AppManager

    manager = AppManager(
        local_identity=local_identity,
        shared_password="nodepass",
    )

    assert manager.is_running is False

    manager.start()

    assert manager.is_running is True
    assert manager._discovery_service.started is True
    assert manager._session_listener.started is True

    manager.stop()

    assert manager.is_running is False
    assert manager._discovery_service.stopped is True
    assert manager._session_listener.stopped is True


def test_discovery_updates_peer_manager_and_notifies_upper_layer(
    local_identity: NodeIdentity,
    app_manager_module,
) -> None:
    AppManager = app_manager_module.AppManager

    captured_peer_lists: list[list[Any]] = []

    def on_peers_updated(peers) -> None:
        captured_peer_lists.append(peers)

    manager = AppManager(
        local_identity=local_identity,
        shared_password="nodepass",
        on_peers_updated=on_peers_updated,
    )

    remote_message = {
        "type": "NODE_ANNOUNCE",
        "protocol_version": "1.0",
        "node_id": "remote-node-001",
        "display_name": "Remote Node",
        "host_name": "REMOTE-PC",
        "ip_address": "192.168.1.50",
        "tcp_port": 50001,
        "version": "1.0",
        "source_ip": "192.168.1.50",
    }

    manager._discovery_service.emit_peer(remote_message)

    peers = manager.get_peers()
    assert len(peers) == 1

    peer = peers[0]
    assert peer.peer_id == "remote-node-001"
    assert peer.display_name == "Remote Node"
    assert peer.host_name == "REMOTE-PC"
    assert peer.ip_address == "192.168.1.50"
    assert peer.tcp_port == 50001
    assert peer.version == "1.0"
    assert peer.is_online is True

    assert len(captured_peer_lists) == 1
    assert len(captured_peer_lists[0]) == 1
    assert captured_peer_lists[0][0].peer_id == "remote-node-001"


def test_repeated_discovery_updates_existing_peer_instead_of_creating_duplicate(
    local_identity: NodeIdentity,
    app_manager_module,
) -> None:
    AppManager = app_manager_module.AppManager

    manager = AppManager(
        local_identity=local_identity,
        shared_password="nodepass",
    )

    first_announce = {
        "type": "NODE_ANNOUNCE",
        "protocol_version": "1.0",
        "node_id": "remote-node-001",
        "display_name": "Remote Node",
        "host_name": "REMOTE-PC",
        "ip_address": "192.168.1.50",
        "tcp_port": 50001,
        "version": "1.0",
    }

    second_announce = {
        "type": "NODE_ANNOUNCE",
        "protocol_version": "1.0",
        "node_id": "remote-node-001",
        "display_name": "Remote Node Updated",
        "host_name": "REMOTE-PC-NEW",
        "ip_address": "192.168.1.51",
        "tcp_port": 50002,
        "version": "1.1",
    }

    manager._discovery_service.emit_peer(first_announce)
    manager._discovery_service.emit_peer(second_announce)

    peers = manager.get_peers()
    assert len(peers) == 1

    peer = peers[0]
    assert peer.peer_id == "remote-node-001"
    assert peer.display_name == "Remote Node Updated"
    assert peer.host_name == "REMOTE-PC-NEW"
    assert peer.ip_address == "192.168.1.51"
    assert peer.tcp_port == 50002
    assert peer.version == "1.1"


def test_request_session_uses_known_peer_and_session_client(
    local_identity: NodeIdentity,
    app_manager_module,
) -> None:
    AppManager = app_manager_module.AppManager

    manager = AppManager(
        local_identity=local_identity,
        shared_password="nodepass",
    )

    remote_message = {
        "type": "NODE_ANNOUNCE",
        "protocol_version": "1.0",
        "node_id": "remote-node-001",
        "display_name": "Remote Node",
        "host_name": "REMOTE-PC",
        "ip_address": "192.168.1.50",
        "tcp_port": 50001,
        "version": "1.0",
    }

    manager._discovery_service.emit_peer(remote_message)

    response = manager.request_session("remote-node-001")

    assert response["type"] == "AUTH_SUCCESS"
    assert "session_id" in response
    assert len(manager._session_client.calls) == 1

    call = manager._session_client.calls[0]
    assert call["peer"].peer_id == "remote-node-001"
    assert isinstance(call["session_id"], str)
    assert call["session_id"]
    assert call["password"] == "nodepass"


def test_request_session_uses_explicit_password_when_provided(
    local_identity: NodeIdentity,
    app_manager_module,
) -> None:
    AppManager = app_manager_module.AppManager

    manager = AppManager(
        local_identity=local_identity,
        shared_password="nodepass",
    )

    remote_message = {
        "type": "NODE_ANNOUNCE",
        "protocol_version": "1.0",
        "node_id": "remote-node-001",
        "display_name": "Remote Node",
        "host_name": "REMOTE-PC",
        "ip_address": "192.168.1.50",
        "tcp_port": 50001,
        "version": "1.0",
    }

    manager._discovery_service.emit_peer(remote_message)

    manager.request_session("remote-node-001", password="override-pass")

    assert len(manager._session_client.calls) == 1
    call = manager._session_client.calls[0]
    assert call["password"] == "override-pass"


def test_request_session_raises_for_unknown_peer(
    local_identity: NodeIdentity,
    app_manager_module,
) -> None:
    AppManager = app_manager_module.AppManager

    manager = AppManager(
        local_identity=local_identity,
        shared_password="nodepass",
    )

    with pytest.raises(ValueError, match="Unknown peer_id"):
        manager.request_session("missing-peer")


def test_incoming_session_request_is_forwarded_to_upper_callback(
    local_identity: NodeIdentity,
    app_manager_module,
) -> None:
    AppManager = app_manager_module.AppManager

    captured_calls: list[dict[str, Any]] = []

    def on_session_requested(
        message: dict[str, Any],
        client_address: tuple[str, int],
    ) -> dict[str, Any]:
        captured_calls.append(
            {
                "message": message,
                "client_address": client_address,
            }
        )
        return {
            "type": "SESSION_ACCEPTED",
            "protocol_version": "1.0",
            "session_id": message["session_id"],
        }

    manager = AppManager(
        local_identity=local_identity,
        shared_password="nodepass",
        on_session_requested=on_session_requested,
    )

    incoming_message = {
        "type": "SESSION_REQUEST",
        "protocol_version": "1.0",
        "session_id": "session-test-001",
        "sender_id": "remote-node-001",
        "sender_name": "Remote Node",
    }

    client_address = ("192.168.1.50", 50099)

    response = manager._session_listener.emit_session_request(
        incoming_message,
        client_address,
    )

    assert len(captured_calls) == 1
    assert captured_calls[0]["message"]["session_id"] == "session-test-001"
    assert captured_calls[0]["client_address"] == client_address

    assert response is not None
    assert response["type"] == "SESSION_ACCEPTED"
    assert response["session_id"] == "session-test-001"


def test_incoming_auth_response_is_validated_by_auth_manager(
    local_identity: NodeIdentity,
    app_manager_module,
) -> None:
    AppManager = app_manager_module.AppManager

    manager = AppManager(
        local_identity=local_identity,
        shared_password="nodepass",
    )

    incoming_message = {
        "type": "AUTH_RESPONSE",
        "protocol_version": "1.0",
        "session_id": "session-auth-001",
        "password": "nodepass",
    }

    client_address = ("192.168.1.50", 50099)

    response = manager._session_listener.emit_auth_response(
        incoming_message,
        client_address,
    )

    assert response is not None
    assert response["type"] == "AUTH_SUCCESS"
    assert response["session_id"] == "session-auth-001"


def test_incoming_auth_response_fails_with_invalid_password(
    local_identity: NodeIdentity,
    app_manager_module,
) -> None:
    AppManager = app_manager_module.AppManager

    manager = AppManager(
        local_identity=local_identity,
        shared_password="nodepass",
    )

    incoming_message = {
        "type": "AUTH_RESPONSE",
        "protocol_version": "1.0",
        "session_id": "session-auth-002",
        "password": "wrongpass",
    }

    client_address = ("192.168.1.50", 50099)

    response = manager._session_listener.emit_auth_response(
        incoming_message,
        client_address,
    )

    assert response is not None
    assert response["type"] == "AUTH_FAILED"
    assert response["session_id"] == "session-auth-002"
    assert response["reason"] == "INVALID_PASSWORD"


def test_cleanup_expired_peers_notifies_upper_layer_when_peer_state_changes(
    local_identity: NodeIdentity,
    app_manager_module,
) -> None:
    from datetime import UTC, datetime, timedelta

    from utils.config import PEER_EXPIRY_SECONDS

    AppManager = app_manager_module.AppManager

    captured_peer_lists: list[list[Any]] = []

    def on_peers_updated(peers) -> None:
        captured_peer_lists.append(peers)

    manager = AppManager(
        local_identity=local_identity,
        shared_password="nodepass",
        on_peers_updated=on_peers_updated,
    )

    remote_message = {
        "type": "NODE_ANNOUNCE",
        "protocol_version": "1.0",
        "node_id": "remote-node-001",
        "display_name": "Remote Node",
        "host_name": "REMOTE-PC",
        "ip_address": "192.168.1.50",
        "tcp_port": 50001,
        "version": "1.0",
    }

    manager._discovery_service.emit_peer(remote_message)

    peer = manager.get_peer("remote-node-001")
    assert peer is not None
    assert peer.is_online is True

    expired_time = datetime.now(UTC) - timedelta(seconds=PEER_EXPIRY_SECONDS + 5)
    peer.last_seen = expired_time

    affected = manager.cleanup_expired_peers(remove=False)

    assert len(affected) == 1
    assert affected[0].peer_id == "remote-node-001"
    assert affected[0].is_online is False

    # 1 callback after discovery, 1 callback after cleanup
    assert len(captured_peer_lists) == 2
    assert captured_peer_lists[-1][0].is_online is False