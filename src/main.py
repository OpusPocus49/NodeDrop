from __future__ import annotations

import socket
import sys
from uuid import uuid4

from PySide6.QtWidgets import QApplication

from core.models import NodeIdentity
from core.app_manager import AppManager
from gui.app_bridge import AppBridge
from gui.main_window import MainWindow
from utils.config import APP_NAME, APP_VERSION, TRANSFER_TCP_PORT
from utils.log_utils import get_log_file, get_logger, setup_logging


def get_local_ip() -> str:
    """
    Best-effort LAN IP detection for NodeDrop V1.
    """
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        test_socket.connect(("8.8.8.8", 80))
        return test_socket.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        test_socket.close()


def build_local_identity() -> NodeIdentity:
    """
    Build the local NodeDrop identity from the current host.
    """
    host_name = socket.gethostname()

    return NodeIdentity(
        node_id=uuid4().hex,
        display_name=host_name,
        host_name=host_name,
        ip_address=get_local_ip(),
        tcp_port=TRANSFER_TCP_PORT,
        version=APP_VERSION,
    )


def main() -> int:
    setup_logging()
    logger = get_logger("main")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    local_identity = build_local_identity()

    # Mot de passe partagé provisoire pour la GUI V1.
    # Une vraie saisie utilisateur sera ajoutée à une étape ultérieure.
    shared_password = "nodedrop"

    app_manager = AppManager(
        local_identity=local_identity,
        shared_password=shared_password,
    )

    bridge = AppBridge(
        app_manager=app_manager,
        local_identity=local_identity,
    )

    window = MainWindow(
        bridge=bridge,
        local_identity=local_identity,
        log_file_path=str(get_log_file()),
    )
    window.show()

    logger.info("%s GUI started.", APP_NAME)
    logger.info("Local identity: %s", local_identity)
    logger.info("Log file location: %s", get_log_file())

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())