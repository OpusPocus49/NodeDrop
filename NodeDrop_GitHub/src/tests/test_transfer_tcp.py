from __future__ import annotations

import shutil
import socket
import sys
import tempfile
import time
import uuid
from pathlib import Path

# Ajoute le dossier src au PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.app_manager import AppManager
from core.models import NodeIdentity, Peer
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


def create_test_file(base_dir: Path) -> Path:
    source_file = base_dir / "sample_input.txt"
    source_file.write_text(
        "NodeDrop integration test\n"
        "Ligne 1\n"
        "Ligne 2\n"
        "Ligne 3\n",
        encoding="utf-8",
    )
    return source_file


def print_directory_tree(base_dir: Path) -> None:
    print()
    print(f"=== CONTENT OF {base_dir} ===")

    if not base_dir.exists():
        print("(directory does not exist)")
        print()
        return

    for path in sorted(base_dir.rglob("*")):
        relative = path.relative_to(base_dir)
        if path.is_dir():
            print(f"[DIR ] {relative}")
        else:
            print(f"[FILE] {relative} ({path.stat().st_size} bytes)")
    print()


def main() -> None:
    setup_logging(level="DEBUG", enable_console=True)

    temp_root = Path(tempfile.mkdtemp(prefix="nodedrop_test_"))
    send_dir = temp_root / "send"
    recv_dir = temp_root / "recv"

    send_dir.mkdir(parents=True, exist_ok=True)
    recv_dir.mkdir(parents=True, exist_ok=True)

    print("=== NodeDrop TCP Transfer Integration Test ===")
    print(f"Working root : {temp_root}")
    print(f"Send dir     : {send_dir}")
    print(f"Receive dir  : {recv_dir}")
    print()

    local_identity = build_test_identity()
    peer = build_loopback_peer()

    app = AppManager(
        local_identity=local_identity,
        shared_password="nodepass",
    )

    source_file = create_test_file(send_dir)

    print(f"Source file  : {source_file}")
    print(f"Peer IP      : {peer.ip_address}")
    print(f"TCP port     : {TRANSFER_TCP_PORT}")
    print()

    try:
        # Injection contrôlée du peer loopback pour éviter toute dépendance
        # à la découverte UDP dans ce test d'intégration local.
        app._peer_manager._peers[peer.peer_id] = peer  # test local assumé

        # Redirige la réception vers notre dossier temporaire de test
        app.transfer_manager.set_receive_directory(recv_dir)

        app.start()
        time.sleep(1.0)

        print("[1] Starting real outgoing transfer with receiver ACK...")
        job_id = app.send_file(
            peer_id=peer.peer_id,
            source_path=source_file,
            password="nodepass",
        )

        print(f"[OK] Transfer job acknowledged and completed: {job_id}")

        # Petite pause de confort pour laisser les derniers logs apparaître
        time.sleep(1.0)

        print_directory_tree(recv_dir)

        received_files = [p for p in recv_dir.rglob("*") if p.is_file()]

        if not received_files:
            raise RuntimeError("No received file found in receive directory.")

        if len(received_files) > 1:
            print("[WARN] More than one file found in receive directory.")
            for file_path in received_files:
                print(f" - {file_path}")

        received_file = received_files[0]

        print(f"[2] Received file found: {received_file}")

        source_content = source_file.read_bytes()
        received_content = received_file.read_bytes()

        if source_content != received_content:
            raise RuntimeError(
                "Received file content does not match source content."
            )

        print("[SUCCESS] File content matches source content.")

        remaining_jobs = app.transfer_manager.get_jobs()
        if remaining_jobs:
            raise RuntimeError(
                f"Transfer jobs should have been cleaned up, but {len(remaining_jobs)} remain."
            )

        print("[SUCCESS] Transfer jobs cleaned up after ACK.")
        print("[SUCCESS] Local transfer integration test passed.")

    finally:
        try:
            app.stop()
        except Exception:
            pass

        print()
        print("Cleaning temporary directories...")
        shutil.rmtree(temp_root, ignore_errors=True)
        print("Done.")


if __name__ == "__main__":
    main()