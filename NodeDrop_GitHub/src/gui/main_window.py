from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.models import NodeIdentity, Peer, TransferJob, TransferProgress, TransferStatus
from gui.app_bridge import AppBridge
from gui.widgets import LogPanelWidget, PeerTableWidget, TransferPanelWidget
from gui.workers import TransferWorker
from utils.config import APP_NAME
from utils.log_utils import get_logger


class MainWindow(QMainWindow):
    """
    Main NodeDrop GUI window.

    Responsibilities:
    - orchestrate the main GUI layout
    - connect AppBridge signals to GUI widgets
    - allow file/folder selection
    - launch transfer workers outside the UI thread
    """

    def __init__(
        self,
        bridge: AppBridge,
        local_identity: NodeIdentity,
        log_file_path: str,
    ) -> None:
        super().__init__()

        self._logger = get_logger("gui.main_window")
        self._bridge = bridge
        self._local_identity = local_identity
        self._log_file_path = log_file_path

        self._transfer_thread: QThread | None = None
        self._transfer_worker: TransferWorker | None = None

        self._last_peers_snapshot: tuple[tuple[str, str, str, str, str], ...] = ()
        self._last_logged_selected_peer_id: str | None = None
        self._selection_restored_in_last_refresh = False
        self._last_logged_status_message: str | None = None

        self.setWindowTitle(f"{APP_NAME} — Phase 9.1")
        self.resize(1040, 780)

        self._build_ui()
        self._connect_signals()
        self._populate_static_fields()
        self._update_action_buttons()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(3000)
        self._refresh_timer.timeout.connect(self._bridge.refresh_peers)
        self._refresh_timer.start()

        self._append_log("Fenêtre initialisée.")
        self._append_log(f"Fichier de log : {self._log_file_path}")

        self._bridge.start_services()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        root_layout.addWidget(self._build_identity_group())
        root_layout.addWidget(self._build_peers_group(), stretch=2)
        root_layout.addWidget(self._build_transfer_group(), stretch=1)
        root_layout.addWidget(self._build_logs_group(), stretch=1)

        self._build_menu()

        self.statusBar().showMessage("Initialisation de NodeDrop...")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Fichier")

        refresh_action = QAction("Actualiser les pairs", self)
        refresh_action.triggered.connect(self._bridge.refresh_peers)
        file_menu.addAction(refresh_action)

        quit_action = QAction("Quitter", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _build_identity_group(self) -> QGroupBox:
        group = QGroupBox("Identité locale", self)
        layout = QGridLayout(group)

        self.local_name_value = QLabel("-")
        self.local_node_id_value = QLabel("-")
        self.local_endpoint_value = QLabel("-")
        self.local_version_value = QLabel("-")

        layout.addWidget(QLabel("Nom affiché :"), 0, 0)
        layout.addWidget(self.local_name_value, 0, 1)

        layout.addWidget(QLabel("Node ID :"), 0, 2)
        layout.addWidget(self.local_node_id_value, 0, 3)

        layout.addWidget(QLabel("Adresse :"), 1, 0)
        layout.addWidget(self.local_endpoint_value, 1, 1)

        layout.addWidget(QLabel("Version :"), 1, 2)
        layout.addWidget(self.local_version_value, 1, 3)

        return group

    def _build_peers_group(self) -> QGroupBox:
        group = QGroupBox("Pairs détectés sur le LAN", self)
        layout = QVBoxLayout(group)

        button_row = QHBoxLayout()

        self.refresh_button = QPushButton("Actualiser")
        self.send_file_button = QPushButton("Envoyer un fichier")
        self.send_folder_button = QPushButton("Envoyer un dossier")

        button_row.addWidget(self.refresh_button)
        button_row.addStretch(1)
        button_row.addWidget(self.send_file_button)
        button_row.addWidget(self.send_folder_button)

        self.peers_table = PeerTableWidget(self)

        layout.addLayout(button_row)
        layout.addWidget(self.peers_table)

        return group

    def _build_transfer_group(self) -> QGroupBox:
        group = QGroupBox("État du transfert", self)
        layout = QVBoxLayout(group)

        self.transfer_panel = TransferPanelWidget(self)
        layout.addWidget(self.transfer_panel)

        control_row = QHBoxLayout()
        control_row.addStretch(1)
        self.cancel_transfer_button = QPushButton("Annuler le transfert")
        control_row.addWidget(self.cancel_transfer_button)

        layout.addLayout(control_row)

        return group

    def _build_logs_group(self) -> QGroupBox:
        group = QGroupBox("Événements récents", self)
        layout = QVBoxLayout(group)

        self.logs_panel = LogPanelWidget(self)
        layout.addWidget(self.logs_panel)

        return group

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self._bridge.refresh_peers)
        self.send_file_button.clicked.connect(self._choose_file_and_send)
        self.send_folder_button.clicked.connect(self._choose_folder_and_send)
        self.cancel_transfer_button.clicked.connect(self._cancel_active_transfer)

        self.peers_table.itemSelectionChanged.connect(self._on_peer_selection_changed)
        self.peers_table.selection_restored.connect(self._on_peer_selection_restored)
        self.peers_table.selection_cleared.connect(self._on_peer_selection_cleared)

        self._bridge.peers_updated.connect(self._on_peers_updated)
        self._bridge.transfer_started.connect(self._on_transfer_started)
        self._bridge.transfer_progress.connect(self._on_transfer_progress)
        self._bridge.transfer_completed.connect(self._on_transfer_completed)
        self._bridge.transfer_failed.connect(self._on_transfer_failed)
        self._bridge.status_message.connect(self._on_status_message)
        self._bridge.fatal_error.connect(self._on_fatal_error)

    def _populate_static_fields(self) -> None:
        self.local_name_value.setText(self._local_identity.display_name)
        self.local_node_id_value.setText(self._local_identity.node_id)
        self.local_endpoint_value.setText(
            f"{self._local_identity.ip_address}:{self._local_identity.tcp_port}"
        )
        self.local_version_value.setText(self._local_identity.version)

    # ------------------------------------------------------------------
    # Peer handling
    # ------------------------------------------------------------------

    def _on_peers_updated(self, peers: object) -> None:
        peer_list = [peer for peer in peers if isinstance(peer, Peer)] if isinstance(peers, list) else []
        peers_snapshot = self._build_peers_snapshot(peer_list)
        peers_changed = peers_snapshot != self._last_peers_snapshot

        self._selection_restored_in_last_refresh = False
        self.peers_table.update_peers(peer_list)
        self._update_action_buttons()

        if peers_changed:
            self._last_peers_snapshot = peers_snapshot
            self._append_log(f"Liste des pairs mise à jour ({len(peer_list)} pair(s)).")

            selected_peer_id = self.peers_table.get_selected_peer_id()
            if selected_peer_id is None:
                self._last_logged_selected_peer_id = None

        self.statusBar().showMessage(f"{len(peer_list)} pair(s) connu(s).", 3000)

    def _on_peer_selection_changed(self) -> None:
        selected_peer_id = self.peers_table.get_selected_peer_id()
        self._update_action_buttons()

        if selected_peer_id is None:
            self._last_logged_selected_peer_id = None
            return

        if self._selection_restored_in_last_refresh:
            self._selection_restored_in_last_refresh = False
            return

        if selected_peer_id == self._last_logged_selected_peer_id:
            return

        selected_peer_name = self.peers_table.get_selected_peer_name()
        if selected_peer_name is None:
            return

        self._last_logged_selected_peer_id = selected_peer_id
        self._append_log(f"Pair sélectionné : {selected_peer_name}")

    def _on_peer_selection_restored(self) -> None:
        self._selection_restored_in_last_refresh = True

    def _on_peer_selection_cleared(self) -> None:
        self._last_logged_selected_peer_id = None
        self._update_action_buttons()

    def _get_selected_peer_id(self) -> str | None:
        return self.peers_table.get_selected_peer_id()

    def _update_action_buttons(self) -> None:
        current_row = self.peers_table.currentRow()
        peer_selected = current_row >= 0

        worker_running = (
            self._transfer_thread is not None
            and self._transfer_thread.isRunning()
        )

        enable_send = peer_selected and not worker_running

        self.send_file_button.setEnabled(enable_send)
        self.send_folder_button.setEnabled(enable_send)
        self.cancel_transfer_button.setEnabled(worker_running)

    def _build_peers_snapshot(
        self,
        peers: list[Peer],
    ) -> tuple[tuple[str, str, str, str, str], ...]:
        snapshot: list[tuple[str, str, str, str, str]] = []

        for peer in sorted(peers, key=lambda item: item.peer_id):
            snapshot.append(
                (
                    peer.peer_id,
                    peer.display_name,
                    peer.ip_address,
                    str(peer.tcp_port),
                    peer.version,
                )
            )

        return tuple(snapshot)

    # ------------------------------------------------------------------
    # File / folder selection
    # ------------------------------------------------------------------

    def _choose_file_and_send(self) -> None:
        peer_id = self._get_selected_peer_id()
        if peer_id is None:
            QMessageBox.information(
                self,
                "Aucun pair sélectionné",
                "Sélectionne d'abord un pair NodeDrop.",
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir un fichier à envoyer",
            "",
            "Tous les fichiers (*)",
        )
        if not file_path:
            return

        self._start_transfer_worker(peer_id, file_path)

    def _choose_folder_and_send(self) -> None:
        peer_id = self._get_selected_peer_id()
        if peer_id is None:
            QMessageBox.information(
                self,
                "Aucun pair sélectionné",
                "Sélectionne d'abord un pair NodeDrop.",
            )
            return

        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Choisir un dossier à envoyer",
            "",
        )
        if not folder_path:
            return

        self._start_transfer_worker(peer_id, folder_path)

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def _start_transfer_worker(self, peer_id: str, source_path: str) -> None:
        if self._transfer_thread is not None and self._transfer_thread.isRunning():
            QMessageBox.warning(
                self,
                "Transfert déjà en cours",
                "Un lancement de transfert est déjà en cours.",
            )
            return

        source = Path(source_path)
        self._append_log(f"Préparation du transfert : {source}")

        self._transfer_thread = QThread(self)
        self._transfer_worker = TransferWorker(
            bridge=self._bridge,
            peer_id=peer_id,
            source_path=source_path,
        )
        self._transfer_worker.moveToThread(self._transfer_thread)

        self._transfer_thread.started.connect(self._transfer_worker.run)
        self._transfer_worker.started.connect(self._on_worker_started)
        self._transfer_worker.finished.connect(self._on_worker_finished)
        self._transfer_worker.failed.connect(self._on_worker_failed)

        self._transfer_worker.finished.connect(self._transfer_thread.quit)
        self._transfer_worker.failed.connect(self._transfer_thread.quit)

        self._transfer_thread.finished.connect(self._cleanup_transfer_worker)

        self._update_action_buttons()
        self._transfer_thread.start()

    def _cleanup_transfer_worker(self) -> None:
        if self._transfer_worker is not None:
            self._transfer_worker.deleteLater()
            self._transfer_worker = None

        if self._transfer_thread is not None:
            self._transfer_thread.deleteLater()
            self._transfer_thread = None

        self._update_action_buttons()

    def _on_worker_started(self, peer_id: str, source_path: str) -> None:
        self.statusBar().showMessage("Lancement du transfert...", 5000)
        self._append_log(
            f"Lancement du transfert vers peer_id={peer_id} | source={source_path}"
        )
        self._update_action_buttons()

    def _on_worker_finished(self, peer_id: str, source_path: str) -> None:
        self.statusBar().showMessage("Opération d'envoi terminée.", 5000)
        self._append_log(
            f"Opération d'envoi terminée pour peer_id={peer_id} | source={source_path}"
        )

    def _on_worker_failed(self, error_message: str) -> None:
        normalized = error_message.lower().strip()
        if "cancel" in normalized or "annul" in normalized:
            self._append_log(f"Worker transfert annulé : {error_message}")
            return

        self._append_log(f"Erreur worker transfert : {error_message}")
        QMessageBox.warning(self, "Erreur de lancement du transfert", error_message)

    def _cancel_active_transfer(self) -> None:
        if self._transfer_thread is None or not self._transfer_thread.isRunning():
            QMessageBox.information(
                self,
                "Aucun transfert actif",
                "Aucun transfert actif n'est en cours.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Annuler le transfert",
            "Veux-tu vraiment annuler le transfert actif ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        requested = self._bridge.cancel_active_transfer()
        if requested:
            self._append_log("Demande d'annulation envoyée au transfert actif.")

    # ------------------------------------------------------------------
    # Transfer state handling
    # ------------------------------------------------------------------

    def _on_transfer_started(self, job: object) -> None:
        if not isinstance(job, TransferJob):
            return

        self.transfer_panel.transfer_started(job)
        self._append_log(f"Transfert démarré : job_id={job.job_id}")
        self._update_action_buttons()

    def _on_transfer_progress(self, progress: object) -> None:
        if not isinstance(progress, TransferProgress):
            return

        self.transfer_panel.transfer_progress(progress)

    def _on_transfer_completed(self, job: object) -> None:
        if not isinstance(job, TransferJob):
            return

        self.transfer_panel.transfer_completed(job)
        self._append_log(f"Transfert terminé : {job.job_id}")
        self._update_action_buttons()

    def _on_transfer_failed(self, job: object, reason: str) -> None:
        if isinstance(job, TransferJob):
            self.transfer_panel.transfer_failed(job)
            if job.status == TransferStatus.CANCELLED:
                self._append_log(f"Transfert annulé : {reason}")
                self.statusBar().showMessage(reason, 5000)
                self._update_action_buttons()
                return

        self._append_log(f"Transfert en erreur : {reason}")
        QMessageBox.warning(self, "Erreur de transfert", reason)
        self._update_action_buttons()

    # ------------------------------------------------------------------
    # Status / logs
    # ------------------------------------------------------------------

    def _on_status_message(self, message: str) -> None:
        self.statusBar().showMessage(message, 5000)

        if self._should_log_status_message(message):
            self._append_log(message)
            self._last_logged_status_message = message

    def _should_log_status_message(self, message: str) -> bool:
        normalized = message.strip()

        if not normalized:
            return False

        if normalized.endswith("pair(s) connu(s)."):
            return False

        if normalized == self._last_logged_status_message:
            return False

        return True

    def _on_fatal_error(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)
        self._append_log(f"ERREUR: {message}")
        QMessageBox.critical(self, "Erreur NodeDrop", message)

    def _append_log(self, message: str) -> None:
        self.logs_panel.append_log(message)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self._refresh_timer.stop()
        except Exception:
            pass

        try:
            if self._transfer_thread is not None and self._transfer_thread.isRunning():
                self._transfer_thread.quit()
                self._transfer_thread.wait(3000)
        except Exception as exc:
            self._logger.exception("Error while stopping transfer thread: %s", exc)

        try:
            self._bridge.stop_services()
        except Exception as exc:
            self._logger.exception("Error while closing NodeDrop main window: %s", exc)

        event.accept()