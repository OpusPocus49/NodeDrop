from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from core.app_manager import AppManager
from core.models import NodeIdentity, Peer, TransferJob, TransferProgress
from utils.log_utils import get_logger


class AppBridge(QObject):
    """
    Qt bridge between the backend AppManager and the GUI.

    Responsibilities:
    - keep AppManager free from Qt dependencies
    - convert backend callbacks into thread-safe Qt signals
    - expose small GUI-friendly methods for startup and state refresh
    """

    peers_updated = Signal(object)              # list[Peer]
    transfer_started = Signal(object)           # TransferJob
    transfer_progress = Signal(object)          # TransferProgress
    transfer_completed = Signal(object)         # TransferJob
    transfer_failed = Signal(object, str)       # TransferJob, reason

    status_message = Signal(str)
    fatal_error = Signal(str)
    
    def send_transfer(self, peer_id: str, source_path: str) -> None:
        """
        Launch a blocking transfer through AppManager.

        This method is intentionally synchronous.
        It must be called from a worker thread, never from the Qt UI thread.
        """
        self._logger.info(
            "GUI requested transfer: peer_id=%s, source_path=%s",
            peer_id,
            source_path,
        )
        self._app_manager.send_transfer(peer_id, source_path)
    
    def __init__(
        self,
        app_manager: AppManager,
        local_identity: NodeIdentity,
    ) -> None:
        super().__init__()
        self._logger = get_logger("gui.app_bridge")
        self._app_manager = app_manager
        self._local_identity = local_identity

        self._app_manager.set_on_peers_updated(self._handle_peers_updated)
        self._app_manager.set_on_transfer_started(self._handle_transfer_started)
        self._app_manager.set_on_transfer_progress(self._handle_transfer_progress)
        self._app_manager.set_on_transfer_completed(self._handle_transfer_completed)
        self._app_manager.set_on_transfer_failed(self._handle_transfer_failed)
        self._app_manager.set_on_session_requested(self._handle_session_requested)
    
    @property
    def app_manager(self) -> AppManager:
        return self._app_manager

    @property
    def local_identity(self) -> NodeIdentity:
        return self._local_identity

    @property
    def is_running(self) -> bool:
        return self._app_manager.is_running

    # ------------------------------------------------------------------
    # Public GUI-facing API
    # ------------------------------------------------------------------

    @Slot()
    def start_services(self) -> None:
        if self._app_manager.is_running:
            self.status_message.emit("Les services NodeDrop sont déjà démarrés.")
            return

        try:
            self._app_manager.start()
            self.status_message.emit("Services NodeDrop démarrés.")
            self.refresh_peers()
        except Exception as exc:
            self._logger.exception("Failed to start AppManager from GUI.")
            self.fatal_error.emit(f"Impossible de démarrer les services NodeDrop : {exc}")

    @Slot()
    def stop_services(self) -> None:
        if not self._app_manager.is_running:
            self.status_message.emit("Les services NodeDrop sont déjà arrêtés.")
            return

        try:
            self._app_manager.stop()
            self.status_message.emit("Services NodeDrop arrêtés.")
        except Exception as exc:
            self._logger.exception("Failed to stop AppManager from GUI.")
            self.fatal_error.emit(f"Erreur lors de l'arrêt des services NodeDrop : {exc}")

    @Slot()
    def refresh_peers(self) -> None:
        """
        Trigger a peer cleanup pass and emit the current peer snapshot.
        """
        try:
            self._app_manager.cleanup_expired_peers(remove=False)
            peers = self._app_manager.get_peers(online_only=False)
            self.peers_updated.emit(peers)
            self.status_message.emit(f"{len(peers)} pair(s) connu(s).")
        except Exception as exc:
            self._logger.exception("Failed to refresh peers.")
            self.fatal_error.emit(f"Impossible de rafraîchir la liste des pairs : {exc}")


    @Slot(result=bool)
    def cancel_active_transfer(self) -> bool:
        """
        Request cancellation of the current outgoing transfer.

        Returns True when a running transfer was found and the cancellation
        request was forwarded to AppManager.
        """
        try:
            job = self._app_manager.cancel_active_transfer()
        except Exception as exc:
            self._logger.exception("Failed to cancel active transfer from GUI.")
            self.fatal_error.emit(f"Impossible d'annuler le transfert actif : {exc}")
            return False

        if job is None:
            self.status_message.emit("Aucun transfert actif à annuler.")
            return False

        self.status_message.emit(
            f"Annulation demandée pour le transfert {job.job_id}."
        )
        return True

    def get_peers(self) -> list[Peer]:
        return self._app_manager.get_peers(online_only=False)

    def get_online_peers(self) -> list[Peer]:
        return self._app_manager.get_peers(online_only=True)

    def get_transfer_jobs(self) -> list[TransferJob]:
        return self._app_manager.transfer_manager.get_jobs()

    # ------------------------------------------------------------------
    # Backend callbacks -> Qt signals
    # ------------------------------------------------------------------

    def _handle_peers_updated(self, peers: list[Peer]) -> None:
        self.peers_updated.emit(peers)

    def _handle_transfer_started(self, job: TransferJob) -> None:
        self.transfer_started.emit(job)

    def _handle_transfer_progress(self, progress: TransferProgress) -> None:
        self.transfer_progress.emit(progress)

    def _handle_transfer_completed(self, job: TransferJob) -> None:
        self.transfer_completed.emit(job)

    def _handle_transfer_failed(self, job: TransferJob, reason: str) -> None:
        self.transfer_failed.emit(job, reason)

    def _handle_session_requested(
        self,
        message: dict[str, Any],
        client_address: tuple[str, int],
    ) -> dict[str, Any] | None:
        """
        Phase 8.1:
        Do not implement interactive acceptance yet.

        We keep this callback minimal and passive for now.
        It will be upgraded in a later GUI phase with a proper dialog.
        """
        sender_id = message.get("sender_id", "unknown")
        session_id = message.get("session_id", "unknown")

        self.status_message.emit(
            f"Demande de session reçue depuis {client_address[0]}:{client_address[1]} "
            f"(sender_id={sender_id}, session_id={session_id})."
        )
        return None