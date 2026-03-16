from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import uuid4


class SessionState(str, Enum):
    """
    Normalized TCP session states for NodeDrop.

    These states describe the lifecycle of the network session itself.
    They must not be confused with transfer job states.
    """

    PENDING = "PENDING"
    REQUESTED = "REQUESTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    AUTHENTICATING = "AUTHENTICATING"
    AUTHENTICATED = "AUTHENTICATED"
    TRANSFERRING = "TRANSFERRING"
    CLOSED = "CLOSED"
    ERROR = "ERROR"


class TransferStatus(str, Enum):
    """
    Lifecycle state of a transfer job.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TransferItemType(str, Enum):
    """
    Type of transferable item handled by NodeDrop.
    """

    FILE = "FILE"
    DIRECTORY = "DIRECTORY"


@dataclass(slots=True)
class NodeIdentity:
    """
    Local application identity.
    """

    node_id: str
    display_name: str
    host_name: str
    ip_address: str
    tcp_port: int
    version: str


@dataclass(slots=True)
class Peer:
    """
    Remote NodeDrop peer discovered on the local network.
    """

    peer_id: str
    display_name: str
    host_name: str
    ip_address: str
    tcp_port: int
    version: str
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_online: bool = True

    def refresh_last_seen(self) -> None:
        self.last_seen = datetime.now(UTC)
        self.is_online = True

    def mark_offline(self) -> None:
        self.is_online = False


@dataclass(slots=True)
class TransferFile:
    """
    Representation of a single transferable item inside a transfer job.
    """

    relative_path: Path
    item_type: TransferItemType = TransferItemType.FILE
    path: Optional[Path] = None
    size_bytes: int = 0
    checksum: Optional[str] = None

    status: TransferStatus = TransferStatus.PENDING

    bytes_sent: int = 0
    bytes_received: int = 0

    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error_message: Optional[str] = None

    @property
    def name(self) -> str:
        return self.relative_path.name

    @property
    def is_file(self) -> bool:
        return self.item_type == TransferItemType.FILE

    @property
    def is_directory(self) -> bool:
        return self.item_type == TransferItemType.DIRECTORY

    @property
    def progress_percent(self) -> float:
        if self.size_bytes <= 0:
            return 0.0

        current = max(self.bytes_sent, self.bytes_received)
        if current <= 0:
            return 0.0

        if current >= self.size_bytes:
            return 100.0

        return (current / self.size_bytes) * 100.0

    def mark_started(self) -> None:
        self.started_at = time.time()
        self.status = TransferStatus.RUNNING
        self.error_message = None

    def mark_completed(self) -> None:
        self.finished_at = time.time()
        self.status = TransferStatus.COMPLETED
        self.error_message = None

        if self.size_bytes > 0:
            self.bytes_sent = min(self.bytes_sent, self.size_bytes)
            self.bytes_received = min(self.bytes_received, self.size_bytes)

    def mark_failed(self, message: str) -> None:
        self.finished_at = time.time()
        self.status = TransferStatus.FAILED
        self.error_message = message

    def mark_cancelled(self, message: str | None = None) -> None:
        self.finished_at = time.time()
        self.status = TransferStatus.CANCELLED
        if message is not None:
            self.error_message = message

    def set_bytes_sent(self, value: int) -> None:
        if value < 0:
            self.bytes_sent = 0
            return

        if self.size_bytes > 0:
            self.bytes_sent = min(value, self.size_bytes)
            return

        self.bytes_sent = value

    def set_bytes_received(self, value: int) -> None:
        if value < 0:
            self.bytes_received = 0
            return

        if self.size_bytes > 0:
            self.bytes_received = min(value, self.size_bytes)
            return

        self.bytes_received = value


@dataclass(slots=True)
class TransferProgress:
    """
    Runtime transfer progress snapshot.
    """

    job_id: str
    session_id: str
    remote_display_name: Optional[str]
    remote_ip_address: Optional[str]
    file_name: Optional[str]
    file_index: int
    file_count: int
    completed_file_count: int
    failed_file_count: int
    bytes_done: int
    bytes_total: int
    job_bytes_done: int
    job_bytes_total: int
    progress_percent: float
    speed_bps: float
    eta_seconds: Optional[float]
    elapsed_seconds: float


@dataclass(slots=True)
class TransferJob:
    """
    Global representation of a transfer operation.
    """

    job_id: str
    session_id: str
    source_peer_id: str
    target_peer_id: str

    items: list[TransferFile] = field(default_factory=list)

    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    status: TransferStatus = TransferStatus.PENDING
    error_message: Optional[str] = None

    total_bytes: int = 0
    transferred_bytes: int = 0

    remote_display_name: Optional[str] = None
    remote_ip_address: Optional[str] = None

    def add_item(self, item: TransferFile) -> None:
        self.items.append(item)

        if item.is_file:
            self.total_bytes += item.size_bytes

    def compute_total_size(self) -> int:
        return sum(item.size_bytes for item in self.items if item.is_file)

    def recompute_total_bytes(self) -> int:
        self.total_bytes = self.compute_total_size()
        return self.total_bytes

    def start(self) -> None:
        self.started_at = time.time()
        self.status = TransferStatus.RUNNING
        self.error_message = None

    def complete(self) -> None:
        self.completed_at = time.time()
        self.transferred_bytes = self.total_bytes
        self.status = TransferStatus.COMPLETED
        self.error_message = None

    def fail(self, message: str) -> None:
        self.completed_at = time.time()
        self.status = TransferStatus.FAILED
        self.error_message = message

    def cancel(self, message: str | None = None) -> None:
        self.completed_at = time.time()
        self.status = TransferStatus.CANCELLED
        if message is not None:
            self.error_message = message

    def set_transferred_bytes(self, value: int) -> None:
        if value < 0:
            self.transferred_bytes = 0
            return

        if self.total_bytes > 0:
            self.transferred_bytes = min(value, self.total_bytes)
            return

        self.transferred_bytes = value

    @property
    def progress_percent(self) -> float:
        if self.total_bytes <= 0:
            return 0.0

        return (self.transferred_bytes / self.total_bytes) * 100.0

    @property
    def file_count(self) -> int:
        return len(self.items)

    @property
    def completed_file_count(self) -> int:
        return sum(1 for item in self.items if item.status == TransferStatus.COMPLETED)

    @property
    def failed_file_count(self) -> int:
        return sum(1 for item in self.items if item.status == TransferStatus.FAILED)

    @property
    def cancelled_file_count(self) -> int:
        return sum(1 for item in self.items if item.status == TransferStatus.CANCELLED)

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0

        end_time = self.completed_at if self.completed_at is not None else time.time()
        return max(0.0, end_time - self.started_at)

    def build_progress(
        self,
        file_name: Optional[str] = None,
        file_index: int = 0,
        file_bytes_done: int = 0,
        file_bytes_total: int = 0,
        speed_bps: float = 0.0,
        eta_seconds: Optional[float] = None,
    ) -> TransferProgress:
        return TransferProgress(
            job_id=self.job_id,
            session_id=self.session_id,
            remote_display_name=self.remote_display_name,
            remote_ip_address=self.remote_ip_address,
            file_name=file_name,
            file_index=file_index,
            file_count=self.file_count,
            completed_file_count=self.completed_file_count,
            failed_file_count=self.failed_file_count,
            bytes_done=file_bytes_done,
            bytes_total=file_bytes_total,
            job_bytes_done=self.transferred_bytes,
            job_bytes_total=self.total_bytes,
            progress_percent=self.progress_percent,
            speed_bps=speed_bps,
            eta_seconds=eta_seconds,
            elapsed_seconds=self.elapsed_seconds,
        )


def generate_session_id() -> str:
    return uuid4().hex


def generate_transfer_job_id() -> str:
    return uuid4().hex