from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from core.models import Peer
from utils.config import PEER_EXPIRY_SECONDS
from utils.log_utils import get_logger


class PeerManager:
    """
    Maintain the list of peers discovered on the local network.

    Peers are indexed by peer_id, which corresponds to the remote
    NodeDrop node_id received in NODE_ANNOUNCE messages.

    Responsibilities:
    - register newly discovered peers
    - update peers when they re-announce
    - provide current peer list
    - mark expired peers offline
    - optionally remove expired peers
    """

    def __init__(self) -> None:
        self._logger = get_logger("core.peer_manager")
        self._peers: dict[str, Peer] = {}
        self._lock = threading.Lock()

    # ---------------------------------------------------------
    # Registration / update
    # ---------------------------------------------------------

    def register_peer(self, message: dict[str, Any]) -> Peer:
        """
        Register or update a peer from a validated NODE_ANNOUNCE message.

        The incoming protocol field is 'node_id', but the internal model
        stores it as 'peer_id'.
        """
        peer_id = message["node_id"]
        now = datetime.now(UTC)

        with self._lock:
            if peer_id in self._peers:
                peer = self._peers[peer_id]
                peer.display_name = message["display_name"]
                peer.host_name = message["host_name"]
                peer.ip_address = message["ip_address"]
                peer.tcp_port = message["tcp_port"]
                peer.version = message["version"]
                peer.last_seen = now
                peer.is_online = True

                self._logger.debug(
                    "Peer updated: %s (%s) at %s:%s",
                    peer.display_name,
                    peer.peer_id,
                    peer.ip_address,
                    peer.tcp_port,
                )
            else:
                peer = Peer(
                    peer_id=peer_id,
                    display_name=message["display_name"],
                    host_name=message["host_name"],
                    ip_address=message["ip_address"],
                    tcp_port=message["tcp_port"],
                    version=message["version"],
                    last_seen=now,
                    is_online=True,
                )

                self._peers[peer_id] = peer

                self._logger.info(
                    "Peer registered: %s (%s) at %s:%s",
                    peer.display_name,
                    peer.peer_id,
                    peer.ip_address,
                    peer.tcp_port,
                )

            return peer

    # ---------------------------------------------------------
    # Retrieval
    # ---------------------------------------------------------

    def get_peers(self, online_only: bool = False) -> list[Peer]:
        """
        Return a snapshot list of peers.

        If online_only is True, only currently online peers are returned.
        """
        with self._lock:
            peers = list(self._peers.values())

        if online_only:
            return [peer for peer in peers if peer.is_online]

        return peers

    def get_peer(self, peer_id: str) -> Peer | None:
        """
        Retrieve a peer by peer_id.
        """
        with self._lock:
            return self._peers.get(peer_id)

    def has_peer(self, peer_id: str) -> bool:
        """
        Return True if a peer is known.
        """
        with self._lock:
            return peer_id in self._peers

    # ---------------------------------------------------------
    # Expiration / offline management
    # ---------------------------------------------------------

    def cleanup_expired(self, remove: bool = False) -> list[Peer]:
        """
        Handle peers that have not been seen recently.

        By default:
        - peers are marked offline, but kept in memory

        If remove=True:
        - expired peers are removed from the manager

        Returns the list of affected peers.
        """
        now = datetime.now(UTC)
        timeout = timedelta(seconds=PEER_EXPIRY_SECONDS)
        affected: list[Peer] = []

        with self._lock:
            expired_ids = [
                peer_id
                for peer_id, peer in self._peers.items()
                if now - peer.last_seen > timeout
            ]

            for peer_id in expired_ids:
                peer = self._peers[peer_id]

                if remove:
                    removed_peer = self._peers.pop(peer_id)
                    affected.append(removed_peer)

                    self._logger.info(
                        "Peer removed after timeout: %s (%s)",
                        removed_peer.display_name,
                        removed_peer.peer_id,
                    )
                else:
                    if peer.is_online:
                        peer.mark_offline()
                        affected.append(peer)

                        self._logger.info(
                            "Peer marked offline after timeout: %s (%s)",
                            peer.display_name,
                            peer.peer_id,
                        )

        return affected

    # ---------------------------------------------------------
    # Manual operations
    # ---------------------------------------------------------

    def remove_peer(self, peer_id: str) -> Peer | None:
        """
        Remove a peer manually.
        """
        with self._lock:
            peer = self._peers.pop(peer_id, None)

        if peer is not None:
            self._logger.info(
                "Peer removed manually: %s (%s)",
                peer.display_name,
                peer.peer_id,
            )

        return peer

    def mark_peer_offline(self, peer_id: str) -> bool:
        """
        Mark a peer as offline manually.
        """
        with self._lock:
            peer = self._peers.get(peer_id)

            if peer is None:
                return False

            if peer.is_online:
                peer.mark_offline()

                self._logger.info(
                    "Peer marked offline manually: %s (%s)",
                    peer.display_name,
                    peer.peer_id,
                )

        return True

    def clear(self) -> None:
        """
        Remove all peers.
        """
        with self._lock:
            self._peers.clear()

        self._logger.info("All peers cleared from PeerManager.")