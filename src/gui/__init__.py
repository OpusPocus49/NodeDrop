from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.models import NodeIdentity, Peer, TransferJob, TransferProgress
from gui.app_bridge import AppBridge
from gui.ui_helpers import (
    format_bytes,
    format_peer_endpoint,
    format_peer_status,
    format_percent,
    format_transfer_summary,
    format_timestamp,
)
from utils.config import APP_NAME
from utils.log_utils import get_logger


class MainWindow(QMainWindow):
    """
    Main NodeDrop GUI window for Phase 8.1.

    Scope of this step:
    - start/stop AppManager
    - show local identity
    - show discovered peers
    - show a minimal transfer/log zone
    - keep send buttons present but not wired yet
    """

    PEER_COLUMNS = ["Nom", "Adresse", "Version", "Statut", "Dernière activité"]

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

        self._selected_peer_id: Optional[str] = None

        self.setWindowTitle(f"{APP_NAME} — Phase 8.1")
        self.resize(980, 700)

        self._build_ui()
        self._connect_signals()
        self._populate_static_fields()

        # Refresh périodique léger pour refléter les expirations réseau.
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

        # Étape 8.1 : boutons visibles mais non branchés au transfert réel.
        self.send_file_button.setEnabled(False)
        self.send_folder_button.setEnabled(False)

        self.send_file_button.setToolTip(
            "Le transfert sera branché à l'étape 8.4 dans un worker non bloquant."
        )
        self.send_folder_button.setToolTip(
            "Le transfert sera branché à l'étape 8.4 dans un worker non bloquant."
        )

        button_row.addWidget(self.refresh_button)
        button_row.addStretch(1)
        button_row.addWidget(self.send_file_button)
        button_row.addWidget(self.send_folder_button)

        self.peers_table = QTableWidget(0, len(self.PEER_COLUMNS), self)
        self.peers_table.setHorizontalHeaderLabels(self.PEER_COLUMNS)
        self.peers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.peers_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.peers_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.peers_table.verticalHeader().setVisible(False)
        self.peers_table.setAlternatingRowColors(True)
        self.peers_table.setSortingEnabled(False)
        self.peers_table.horizontalHeader().setStretchLastSection(True)

        layout.addLayout(button_row)
        layout.addWidget(self.peers_table)

        return group

    def _build_transfer_group(self) -> QGroupBox:
        group = QGroupBox("État du transfert", self)
        layout = QGridLayout(group)

        self.transfer_job_value = QLabel("Aucun transfert")
        self.transfer_file_value = QLabel("-")
        self.transfer_status_value = QLabel("Idle")
        self.transfer_bytes_value = QLabel("0 B / 0 B")

        self.transfer_progress_bar = QProgressBar(self)
        self.transfer_progress_bar.setRange(0, 100)
        self.transfer_progress_bar.setValue(0)
        self.transfer_progress_bar.setFormat("%p%")

        layout.addWidget(QLabel("Job :"), 0, 0)
        layout.addWidget(self.transfer_job_value, 0, 1, 1, 3)

        layout.addWidget(QLabel("Fichier courant :"), 1, 0)
        layout.addWidget(self.transfer_file_value, 1, 1, 1, 3)

        layout.addWidget(QLabel("État :"), 2, 0)
        layout.addWidget(self.transfer_status_value, 2, 1)

        layout.addWidget(QLabel("Progression :"), 2, 2)
        layout.addWidget(self.transfer_bytes_value, 2, 3)

        layout.addWidget(self.transfer_progress_bar, 3, 0, 1, 4)

        return group

    def _build_logs_group(self) -> QGroupBox:
        group = QGroupBox("Événements récents", self)
        layout = QVBoxLayout(group)

        self.logs_edit = QPlainTextEdit(self)
        self.logs_edit.setReadOnly(True)
        self.logs_edit.setMaximumBlockCount(400)

        layout.addWidget(self.logs_edit)
        return group

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self._bridge.refresh_peers)

        self.peers_table.itemSelectionChanged.connect(self._on_peer_selection_changed)

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
        peer_list = list(peers) if isinstance(peers, list) else []
        self._rebuild_peers_table(peer_list)
        self._append_log(f"Liste des pairs mise à jour ({len(peer_list)} pair(s)).")

    def _rebuild_peers_table(self, peers: list[Peer]) -> None:
        previous_selected_peer_id = self._selected_peer_id

        self.peers_table.setRowCount(len(peers))

        for row_index, peer in enumerate(peers):
            self._set_table_item(row_index, 0, peer.display_name, peer.peer_id)
            self._set_table_item(row_index, 1, format_peer_endpoint(peer), peer.peer_id)
            self._set_table_item(row_index, 2, peer.version, peer.peer_id)
            self._set_table_item(row_index, 3, format_peer_status(peer), peer.peer_id)
            self._set_table_item(row_index, 4, format_timestamp(peer.last_seen), peer.peer_id)

        self.peers_table.resizeColumnsToContents()

        if previous_selected_peer_id is not None:
            self._restore_peer_selection(previous_selected_peer_id)

    def _set_table_item(self, row: int, column: int, text: str, peer_id: str) -> None:
        item = QTableWidgetItem(text)
        item.setData(Qt.UserRole, peer_id)
        self.peers_table.setItem(row, column, item)

    def _restore_peer_selection(self, peer_id: str) -> None:
        for row in range(self.peers_table.rowCount()):
            item = self.peers_table.item(row, 0)
            if item is None:
                continue
            if item.data(Qt.UserRole) == peer_id:
                self.peers_table.selectRow(row)
                return

    def _on_peer_selection_changed(self) -> None:
        selected_items = self.peers_table.selectedItems()
        if not selected_items:
            self._selected_peer_id = None
            return

        first_item = selected_items[0]
        self._selected_peer_id = first_item.data(Qt.UserRole)

        selected_peer_name = self.peers_table.item(first_item.row(), 0).text()
        self._append_log(f"Pair sélectionné : {selected_peer_name}")

    # ------------------------------------------------------------------
    # Transfer state handling
    # ------------------------------------------------------------------

    def _on_transfer_started(self, job: object) -> None:
        if not isinstance(job, TransferJob):
            return

        self.transfer_job_value.setText(job.job_id)
        self.transfer_file_value.setText("-")
        self.transfer_status_value.setText(job.status.value)
        self.transfer_bytes_value.setText(format_transfer_summary(job))
        self.transfer_progress_bar.setValue(0)

        self._append_log(
            f"Transfert démarré : job_id={job.job_id}, total={format_bytes(job.total_bytes)}"
        )

    def _on_transfer_progress(self, progress: object) -> None:
        if not isinstance(progress, TransferProgress):
            return

        self.transfer_job_value.setText(progress.job_id)
        self.transfer_file_value.setText(progress.file_name or "-")
        self.transfer_status_value.setText("RUNNING")
        self.transfer_bytes_value.setText(
            f"{format_bytes(progress.job_bytes_done)} / {format_bytes(progress.job_bytes_total)}"
        )
        self.transfer_progress_bar.setValue(int(max(0.0, min(100.0, progress.progress_percent))))
        self.transfer_progress_bar.setFormat(format_percent(progress.progress_percent))

    def _on_transfer_completed(self, job: object) -> None:
        if not isinstance(job, TransferJob):
            return

        self.transfer_job_value.setText(job.job_id)
        self.transfer_status_value.setText(job.status.value)
        self.transfer_bytes_value.setText(format_transfer_summary(job))
        self.transfer_progress_bar.setValue(100)
        self.transfer_progress_bar.setFormat("100 %")

        self._append_log(f"Transfert terminé : {job.job_id}")

    def _on_transfer_failed(self, job: object, reason: str) -> None:
        if isinstance(job, TransferJob):
            self.transfer_job_value.setText(job.job_id)
            self.transfer_status_value.setText(job.status.value)
            self.transfer_bytes_value.setText(format_transfer_summary(job))

        self._append_log(f"Transfert en erreur : {reason}")
        QMessageBox.warning(self, "Erreur de transfert", reason)

    # ------------------------------------------------------------------
    # Status / logs
    # ------------------------------------------------------------------

    def _on_status_message(self, message: str) -> None:
        self.statusBar().showMessage(message, 5000)
        self._append_log(message)

    def _on_fatal_error(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)
        self._append_log(f"ERREUR: {message}")
        QMessageBox.critical(self, "Erreur NodeDrop", message)

    def _append_log(self, message: str) -> None:
        self.logs_edit.appendPlainText(message)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self._refresh_timer.stop()
        except Exception:
            pass

        try:
            self._bridge.stop_services()
        except Exception as exc:
            self._logger.exception("Error while closing NodeDrop main window: %s", exc)

        event.accept()