from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Generator, Iterable
from uuid import uuid4

from core.models import (
    TransferFile,
    TransferJob,
    TransferProgress,
    TransferStatus,
)
from network.protocol import MessageType, create_message
from utils.file_utils import (
    DEFAULT_FILE_CHUNK_SIZE,
    FileWriteError,
    build_transfer_manifest,
    open_file_for_writing,
    read_file_chunks,
)
from utils.log_utils import get_logger


class TransferManagerError(Exception):
    pass


class TransferNotFoundError(TransferManagerError):
    pass


class TransferStateError(TransferManagerError):
    pass


class TransferIntegrityError(TransferManagerError):
    pass


@dataclass(slots=True)
class _IncomingFileState:
    job_id: str
    relative_path: Path
    destination_path: Path
    expected_size: int
    expected_checksum: str | None
    file_handle: BinaryIO
    hasher: Any
    received_bytes: int = 0
    started_at: float = 0.0
    is_completed: bool = False


class TransferManager:
    def __init__(self, downloads_dir: str | Path = "downloads") -> None:
        self._logger = get_logger("core.transfer_manager")
        self._downloads_dir = Path(downloads_dir)

        self._active_transfers: dict[str, TransferJob] = {}
        self._incoming_files: dict[str, _IncomingFileState] = {}

    @property
    def downloads_dir(self) -> Path:
        return self._downloads_dir

    def set_receive_directory(self, downloads_dir: str | Path) -> None:
        self._downloads_dir = Path(downloads_dir)
        self._logger.info(
            "TransferManager receive directory updated to '%s'.",
            self._downloads_dir,
        )

    def get_job(self, job_id: str) -> TransferJob:
        try:
            return self._active_transfers[job_id]
        except KeyError as exc:
            raise TransferNotFoundError(f"Unknown transfer job: {job_id}") from exc

    def get_jobs(self) -> list[TransferJob]:
        return list(self._active_transfers.values())

    def cleanup_finished_transfers(self) -> list[str]:
        removable_statuses = {
            TransferStatus.COMPLETED,
            TransferStatus.FAILED,
            TransferStatus.CANCELLED,
        }

        removed_job_ids: list[str] = []

        for job_id, job in list(self._active_transfers.items()):
            if job.status in removable_statuses:
                self._active_transfers.pop(job_id, None)
                self._incoming_files.pop(job_id, None)
                removed_job_ids.append(job_id)

        if removed_job_ids:
            self._logger.info(
                "Cleaned up %d finished transfer job(s): %s",
                len(removed_job_ids),
                ", ".join(removed_job_ids),
            )

        return removed_job_ids

    # ============================================================
    # Outgoing transfer preparation
    # ============================================================

    def start_transfer(
        self,
        session_id: str,
        source_peer_id: str,
        target_peer_id: str,
        source_path: str | Path | Iterable[str | Path],
        job_id: str | None = None,
        remote_display_name: str | None = None,
        remote_ip_address: str | None = None,
    ) -> TransferJob:
        sources = self._normalize_sources(source_path)
        items, total_bytes = build_transfer_manifest(sources)

        if not items:
            raise TransferManagerError("Cannot create a transfer job with no files.")

        final_job_id = job_id or self._generate_job_id()

        job = TransferJob(
            job_id=final_job_id,
            session_id=session_id,
            source_peer_id=source_peer_id,
            target_peer_id=target_peer_id,
            items=items,
            remote_display_name=remote_display_name,
            remote_ip_address=remote_ip_address,
        )
        job.total_bytes = total_bytes
        job.start()

        self._active_transfers[job.job_id] = job

        self._logger.info(
            "Prepared outgoing transfer job %s with %d file(s), total_bytes=%d.",
            job.job_id,
            len(job.items),
            job.total_bytes,
        )

        return job

    def cancel_transfer(self, job_id: str, reason: str = "Transfer cancelled by sender.") -> TransferJob:
        job = self.get_job(job_id)

        if job.status in {TransferStatus.COMPLETED, TransferStatus.FAILED, TransferStatus.CANCELLED}:
            return job

        for item in job.items:
            if item.status == TransferStatus.RUNNING:
                item.mark_cancelled(reason)

        job.cancel(reason)

        self._logger.info(
            "Transfer job %s cancelled: %s",
            job.job_id,
            reason,
        )

        return job

    def iter_job_files(self, job_id: str) -> Generator[TransferFile, None, None]:
        job = self.get_job(job_id)

        for item in job.items:
            if job.status == TransferStatus.CANCELLED:
                raise TransferStateError(f"Transfer job {job.job_id} is cancelled.")
            yield item

    def build_transfer_init_message(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)

        return create_message(
            MessageType.TRANSFER_INIT,
            session_id=job.session_id,
            job_id=job.job_id,
            item_count=len(job.items),
            total_bytes=job.total_bytes,
        )

    def build_file_info_message(
        self,
        job_id: str,
        relative_path: str | Path | None = None,
    ) -> dict[str, Any]:
        job = self.get_job(job_id)
        file_item = self._select_outgoing_file(job, relative_path)

        return create_message(
            MessageType.FILE_INFO,
            session_id=job.session_id,
            job_id=job.job_id,
            relative_path=file_item.relative_path.as_posix(),
            item_type="FILE",
            size_bytes=file_item.size_bytes,
            checksum=file_item.checksum,
        )

    def iter_file_chunks(
        self,
        job_id: str,
        relative_path: str | Path | None = None,
        chunk_size: int = DEFAULT_FILE_CHUNK_SIZE,
    ) -> Generator[tuple[dict[str, Any], bytes], None, None]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0.")

        job = self.get_job(job_id)

        if job.status == TransferStatus.CANCELLED:
            raise TransferStateError(f"Transfer job {job.job_id} is cancelled.")

        file_item = self._select_outgoing_file(job, relative_path)

        if file_item.path is None:
            raise TransferStateError(
                f"Outgoing file item has no source path: {file_item.relative_path}"
            )

        if file_item.started_at is None:
            file_item.mark_started()

        self._logger.info(
            "Starting chunk iteration for job %s file '%s' with chunk_size=%d.",
            job.job_id,
            file_item.relative_path.as_posix(),
            chunk_size,
        )

        for chunk in read_file_chunks(file_item.path, chunk_size=chunk_size):
            if job.status == TransferStatus.CANCELLED:
                file_item.mark_cancelled("Transfer cancelled during file streaming.")
                raise TransferStateError(f"Transfer job {job.job_id} is cancelled.")

            chunk_message = create_message(
                MessageType.FILE_CHUNK,
                session_id=job.session_id,
                job_id=job.job_id,
                relative_path=file_item.relative_path.as_posix(),
                chunk_size=len(chunk),
            )

            file_item.set_bytes_sent(file_item.bytes_sent + len(chunk))
            job.set_transferred_bytes(job.transferred_bytes + len(chunk))

            yield chunk_message, chunk

    def build_file_complete_message(
        self,
        job_id: str,
        relative_path: str | Path | None = None,
    ) -> dict[str, Any]:
        job = self.get_job(job_id)

        if job.status == TransferStatus.CANCELLED:
            raise TransferStateError(f"Transfer job {job.job_id} is cancelled.")

        file_item = self._select_outgoing_file(job, relative_path)
        file_item.mark_completed()

        return create_message(
            MessageType.FILE_COMPLETE,
            session_id=job.session_id,
            job_id=job.job_id,
            relative_path=file_item.relative_path.as_posix(),
        )

    def build_transfer_complete_message(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)

        if job.status == TransferStatus.CANCELLED:
            raise TransferStateError(f"Transfer job {job.job_id} is cancelled.")

        return create_message(
            MessageType.TRANSFER_COMPLETE,
            session_id=job.session_id,
            job_id=job.job_id,
        )

    def build_transfer_ack_message(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)

        return create_message(
            MessageType.TRANSFER_ACK,
            session_id=job.session_id,
            job_id=job.job_id,
        )

    def build_transfer_error_message(
        self,
        job_id: str,
        error_message: str,
    ) -> dict[str, Any]:
        job = self.get_job(job_id)
        job.fail(error_message)

        self._logger.error(
            "Transfer job %s failed: %s",
            job.job_id,
            error_message,
        )

        return create_message(
            MessageType.TRANSFER_ERROR,
            session_id=job.session_id,
            job_id=job.job_id,
            error_message=error_message,
        )

    def build_transfer_cancel_message(
        self,
        job_id: str,
        reason: str = "Transfer cancelled by sender.",
    ) -> dict[str, Any]:
        job = self.cancel_transfer(job_id, reason)

        return create_message(
            MessageType.TRANSFER_CANCEL,
            session_id=job.session_id,
            job_id=job.job_id,
            reason=reason,
        )

    def handle_transfer_ack(self, message: dict[str, Any]) -> TransferJob:
        job = self.get_job(message["job_id"])
        job.complete()

        self._logger.info(
            "Outgoing transfer job %s acknowledged and completed.",
            job.job_id,
        )

        return job

    # ============================================================
    # Incoming transfer handling
    # ============================================================

    def handle_transfer_init(
        self,
        message: dict[str, Any],
        source_peer_id: str,
        target_peer_id: str,
        remote_display_name: str | None = None,
        remote_ip_address: str | None = None,
    ) -> TransferJob:
        job_id = message["job_id"]

        if job_id in self._active_transfers:
            existing_job = self._active_transfers[job_id]

            if (
                existing_job.source_peer_id == source_peer_id
                and existing_job.target_peer_id == target_peer_id
            ):
                self._logger.debug(
                    "Ignoring duplicate TRANSFER_INIT for existing job %s.",
                    job_id,
                )
                return existing_job

            raise TransferStateError(f"Transfer job already exists: {job_id}")

        job = TransferJob(
            job_id=job_id,
            session_id=message["session_id"],
            source_peer_id=source_peer_id,
            target_peer_id=target_peer_id,
            items=[],
            remote_display_name=remote_display_name,
            remote_ip_address=remote_ip_address,
        )
        job.total_bytes = message["total_bytes"]
        job.start()

        self._active_transfers[job_id] = job

        self._logger.info(
            "Registered incoming transfer job %s (total_bytes=%d).",
            job.job_id,
            job.total_bytes,
        )

        return job

    def handle_file_info(self, message: dict[str, Any]) -> TransferFile:
        job = self.get_job(message["job_id"])

        if job.status == TransferStatus.CANCELLED:
            raise TransferStateError(f"Job {job.job_id} is cancelled.")

        if job.job_id in self._incoming_files:
            raise TransferStateError(
                f"Job {job.job_id} already has an active incoming file."
            )

        relative_path = self._normalize_relative_transfer_path(message["relative_path"])
        destination_path = self._downloads_dir / relative_path

        try:
            file_handle = open_file_for_writing(destination_path)
        except FileWriteError as exc:
            raise TransferManagerError(str(exc)) from exc

        hasher = hashlib.sha256()

        transfer_file = self._find_job_item(job, relative_path)
        if transfer_file is None:
            transfer_file = TransferFile(
                path=destination_path,
                relative_path=relative_path,
                size_bytes=message["size_bytes"],
                checksum=message.get("checksum"),
            )
            job.items.append(transfer_file)
        else:
            transfer_file.path = destination_path
            transfer_file.size_bytes = message["size_bytes"]
            transfer_file.checksum = message.get("checksum")

        transfer_file.mark_started()

        self._incoming_files[job.job_id] = _IncomingFileState(
            job_id=job.job_id,
            relative_path=relative_path,
            destination_path=destination_path,
            expected_size=message["size_bytes"],
            expected_checksum=message.get("checksum"),
            file_handle=file_handle,
            hasher=hasher,
            started_at=time.time(),
        )

        self._logger.info(
            "Prepared incoming file for job %s at '%s' (%d bytes expected).",
            job.job_id,
            destination_path,
            message["size_bytes"],
        )

        return transfer_file

    def handle_file_chunk(self, message: dict[str, Any], chunk_data: bytes) -> int:
        if not isinstance(chunk_data, (bytes, bytearray, memoryview)):
            raise TypeError("chunk_data must be bytes-like.")

        job = self.get_job(message["job_id"])

        if job.status == TransferStatus.CANCELLED:
            raise TransferStateError(f"Job {job.job_id} is cancelled.")

        incoming_state = self._get_incoming_state(job.job_id)

        relative_path = self._normalize_relative_transfer_path(message["relative_path"])
        if relative_path != incoming_state.relative_path:
            raise TransferStateError(
                "Received FILE_CHUNK for an unexpected relative_path."
            )

        expected_chunk_size = message["chunk_size"]
        actual_chunk_size = len(chunk_data)

        if actual_chunk_size != expected_chunk_size:
            raise TransferStateError(
                f"Chunk size mismatch: expected {expected_chunk_size}, received {actual_chunk_size}."
            )

        try:
            written = incoming_state.file_handle.write(chunk_data)
        except OSError as exc:
            raise TransferManagerError(
                f"Failed to write incoming chunk to disk for {relative_path.as_posix()}."
            ) from exc

        incoming_state.hasher.update(chunk_data)
        incoming_state.received_bytes += written

        transfer_file = self._require_job_item(job, relative_path)
        transfer_file.set_bytes_received(incoming_state.received_bytes)

        job.set_transferred_bytes(job.transferred_bytes + written)

        return written

    def handle_file_complete(self, message: dict[str, Any]) -> TransferFile:
        job = self.get_job(message["job_id"])
        incoming_state = self._get_incoming_state(job.job_id)

        relative_path = self._normalize_relative_transfer_path(message["relative_path"])
        if relative_path != incoming_state.relative_path:
            raise TransferStateError(
                "Received FILE_COMPLETE for an unexpected relative_path."
            )

        transfer_file = self._require_job_item(job, relative_path)

        try:
            incoming_state.file_handle.flush()
        finally:
            incoming_state.file_handle.close()

        actual_size = incoming_state.received_bytes
        if actual_size != incoming_state.expected_size:
            transfer_file.mark_failed("size mismatch")
            self._incoming_files.pop(job.job_id, None)
            raise TransferIntegrityError(
                f"Size mismatch for '{relative_path.as_posix()}': "
                f"expected {incoming_state.expected_size}, got {actual_size}."
            )

        actual_checksum = incoming_state.hasher.hexdigest()
        if (
            incoming_state.expected_checksum
            and actual_checksum.lower() != incoming_state.expected_checksum.lower()
        ):
            transfer_file.mark_failed("checksum mismatch")
            self._incoming_files.pop(job.job_id, None)
            raise TransferIntegrityError(
                f"Checksum mismatch for '{relative_path.as_posix()}'."
            )

        transfer_file.set_bytes_received(actual_size)
        transfer_file.mark_completed()

        incoming_state.is_completed = True
        self._incoming_files.pop(job.job_id, None)

        self._logger.info(
            "Incoming file completed for job %s: '%s'.",
            job.job_id,
            relative_path.as_posix(),
        )

        return transfer_file

    def handle_transfer_complete(self, message: dict[str, Any]) -> TransferJob:
        job = self.get_job(message["job_id"])

        if job.status == TransferStatus.CANCELLED:
            return job

        if job.job_id in self._incoming_files:
            raise TransferStateError(
                f"Cannot complete transfer job {job.job_id}: an incoming file is still active."
            )

        if job.total_bytes > 0 and job.transferred_bytes != job.total_bytes:
            raise TransferIntegrityError(
                f"Transfer job {job.job_id} total size mismatch: "
                f"expected {job.total_bytes}, got {job.transferred_bytes}."
            )

        job.complete()

        self._logger.info(
            "Incoming transfer job %s completed successfully.",
            job.job_id,
        )

        return job

    def handle_transfer_error(self, message: dict[str, Any]) -> TransferJob:
        job = self.get_job(message["job_id"])
        error_message = message.get("error_message", "remote transfer error")
        job.fail(error_message)

        incoming_state = self._incoming_files.pop(job.job_id, None)
        if incoming_state is not None:
            try:
                incoming_state.file_handle.close()
            except OSError:
                pass

        self._logger.error(
            "Transfer job %s marked as failed by remote side: %s",
            job.job_id,
            error_message,
        )

        return job

    def handle_transfer_cancel(self, message: dict[str, Any]) -> TransferJob:
        job = self.get_job(message["job_id"])
        reason = message.get("reason", "Transfer cancelled by remote side.")

        incoming_state = self._incoming_files.pop(job.job_id, None)
        if incoming_state is not None:
            try:
                incoming_state.file_handle.close()
            except OSError:
                pass

            partial_item = self._find_job_item(job, incoming_state.relative_path)
            if partial_item is not None:
                partial_item.mark_cancelled(reason)

        for item in job.items:
            if item.status == TransferStatus.RUNNING:
                item.mark_cancelled(reason)

        job.cancel(reason)

        self._logger.info(
            "Transfer job %s cancelled by remote side: %s",
            job.job_id,
            reason,
        )

        return job

    # ============================================================
    # Progress helpers
    # ============================================================

    def build_progress_snapshot(
        self,
        job_id: str,
        relative_path: str | Path | None = None,
    ) -> TransferProgress:
        job = self.get_job(job_id)
        elapsed_seconds = job.elapsed_seconds
        speed_bps = 0.0
        eta_seconds: float | None = None

        if elapsed_seconds > 0 and job.transferred_bytes > 0:
            speed_bps = job.transferred_bytes / elapsed_seconds
            remaining_bytes = max(0, job.total_bytes - job.transferred_bytes)
            if speed_bps > 0:
                eta_seconds = remaining_bytes / speed_bps

        if relative_path is None:
            return job.build_progress(
                file_name=None,
                file_index=max(0, min(job.completed_file_count, job.file_count)),
                file_bytes_done=0,
                file_bytes_total=0,
                speed_bps=speed_bps,
                eta_seconds=eta_seconds,
            )

        normalized_path = self._normalize_relative_transfer_path(relative_path)
        file_item = self._require_job_item(job, normalized_path)
        file_index = self._get_file_index(job, file_item)

        return job.build_progress(
            file_name=file_item.relative_path.as_posix(),
            file_index=file_index,
            file_bytes_done=max(file_item.bytes_sent, file_item.bytes_received),
            file_bytes_total=file_item.size_bytes,
            speed_bps=speed_bps,
            eta_seconds=eta_seconds,
        )

    # ============================================================
    # Internal helpers
    # ============================================================

    def _normalize_sources(
        self,
        source_path: str | Path | Iterable[str | Path],
    ) -> list[Path]:
        if isinstance(source_path, (str, Path)):
            return [Path(source_path)]

        return [Path(item) for item in source_path]

    def _generate_job_id(self) -> str:
        return uuid4().hex

    def _select_outgoing_file(
        self,
        job: TransferJob,
        relative_path: str | Path | None,
    ) -> TransferFile:
        if relative_path is None:
            if len(job.items) != 1:
                raise TransferStateError(
                    "relative_path is required for multi-file jobs."
                )
            return job.items[0]

        normalized_path = self._normalize_relative_transfer_path(relative_path)
        return self._require_job_item(job, normalized_path)

    def _find_job_item(
        self,
        job: TransferJob,
        relative_path: Path,
    ) -> TransferFile | None:
        target = relative_path.as_posix()

        for item in job.items:
            if item.relative_path.as_posix() == target:
                return item

        return None

    def _require_job_item(
        self,
        job: TransferJob,
        relative_path: Path,
    ) -> TransferFile:
        item = self._find_job_item(job, relative_path)
        if item is None:
            raise TransferStateError(
                f"Unknown file '{relative_path.as_posix()}' in job {job.job_id}."
            )
        return item

    def _get_incoming_state(self, job_id: str) -> _IncomingFileState:
        try:
            return self._incoming_files[job_id]
        except KeyError as exc:
            raise TransferStateError(
                f"No active incoming file for job {job_id}."
            ) from exc

    def _get_file_index(self, job: TransferJob, file_item: TransferFile) -> int:
        target = file_item.relative_path.as_posix()
        for index, item in enumerate(job.items, start=1):
            if item.relative_path.as_posix() == target:
                return index
        return 0

    def _normalize_relative_transfer_path(self, path: str | Path) -> Path:
        relative_path = Path(path)

        if relative_path.is_absolute():
            raise TransferStateError("Transfer relative path must not be absolute.")

        if any(part == ".." for part in relative_path.parts):
            raise TransferStateError("Transfer relative path contains path traversal.")

        if str(relative_path).strip() == "":
            raise TransferStateError("Transfer relative path must not be empty.")

        return relative_path