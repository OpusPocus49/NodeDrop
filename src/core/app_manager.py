from __future__ import annotations

import socket
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable

from core.auth_manager import AuthManager
from core.models import NodeIdentity, Peer, TransferJob, TransferProgress
from core.peer_manager import PeerManager
from core.transfer_manager import TransferManager
from network.discovery import DiscoveryService
from network.listener import SessionListener
from network.protocol import MessageType, create_message, message_has_type
from network.session import SessionClient

try:
    from network.session import SessionCancelledError
except ImportError:  # backward compatibility with older session.py snapshots
    class SessionCancelledError(RuntimeError):
        pass
from utils.log_utils import get_logger

PeersUpdatedCallback = Callable[[list[Peer]], None]
SessionRequestCallback = Callable[[dict[str, Any], tuple[str, int]], dict[str, Any] | None]

TransferStartedCallback = Callable[[TransferJob], None]
TransferProgressCallback = Callable[[TransferProgress], None]
TransferCompletedCallback = Callable[[TransferJob], None]
TransferFailedCallback = Callable[[TransferJob, str], None]


class AppManager:
    def __init__(
        self,
        local_identity: NodeIdentity,
        shared_password: str,
        on_peers_updated: PeersUpdatedCallback | None = None,
        on_session_requested: SessionRequestCallback | None = None,
        on_transfer_started: TransferStartedCallback | None = None,
        on_transfer_progress: TransferProgressCallback | None = None,
        on_transfer_completed: TransferCompletedCallback | None = None,
        on_transfer_failed: TransferFailedCallback | None = None,
    ) -> None:
        self._logger = get_logger("core.app_manager")
        self._local_identity = local_identity
        self._shared_password = shared_password

        self._peer_manager = PeerManager()
        self._auth_manager = AuthManager(shared_password=shared_password)
        self._session_client = SessionClient(local_identity=local_identity)
        self._transfer_manager = TransferManager()

        self._discovery_service = DiscoveryService(
            local_identity=local_identity,
            on_peer_discovered=self._handle_peer_discovered,
        )

        try:
            self._session_listener = SessionListener(
                on_session_requested=self._handle_session_requested,
                on_auth_response=self._handle_auth_response,
                on_transfer_message=self._handle_transfer_message,
            )
        except TypeError:
            self._session_listener = SessionListener(
                on_session_requested=self._handle_session_requested,
                on_auth_response=self._handle_auth_response,
            )

        self._on_peers_updated = on_peers_updated
        self._on_session_requested = on_session_requested

        self._on_transfer_started = on_transfer_started
        self._on_transfer_progress = on_transfer_progress
        self._on_transfer_completed = on_transfer_completed
        self._on_transfer_failed = on_transfer_failed

        self._lock = threading.Lock()
        self._running = False

        self._transfer_control_lock = threading.Lock()
        self._active_outgoing_job_id: str | None = None
        self._active_transfer_cancel_event = threading.Event()
        self._active_outgoing_socket: socket.socket | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def transfer_manager(self) -> TransferManager:
        return self._transfer_manager

    def start(self) -> None:
        with self._lock:
            if self._running:
                self._logger.warning("AppManager is already running.")
                return

            self._logger.info("Starting AppManager services.")
            self._running = True

        try:
            self._session_listener.start()
            self._discovery_service.start()
            self._logger.info("AppManager services started successfully.")
        except Exception:
            self._logger.exception("Failed to start AppManager services.")
            self.stop()
            raise

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                self._logger.warning("AppManager is not running.")
                return

            self._logger.info("Stopping AppManager services.")
            self._running = False

        try:
            self._discovery_service.stop()
        except Exception:
            self._logger.exception("Error while stopping DiscoveryService.")

        try:
            self._session_listener.stop()
        except Exception:
            self._logger.exception("Error while stopping SessionListener.")

        self._logger.info("AppManager stopped.")

    def set_on_peers_updated(self, callback: PeersUpdatedCallback | None) -> None:
        self._on_peers_updated = callback

    def set_on_session_requested(self, callback: SessionRequestCallback | None) -> None:
        self._on_session_requested = callback

    def set_on_transfer_started(self, callback: TransferStartedCallback | None) -> None:
        self._on_transfer_started = callback

    def set_on_transfer_progress(self, callback: TransferProgressCallback | None) -> None:
        self._on_transfer_progress = callback

    def set_on_transfer_completed(self, callback: TransferCompletedCallback | None) -> None:
        self._on_transfer_completed = callback

    def set_on_transfer_failed(self, callback: TransferFailedCallback | None) -> None:
        self._on_transfer_failed = callback

    def get_peers(self, online_only: bool = False) -> list[Peer]:
        return self._peer_manager.get_peers(online_only=online_only)

    def get_peer(self, peer_id: str) -> Peer | None:
        return self._peer_manager.get_peer(peer_id)

    def cleanup_expired_peers(self, remove: bool = False) -> list[Peer]:
        affected = self._peer_manager.cleanup_expired(remove=remove)

        if affected:
            self._logger.info(
                "Peer cleanup affected %d peer(s).",
                len(affected),
            )
            self._notify_peers_updated()

        return affected

    def cleanup_finished_transfers(self) -> list[str]:
        return self._transfer_manager.cleanup_finished_transfers()

    def update_shared_password(self, new_password: str) -> None:
        self._auth_manager.update_password(new_password)
        self._shared_password = new_password
        self._logger.info("AppManager shared password updated.")

    def request_session(self, peer_id: str, password: str | None = None) -> dict[str, Any]:
        peer = self._peer_manager.get_peer(peer_id)
        if peer is None:
            raise ValueError(f"Unknown peer_id: {peer_id}")

        session_id = self._generate_session_id()
        outgoing_password = self._resolve_outgoing_password(password)

        self._logger.info(
            "Requesting authenticated session to peer %s (%s), session_id=%s",
            peer.display_name,
            peer.peer_id,
            session_id,
        )

        response = self._session_client.request_session(
            peer=peer,
            session_id=session_id,
            password=outgoing_password,
        )

        self._logger.info(
            "Final session/auth response received from peer %s (%s): %s",
            peer.display_name,
            peer.peer_id,
            response.get("type"),
        )

        return response

    def send_file(
        self,
        peer_id: str,
        source_path: str | Path,
        password: str | None = None,
    ) -> str:
        return self.send_transfer(
            peer_id=peer_id,
            source_paths=source_path,
            password=password,
        )

    def cancel_active_transfer(self, reason: str = "Transfert annulé par l'utilisateur.") -> TransferJob | None:
        with self._transfer_control_lock:
            active_job_id = self._active_outgoing_job_id
            active_socket = self._active_outgoing_socket

            if active_job_id is None:
                return None

            self._active_transfer_cancel_event.set()

        job = self._transfer_manager.cancel_transfer(active_job_id, reason)
        self._logger.info("Cancellation requested for active transfer job %s.", active_job_id)

        if active_socket is not None:
            try:
                active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            try:
                active_socket.close()
            except OSError:
                pass

            self._logger.info(
                "Active outgoing socket force-closed for cancelled job %s.",
                active_job_id,
            )

        return job

    def send_transfer(
        self,
        peer_id: str,
        source_paths: str | Path | Iterable[str | Path],
        password: str | None = None,
        cancel_after_chunks: int | None = None,
    ) -> str:
        peer = self._peer_manager.get_peer(peer_id)
        if peer is None:
            raise ValueError(f"Unknown peer_id: {peer_id}")

        session_id = self._generate_session_id()
        outgoing_password = self._resolve_outgoing_password(password)

        self._logger.info(
            "Opening authenticated transfer session to peer %s (%s), session_id=%s",
            peer.display_name,
            peer.peer_id,
            session_id,
        )

        job = self._transfer_manager.start_transfer(
            session_id=session_id,
            source_peer_id=self._local_identity.node_id,
            target_peer_id=peer.peer_id,
            source_path=source_paths,
            remote_display_name=peer.display_name,
            remote_ip_address=peer.ip_address,
        )
        self._set_active_outgoing_job_id(job.job_id)

        self._emit_transfer_started(job)

        sock = None
        chunks_sent = 0
        ack_received = False
        session_close_sent = False
        transfer_error_sent = False
        transfer_cancel_sent = False
        completed_job_id: str | None = None

        try:
            sock, auth_response = self._session_client.open_authenticated_session(
                peer=peer,
                session_id=session_id,
                password=outgoing_password,
            )
            self._set_active_outgoing_socket(sock)

            if not message_has_type(auth_response, MessageType.AUTH_SUCCESS):
                raise RuntimeError(
                    "open_authenticated_session() returned a non-success final response."
                )

            transfer_init_message = self._transfer_manager.build_transfer_init_message(job.job_id)
            self._session_client.send_message(sock, transfer_init_message)

            for file_item in self._transfer_manager.iter_job_files(job.job_id):
                self._raise_if_active_transfer_cancelled()

                file_info_message = self._transfer_manager.build_file_info_message(
                    job.job_id,
                    relative_path=file_item.relative_path,
                )
                self._session_client.send_message(sock, file_info_message)

                self._emit_transfer_progress(
                    self._transfer_manager.build_progress_snapshot(
                        job.job_id,
                        relative_path=file_item.relative_path,
                    )
                )

                for chunk_message, chunk_data in self._transfer_manager.iter_file_chunks(
                    job.job_id,
                    relative_path=file_item.relative_path,
                ):
                    self._raise_if_active_transfer_cancelled()

                    self._session_client.send_message(sock, chunk_message)
                    self._session_client.send_bytes(sock, chunk_data)

                    chunks_sent += 1

                    self._emit_transfer_progress(
                        self._transfer_manager.build_progress_snapshot(
                            job.job_id,
                            relative_path=file_item.relative_path,
                        )
                    )

                    self._raise_if_active_transfer_cancelled()

                    if (
                        cancel_after_chunks is not None
                        and chunks_sent >= cancel_after_chunks
                    ):
                        cancel_message = self._transfer_manager.build_transfer_cancel_message(
                            job.job_id,
                            "Transfer cancelled by sender.",
                        )
                        self._session_client.send_message(sock, cancel_message)
                        transfer_cancel_sent = True
                        cancelled_job = self._transfer_manager.get_job(job.job_id)
                        self._emit_transfer_failed(
                            cancelled_job,
                            "Transfer cancelled by sender.",
                        )
                        self._transfer_manager.cleanup_finished_transfers()
                        return cancelled_job.job_id

                self._raise_if_active_transfer_cancelled()

                file_complete_message = self._transfer_manager.build_file_complete_message(
                    job.job_id,
                    relative_path=file_item.relative_path,
                )
                self._session_client.send_message(sock, file_complete_message)

                self._emit_transfer_progress(
                    self._transfer_manager.build_progress_snapshot(
                        job.job_id,
                        relative_path=file_item.relative_path,
                    )
                )

            self._raise_if_active_transfer_cancelled()

            transfer_complete_message = self._transfer_manager.build_transfer_complete_message(
                job.job_id
            )
            self._session_client.send_message(sock, transfer_complete_message)

            ack_message = self._session_client.receive_message(sock)

            if message_has_type(ack_message, MessageType.TRANSFER_ACK):
                if ack_message.get("job_id") != job.job_id:
                    raise RuntimeError(
                        "Received TRANSFER_ACK for an unexpected job_id."
                    )

                ack_received = True
                completed_job = self._transfer_manager.handle_transfer_ack(ack_message)

                session_close_message = create_message(
                    MessageType.SESSION_CLOSE,
                    session_id=session_id,
                )
                self._session_client.send_message(sock, session_close_message)
                session_close_sent = True

                self._emit_transfer_completed(completed_job)
                completed_job_id = completed_job.job_id
                self._transfer_manager.cleanup_finished_transfers()
                return completed_job.job_id

            if message_has_type(ack_message, MessageType.TRANSFER_ERROR):
                failed_job = self._transfer_manager.handle_transfer_error(ack_message)
                self._emit_transfer_failed(
                    failed_job,
                    ack_message.get("error_message", "remote transfer error"),
                )
                raise RuntimeError(
                    f"Remote peer reported TRANSFER_ERROR: {ack_message.get('error_message')}"
                )

            if message_has_type(ack_message, MessageType.TRANSFER_CANCEL):
                cancelled_job = self._transfer_manager.handle_transfer_cancel(ack_message)
                self._emit_transfer_failed(
                    cancelled_job,
                    ack_message.get("reason", "Transfer cancelled by remote side."),
                )
                self._transfer_manager.cleanup_finished_transfers()
                return cancelled_job.job_id

            raise RuntimeError(
                f"Unexpected post-transfer response received: {ack_message.get('type')!r}"
            )

        except Exception as exc:
            try:
                current_job = self._transfer_manager.get_job(job.job_id)
            except Exception:
                current_job = job

            if self._is_expected_cancellation_exception(exc, current_job):
                cancellation_reason = current_job.error_message or "Transfert annulé par l'utilisateur."
                self._logger.info(
                    "Outgoing transfer cancelled for peer %s (%s), session_id=%s, job_id=%s: %s",
                    peer.display_name,
                    peer.peer_id,
                    session_id,
                    job.job_id,
                    cancellation_reason,
                )
                self._emit_transfer_failed(current_job, cancellation_reason)
                self._transfer_manager.cleanup_finished_transfers()
                return current_job.job_id

            self._log_outgoing_transfer_exception(
                exc=exc,
                peer=peer,
                session_id=session_id,
                job_id=job.job_id,
                ack_received=ack_received,
                session_close_sent=session_close_sent,
            )

            if current_job.status.name == "CANCELLED":
                cancellation_reason = current_job.error_message or "Transfert annulé par l'utilisateur."

                if sock is not None and not transfer_cancel_sent and not ack_received and not session_close_sent:
                    try:
                        cancel_message = self._transfer_manager.build_transfer_cancel_message(
                            job.job_id,
                            cancellation_reason,
                        )
                        self._session_client.send_message(sock, cancel_message)
                        transfer_cancel_sent = True
                    except Exception:
                        self._logger.debug(
                            "TRANSFER_CANCEL could not be sent after forced socket interruption for job %s.",
                            job.job_id,
                        )

                self._emit_transfer_failed(current_job, cancellation_reason)
                self._transfer_manager.cleanup_finished_transfers()
                return current_job.job_id

            if current_job.status.name not in {"FAILED", "CANCELLED", "COMPLETED"}:
                try:
                    current_job.fail(str(exc))
                except Exception:
                    pass

            self._emit_transfer_failed(current_job, str(exc))

            if self._should_send_transfer_error(
                sock=sock,
                current_job=current_job,
                ack_received=ack_received,
                session_close_sent=session_close_sent,
                exc=exc,
            ):
                try:
                    error_message = self._transfer_manager.build_transfer_error_message(
                        job.job_id,
                        str(exc),
                    )
                    self._session_client.send_message(sock, error_message)
                    transfer_error_sent = True
                except Exception:
                    self._logger.exception(
                        "Failed to send TRANSFER_ERROR for job %s.",
                        job.job_id,
                    )

            self._transfer_manager.cleanup_finished_transfers()
            raise

        finally:
            self._clear_active_outgoing_job_id(job.job_id)
            self._clear_active_outgoing_socket(sock)

            if sock is not None:
                wait_for_remote_close = (
                    ack_received
                    or session_close_sent
                    or transfer_error_sent
                    or transfer_cancel_sent
                )
                try:
                    self._close_session_socket(
                        sock,
                        wait_for_remote_close=wait_for_remote_close,
                    )
                except OSError as exc:
                    if not self._is_socket_already_closed_error(exc):
                        raise

                self._logger.debug(
                    "Outgoing socket closed for session_id=%s, job_id=%s, ack_received=%s, session_close_sent=%s, completed_job_id=%s",
                    session_id,
                    job.job_id,
                    ack_received,
                    session_close_sent,
                    completed_job_id,
                )

    def _handle_peer_discovered(self, message: dict[str, Any]) -> None:
        peer = self._peer_manager.register_peer(message)

        self._logger.debug(
            "Peer discovery integrated into PeerManager: %s (%s)",
            peer.display_name,
            peer.peer_id,
        )

        self._notify_peers_updated()

    def _handle_session_requested(
        self,
        message: dict[str, Any],
        client_address: tuple[str, int],
    ) -> dict[str, Any] | None:
        self._logger.info(
            "Incoming session request received from %s:%s, sender_id=%s, session_id=%s",
            client_address[0],
            client_address[1],
            message.get("sender_id"),
            message.get("session_id"),
        )

        if self._on_session_requested is not None:
            try:
                return self._on_session_requested(message, client_address)
            except Exception:
                self._logger.exception("Upper session request callback failed.")
                raise

        return None

    def _handle_auth_response(
        self,
        message: dict[str, Any],
        client_address: tuple[str, int],
    ) -> dict[str, Any]:
        session_id = message["session_id"]
        password = message["password"]

        self._logger.info(
            "Validating AUTH_RESPONSE from %s:%s for session_id=%s",
            client_address[0],
            client_address[1],
            session_id,
        )

        result = self._auth_manager.verify_password(password)

        if result.success:
            return create_message(
                MessageType.AUTH_SUCCESS,
                session_id=session_id,
            )

        return create_message(
            MessageType.AUTH_FAILED,
            session_id=session_id,
            reason=result.reason or "AUTH_FAILED",
        )

    def _handle_transfer_message(
        self,
        message: dict[str, Any],
        chunk_data: bytes | None,
        session_context: dict[str, Any],
        client_address: tuple[str, int],
    ) -> None:
        message_type = message.get("type")

        self._logger.debug(
            "Handling transfer message %s from %s:%s for session_id=%s",
            message_type,
            client_address[0],
            client_address[1],
            session_context.get("session_id"),
        )

        client_socket = session_context.get("client_socket")

        if message_has_type(message, MessageType.TRANSFER_INIT):
            job = self._transfer_manager.handle_transfer_init(
                message=message,
                source_peer_id=session_context["sender_id"],
                target_peer_id=self._local_identity.node_id,
                remote_display_name=session_context.get("sender_name"),
                remote_ip_address=client_address[0],
            )
            self._emit_transfer_started(job)
            return

        if message_has_type(message, MessageType.FILE_INFO):
            file_item = self._transfer_manager.handle_file_info(message)
            self._emit_transfer_progress(
                self._transfer_manager.build_progress_snapshot(
                    message["job_id"],
                    relative_path=file_item.relative_path,
                )
            )
            return

        if message_has_type(message, MessageType.FILE_CHUNK):
            if chunk_data is None:
                raise ValueError("FILE_CHUNK received without chunk_data.")

            self._transfer_manager.handle_file_chunk(
                message=message,
                chunk_data=chunk_data,
            )

            self._emit_transfer_progress(
                self._transfer_manager.build_progress_snapshot(
                    message["job_id"],
                    relative_path=message["relative_path"],
                )
            )
            return

        if message_has_type(message, MessageType.FILE_COMPLETE):
            file_item = self._transfer_manager.handle_file_complete(message)

            self._emit_transfer_progress(
                self._transfer_manager.build_progress_snapshot(
                    message["job_id"],
                    relative_path=file_item.relative_path,
                )
            )
            return

        if message_has_type(message, MessageType.TRANSFER_COMPLETE):
            completed_job = self._transfer_manager.handle_transfer_complete(message)

            if client_socket is None:
                raise RuntimeError(
                    "TRANSFER_COMPLETE received but no client_socket is available "
                    "in session_context for ACK response."
                )

            ack_message = self._transfer_manager.build_transfer_ack_message(
                message["job_id"]
            )
            self._session_client.send_message(client_socket, ack_message)
            session_context["transfer_complete_received"] = True
            session_context["transfer_ack_sent"] = True

            self._emit_transfer_completed(completed_job)
            self._transfer_manager.cleanup_finished_transfers()
            return

        if message_has_type(message, MessageType.TRANSFER_ACK):
            completed_job = self._transfer_manager.handle_transfer_ack(message)
            self._emit_transfer_completed(completed_job)
            self._transfer_manager.cleanup_finished_transfers()
            return

        if message_has_type(message, MessageType.TRANSFER_ERROR):
            failed_job = self._transfer_manager.handle_transfer_error(message)
            self._emit_transfer_failed(
                failed_job,
                message.get("error_message", "remote transfer error"),
            )
            self._transfer_manager.cleanup_finished_transfers()
            return

        if message_has_type(message, MessageType.TRANSFER_CANCEL):
            cancelled_job = self._transfer_manager.handle_transfer_cancel(message)
            self._emit_transfer_failed(
                cancelled_job,
                message.get("reason", "Transfer cancelled by remote side."),
            )
            self._transfer_manager.cleanup_finished_transfers()
            return

        if message_has_type(message, MessageType.SESSION_CLOSE):
            session_context["session_close_received"] = True
            self._logger.info(
                "SESSION_CLOSE received from %s:%s for session_id=%s",
                client_address[0],
                client_address[1],
                session_context.get("session_id"),
            )
            return

        raise ValueError(f"Unsupported transfer message type: {message_type!r}")

    def _notify_peers_updated(self) -> None:
        if self._on_peers_updated is None:
            return

        try:
            peers = self._peer_manager.get_peers(online_only=False)
            self._on_peers_updated(peers)
        except Exception:
            self._logger.exception("Peers updated callback failed.")

    def _emit_transfer_started(self, job: TransferJob) -> None:
        if self._on_transfer_started is None:
            return

        try:
            self._on_transfer_started(job)
        except Exception:
            self._logger.exception("Transfer started callback failed.")

    def _emit_transfer_progress(self, progress: TransferProgress) -> None:
        if self._on_transfer_progress is None:
            return

        try:
            self._on_transfer_progress(progress)
        except Exception:
            self._logger.exception("Transfer progress callback failed.")

    def _emit_transfer_completed(self, job: TransferJob) -> None:
        if self._on_transfer_completed is None:
            return

        try:
            self._on_transfer_completed(job)
        except Exception:
            self._logger.exception("Transfer completed callback failed.")

    def _emit_transfer_failed(self, job: TransferJob, reason: str) -> None:
        if self._on_transfer_failed is None:
            return

        try:
            self._on_transfer_failed(job, reason)
        except Exception:
            self._logger.exception("Transfer failed callback failed.")

    def _resolve_outgoing_password(self, password: str | None) -> str:
        if password is not None:
            return password

        return self._shared_password

    def _close_session_socket(
        self,
        sock: object,
        *,
        wait_for_remote_close: bool,
    ) -> None:
        close_gracefully = getattr(self._session_client, "close_gracefully", None)
        if callable(close_gracefully):
            try:
                close_gracefully(
                    sock,
                    wait_for_remote_close=wait_for_remote_close,
                )
            except OSError as exc:
                if not self._is_socket_already_closed_error(exc):
                    raise
            return

        try:
            sock.close()
        except OSError:
            pass

    def _is_socket_already_closed_error(self, exc: BaseException) -> bool:
        checker = getattr(self._session_client, "_is_socket_already_closed_error", None)
        if callable(checker) and isinstance(exc, OSError):
            try:
                return bool(checker(exc))
            except Exception:
                return False

        if not isinstance(exc, OSError):
            return False

        return getattr(exc, "winerror", None) in {10038, 10057}

    def _is_expected_cancellation_exception(
        self,
        exc: BaseException,
        current_job: TransferJob,
    ) -> bool:
        if current_job.status.name != "CANCELLED":
            return False

        if isinstance(exc, SessionCancelledError):
            return True

        if self._active_transfer_cancel_event.is_set():
            if isinstance(exc, RuntimeError) and "annulé" in str(exc).lower():
                return True
            if self._session_client.is_connection_reset_error(exc):
                return True
            if self._is_socket_already_closed_error(exc):
                return True

        return False

    def _should_send_transfer_error(
        self,
        *,
        sock: object | None,
        current_job: TransferJob,
        ack_received: bool,
        session_close_sent: bool,
        exc: BaseException,
    ) -> bool:
        if sock is None:
            return False

        if current_job.status.name == "CANCELLED":
            return False

        if ack_received or session_close_sent:
            return False

        if self._session_client.is_connection_reset_error(exc):
            return False

        return True

    def _log_outgoing_transfer_exception(
        self,
        *,
        exc: BaseException,
        peer: Peer,
        session_id: str,
        job_id: str,
        ack_received: bool,
        session_close_sent: bool,
    ) -> None:
        if (ack_received or session_close_sent) and self._session_client.is_connection_reset_error(exc):
            self._logger.info(
                "Outgoing transfer socket reset after finalization for peer %s (%s), session_id=%s, job_id=%s: %s",
                peer.display_name,
                peer.peer_id,
                session_id,
                job_id,
                exc,
            )
            return

        self._logger.exception(
            "Outgoing transfer failed for peer %s (%s), session_id=%s, job_id=%s: %s",
            peer.display_name,
            peer.peer_id,
            session_id,
            job_id,
            exc,
        )

    def _set_active_outgoing_job_id(self, job_id: str) -> None:
        with self._transfer_control_lock:
            self._active_outgoing_job_id = job_id
            self._active_transfer_cancel_event.clear()

    def _clear_active_outgoing_job_id(self, job_id: str) -> None:
        with self._transfer_control_lock:
            if self._active_outgoing_job_id == job_id:
                self._active_outgoing_job_id = None
                self._active_transfer_cancel_event.clear()

    def _set_active_outgoing_socket(self, sock: socket.socket | None) -> None:
        with self._transfer_control_lock:
            self._active_outgoing_socket = sock

    def _clear_active_outgoing_socket(self, sock: socket.socket | None) -> None:
        with self._transfer_control_lock:
            if self._active_outgoing_socket is sock:
                self._active_outgoing_socket = None

    def _raise_if_active_transfer_cancelled(self) -> None:
        if self._active_transfer_cancel_event.is_set():
            raise RuntimeError("Transfert annulé par l'utilisateur.")

    @staticmethod
    def _generate_session_id() -> str:
        return uuid.uuid4().hex