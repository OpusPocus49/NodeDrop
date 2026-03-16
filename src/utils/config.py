from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

# ============================================================
# Application metadata
# ============================================================

APP_NAME: Final[str] = "NodeDrop"
APP_VERSION: Final[str] = "1.0.0-dev"

# ============================================================
# Network configuration (application-level defaults)
# These values are configurable application parameters.
# Protocol message types and validation rules must stay in
# network/protocol.py.
# ============================================================

DISCOVERY_UDP_PORT: Final[int] = 48555
TRANSFER_TCP_PORT: Final[int] = 48556

DISCOVERY_BROADCAST_IP: Final[str] = "192.168.1.255"
DISCOVERY_INTERVAL_SECONDS: Final[int] = 5
PEER_EXPIRY_SECONDS: Final[int] = 15

TCP_CONNECT_TIMEOUT_SECONDS: Final[int] = 5
TCP_READ_TIMEOUT_SECONDS: Final[int] = 10
TCP_WRITE_TIMEOUT_SECONDS: Final[int] = 10
MAX_PENDING_CONNECTIONS: Final[int] = 5

# 4 MiB, aligned with the V1 protocol documentation.
TRANSFER_BLOCK_SIZE: Final[int] = 4 * 1024 * 1024

# ============================================================
# Transfer and session defaults
# ============================================================

DEFAULT_BUFFER_SIZE: Final[int] = 64 * 1024
SESSION_ID_LENGTH: Final[int] = 32

# ============================================================
# Logging configuration
# ============================================================

LOG_DIRECTORY_NAME: Final[str] = "logs"
LOG_FILE_NAME: Final[str] = "nodedrop.log"
LOG_MAX_BYTES: Final[int] = 5 * 1024 * 1024
LOG_BACKUP_COUNT: Final[int] = 3
LOG_LEVEL: Final[str] = "INFO"

# ============================================================
# Runtime directories
# The application is intended to be portable. For a frozen build
# (PyInstaller), runtime data is stored next to the executable.
# During development, runtime data is stored at the project root.
# ============================================================

RUNTIME_DIRECTORY_NAME: Final[str] = "runtime"
RECEIVED_FILES_DIRECTORY_NAME: Final[str] = "received"

# ============================================================
# UI / refresh defaults
# ============================================================

UI_REFRESH_INTERVAL_MS: Final[int] = 500

# ============================================================
# Helpers
# ============================================================


def is_frozen() -> bool:
    """
    Return True when the application runs from a frozen executable
    (for example with PyInstaller).
    """
    return getattr(sys, "frozen", False) is True


def get_base_directory() -> Path:
    """
    Return the base directory used by the application.

    Development mode:
        project_root/

    Frozen mode:
        directory containing the executable
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent

    # src/utils/config.py -> utils -> src -> project_root
    return Path(__file__).resolve().parents[2]


def get_runtime_directory() -> Path:
    """
    Return the runtime directory used to store mutable application data.
    """
    return get_base_directory() / RUNTIME_DIRECTORY_NAME


def get_logs_directory() -> Path:
    """
    Return the logs directory.
    """
    return get_runtime_directory() / LOG_DIRECTORY_NAME


def get_received_files_directory() -> Path:
    """
    Return the default directory used to store received files.
    """
    return get_runtime_directory() / RECEIVED_FILES_DIRECTORY_NAME


def get_log_file_path() -> Path:
    """
    Return the main application log file path.
    """
    return get_logs_directory() / LOG_FILE_NAME


def ensure_runtime_directories() -> None:
    """
    Create runtime directories if they do not already exist.
    """
    get_runtime_directory().mkdir(parents=True, exist_ok=True)
    get_logs_directory().mkdir(parents=True, exist_ok=True)
    get_received_files_directory().mkdir(parents=True, exist_ok=True)