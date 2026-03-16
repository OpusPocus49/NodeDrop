from __future__ import annotations

import socket
import threading
from typing import Any, Callable

from core.models import NodeIdentity
from network.protocol import (
    MessageSerializationError,
    MessageType,
    create_message,
    deserialize_message,
    serialize_message,
)
from utils.config import (
    DISCOVERY_BROADCAST_IP,
    DISCOVERY_INTERVAL_SECONDS,
    DISCOVERY_UDP_PORT,
)
from utils.log_utils import get_logger

# ============================================================
# Internal discovery defaults
# ============================================================

DISCOVERY_SOCKET_TIMEOUT_SECONDS: float = 1.0
DISCOVERY_BUFFER_SIZE: int = 65535

PeerDiscoveredCallback = Callable[[dict[str, Any]], None]


class DiscoveryService:
    """
    UDP LAN discovery service for NodeDrop V1.

    Responsibilities:
    - periodically broadcast local NODE_ANNOUNCE messages
    - listen for remote NODE_ANNOUNCE messages
    - validate incoming messages through protocol.py
    - ignore self-announcements
    - notify the application through an optional callback

    The service is intentionally simple for V1 and does not depend
    on AppManager yet. It only exposes discovery events upward.
    """

    def __init__(
        self,
        local_identity: NodeIdentity,
        on_peer_discovered: PeerDiscoveredCallback | None = None,
    ) -> None:
        self._logger = get_logger("network.discovery")
        self._local_identity = local_identity
        self._on_peer_discovered = on_peer_discovered

        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._broadcast_thread: threading.Thread | None = None
        self._listen_thread: threading.Thread | None = None

        self._broadcast_socket: socket.socket | None = None
        self._listen_socket: socket.socket | None = None

        self._running = False

    # ============================================================
    # Public API
    # ============================================================

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start(self) -> None:
        """
        Start the discovery service.

        Starts:
        - one broadcast thread
        - one listen thread
        """
        with self._lock:
            if self._running:
                self._logger.warning("DiscoveryService is already running.")
                return

            self._logger.info(
                "Starting DiscoveryService on UDP port %s (broadcast=%s, interval=%ss).",
                DISCOVERY_UDP_PORT,
                DISCOVERY_BROADCAST_IP,
                DISCOVERY_INTERVAL_SECONDS,
            )

            self._stop_event.clear()

            self._broadcast_thread = threading.Thread(
                target=self._broadcast_loop,
                name="NodeDropDiscoveryBroadcast",
                daemon=True,
            )
            self._listen_thread = threading.Thread(
                target=self._listen_loop,
                name="NodeDropDiscoveryListen",
                daemon=True,
            )

            try:
                self._listen_thread.start()
                self._broadcast_thread.start()
            except Exception:
                self._stop_event.set()
                self._close_sockets()
                self._broadcast_thread = None
                self._listen_thread = None
                raise

            self._running = True

    def stop(self) -> None:
        """
        Stop the discovery service cleanly.
        """
        with self._lock:
            if not self._running:
                self._logger.warning("DiscoveryService is not running.")
                return

            self._logger.info("Stopping DiscoveryService.")
            self._stop_event.set()
            self._close_sockets()

            broadcast_thread = self._broadcast_thread
            listen_thread = self._listen_thread

            self._broadcast_thread = None
            self._listen_thread = None
            self._running = False

        if broadcast_thread is not None:
            broadcast_thread.join(timeout=2.0)

        if listen_thread is not None:
            listen_thread.join(timeout=2.0)

        self._logger.info("DiscoveryService stopped.")

    # ============================================================
    # Internal message building / handling
    # ============================================================

    def _build_announce_message(self) -> dict[str, Any]:
        """
        Build a validated NODE_ANNOUNCE message from local identity.
        """
        return create_message(
            MessageType.NODE_ANNOUNCE,
            node_id=self._local_identity.node_id,
            display_name=self._local_identity.display_name,
            host_name=self._local_identity.host_name,
            ip_address=self._local_identity.ip_address,
            tcp_port=self._local_identity.tcp_port,
            version=self._local_identity.version,
        )

    def _handle_incoming_announce(self, message: dict[str, Any], source_ip: str) -> None:
        """
        Handle a validated remote NODE_ANNOUNCE message.
        """
        remote_node_id = message.get("node_id")

        if remote_node_id == self._local_identity.node_id:
            self._logger.debug(
                "Ignoring self-announcement from node_id=%s.",
                remote_node_id,
            )
            return

        normalized_message = dict(message)
        announced_ip = normalized_message.get("ip_address")

        # On Windows / VirtualBox / multi-adapter hosts, the UDP packet source
        # may come from a link-local adapter (169.254.x.x). For V1, we keep the
        # announced IP and store the packet source separately for diagnostics.
        normalized_message["source_ip"] = source_ip

        if not announced_ip:
            normalized_message["ip_address"] = source_ip

        self._logger.info(
            "Discovered peer: %s (%s) announced_ip=%s source_ip=%s tcp_port=%s",
            normalized_message.get("display_name"),
            normalized_message.get("node_id"),
            normalized_message.get("ip_address"),
            normalized_message.get("source_ip"),
            normalized_message.get("tcp_port"),
        )

        if self._on_peer_discovered is not None:
            try:
                self._on_peer_discovered(normalized_message)
            except Exception as exc:
                self._logger.exception("Peer discovered callback failed: %s", exc)

    # ============================================================
    # Broadcast thread
    # ============================================================

    def _broadcast_loop(self) -> None:
        """
        Periodically broadcast NODE_ANNOUNCE over UDP.
        """
        self._logger.debug("Broadcast loop started.")

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
                self._broadcast_socket = sock
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

                while not self._stop_event.is_set():
                    try:
                        message = self._build_announce_message()
                        payload = serialize_message(message).encode("utf-8")

                        sock.sendto(
                            payload,
                            (DISCOVERY_BROADCAST_IP, DISCOVERY_UDP_PORT),
                        )

                        self._logger.debug(
                            "NODE_ANNOUNCE broadcast sent to %s:%s.",
                            DISCOVERY_BROADCAST_IP,
                            DISCOVERY_UDP_PORT,
                        )

                    except OSError as exc:
                        if self._stop_event.is_set():
                            break
                        self._logger.warning("Broadcast socket error: %s", exc)

                    except Exception as exc:
                        self._logger.exception("Unexpected error in broadcast loop: %s", exc)

                    if self._stop_event.wait(DISCOVERY_INTERVAL_SECONDS):
                        break

        except Exception as exc:
            self._logger.exception("Failed to initialize broadcast loop: %s", exc)

        finally:
            self._broadcast_socket = None
            self._logger.debug("Broadcast loop stopped.")

    # ============================================================
    # Listen thread
    # ============================================================

    def _listen_loop(self) -> None:
        """
        Listen for UDP NODE_ANNOUNCE messages on the discovery port.
        """
        self._logger.debug("Listen loop started.")

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
                self._listen_socket = sock
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("0.0.0.0", DISCOVERY_UDP_PORT))
                sock.settimeout(DISCOVERY_SOCKET_TIMEOUT_SECONDS)

                self._logger.info(
                    "Discovery listener bound on 0.0.0.0:%s.",
                    DISCOVERY_UDP_PORT,
                )

                while not self._stop_event.is_set():
                    try:
                        data, address = sock.recvfrom(DISCOVERY_BUFFER_SIZE)
                        source_ip, source_port = address

                        self._logger.debug(
                            "UDP packet received from %s:%s (%d bytes).",
                            source_ip,
                            source_port,
                            len(data),
                        )

                        message = deserialize_message(data)

                    except socket.timeout:
                        continue

                    except MessageSerializationError as exc:
                        self._logger.debug("Invalid discovery payload ignored: %s", exc)
                        continue

                    except OSError as exc:
                        if self._stop_event.is_set():
                            break
                        self._logger.warning("Listener socket error: %s", exc)
                        continue

                    except Exception as exc:
                        self._logger.warning("Unexpected discovery listener error: %s", exc)
                        continue

                    if message.get("type") != MessageType.NODE_ANNOUNCE.value:
                        self._logger.debug(
                            "Ignoring non-discovery message received on discovery port: %s",
                            message.get("type"),
                        )
                        continue

                    self._handle_incoming_announce(message, source_ip)

        except Exception as exc:
            self._logger.exception("Failed to initialize listen loop: %s", exc)

        finally:
            self._listen_socket = None
            self._logger.debug("Listen loop stopped.")

    # ============================================================
    # Utilities
    # ============================================================

    def _close_sockets(self) -> None:
        """
        Close sockets to unblock threads during shutdown.
        """
        if self._broadcast_socket is not None:
            try:
                self._broadcast_socket.close()
            except OSError:
                pass
            finally:
                self._broadcast_socket = None

        if self._listen_socket is not None:
            try:
                self._listen_socket.close()
            except OSError:
                pass
            finally:
                self._listen_socket = None