from __future__ import annotations

import socket
import sys
import time
import uuid
from pathlib import Path

# ajoute src au PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.models import NodeIdentity
from network.discovery import DiscoveryService
from utils.config import TRANSFER_TCP_PORT
from utils.log_utils import setup_logging


def detect_local_ip() -> str:
    """
    Best-effort detection of the local LAN IP address.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def on_peer_discovered(message: dict) -> None:
    print()
    print("[PEER DETECTED]")
    print(message)


def build_test_node_id() -> str:
    """
    Build a unique node_id for each test process.
    """
    return f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


def main() -> None:
    setup_logging(level="DEBUG", enable_console=True)

    host_name = socket.gethostname()
    local_ip = detect_local_ip()

    local_identity = NodeIdentity(
        node_id=build_test_node_id(),
        display_name=host_name,
        host_name=host_name,
        ip_address=local_ip,
        tcp_port=TRANSFER_TCP_PORT,
        version="1.0.0-dev",
    )

    service = DiscoveryService(
        local_identity=local_identity,
        on_peer_discovered=on_peer_discovered,
    )

    print("=== NodeDrop Discovery Test ===")
    print(f"Node ID      : {local_identity.node_id}")
    print(f"Display name : {local_identity.display_name}")
    print(f"Host name    : {local_identity.host_name}")
    print(f"IP address   : {local_identity.ip_address}")
    print(f"TCP port     : {local_identity.tcp_port}")
    print()
    print("Discovery service starting for 60 seconds...")
    print("Lance le même test sur une autre machine du LAN pour vérifier la détection.")
    print()

    service.start()

    try:
        time.sleep(60)
    finally:
        service.stop()
        print()
        print("Discovery service stopped.")


if __name__ == "__main__":
    main()