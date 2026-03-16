from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from core.models import Peer, TransferJob, TransferProgress
from gui.ui_helpers import (
    format_bytes,
    format_duration,
    format_percent,
    format_peer_endpoint,
    format_peer_status,
    format_remote_endpoint,
    format_speed,
    format_timestamp,
    format_transfer_summary,
)


class PeerTableWidget(QTableWidget):
    COLUMNS = ["Nom", "Adresse", "Version", "Statut", "Dernière activité"]

    selection_restored = Signal()
    selection_cleared = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, len(self.COLUMNS), parent)

        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)

        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)

        self._selected_peer_id: Optional[str] = None
        self._suppress_selection_signal = False

        self.itemSelectionChanged.connect(self._on_selection_changed)

    def update_peers(self, peers: list[Peer]) -> bool:
        """
        Update table contents while attempting to preserve the current selection.

        Returns:
            bool: True if the previous selection was restored automatically,
            False otherwise.
        """
        previous_selected_peer_id = self._selected_peer_id
        selection_restored = False

        self._suppress_selection_signal = True
        try:
            self.clearSelection()
            self.setCurrentCell(-1, -1)
            self.setRowCount(0)
            self.clearContents()
            self._selected_peer_id = None
            self.setRowCount(len(peers))

            for row, peer in enumerate(peers):
                self._set_item(row, 0, peer.display_name, peer.peer_id)
                self._set_item(row, 1, format_peer_endpoint(peer), peer.peer_id)
                self._set_item(row, 2, peer.version, peer.peer_id)
                self._set_item(row, 3, format_peer_status(peer), peer.peer_id)
                self._set_item(row, 4, format_timestamp(peer.last_seen), peer.peer_id)

            self.resizeColumnsToContents()

            if previous_selected_peer_id is not None:
                selection_restored = self._restore_selection(previous_selected_peer_id)
        finally:
            self._suppress_selection_signal = False

        if selection_restored:
            self.selection_restored.emit()
        elif previous_selected_peer_id is not None and self._selected_peer_id is None:
            self.selection_cleared.emit()

        return selection_restored

    def get_selected_peer_id(self) -> Optional[str]:
        row = self.currentRow()
        if row < 0:
            return None

        item = self.item(row, 0)
        if item is None:
            return None

        peer_id = item.data(Qt.UserRole)
        return peer_id if isinstance(peer_id, str) else None

    def get_selected_peer_name(self) -> Optional[str]:
        row = self.currentRow()
        if row < 0:
            return None

        item = self.item(row, 0)
        if item is None:
            return None

        return item.text()

    def _set_item(self, row: int, col: int, text: str, peer_id: str) -> None:
        item = QTableWidgetItem(text)
        item.setData(Qt.UserRole, peer_id)
        self.setItem(row, col, item)

    def _restore_selection(self, peer_id: str) -> bool:
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item is None:
                continue

            if item.data(Qt.UserRole) == peer_id:
                self.selectRow(row)
                self.setCurrentCell(row, 0)
                self._selected_peer_id = peer_id
                return True

        return False

    def _on_selection_changed(self) -> None:
        if self._suppress_selection_signal:
            return

        row = self.currentRow()
        if row < 0:
            self._selected_peer_id = None
            return

        item = self.item(row, 0)
        if item is None:
            self._selected_peer_id = None
            return

        peer_id = item.data(Qt.UserRole)
        self._selected_peer_id = peer_id if isinstance(peer_id, str) else None


class TransferPanelWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QGridLayout(self)

        self.job_label = QLabel("Aucun transfert")
        self.session_label = QLabel("-")
        self.peer_label = QLabel("-")
        self.file_label = QLabel("-")
        self.files_label = QLabel("0 / 0")
        self.status_label = QLabel("Idle")
        self.file_bytes_label = QLabel("0 B / 0 B")
        self.job_bytes_label = QLabel("0 B / 0 B")
        self.speed_label = QLabel("-")
        self.elapsed_label = QLabel("00:00:00")
        self.eta_label = QLabel("-")

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setFormat("0.0 %")

        layout.addWidget(QLabel("Job :"), 0, 0)
        layout.addWidget(self.job_label, 0, 1)
        layout.addWidget(QLabel("Session :"), 0, 2)
        layout.addWidget(self.session_label, 0, 3)

        layout.addWidget(QLabel("Pair :"), 1, 0)
        layout.addWidget(self.peer_label, 1, 1, 1, 3)

        layout.addWidget(QLabel("Fichier courant :"), 2, 0)
        layout.addWidget(self.file_label, 2, 1, 1, 3)

        layout.addWidget(QLabel("Fichiers :"), 3, 0)
        layout.addWidget(self.files_label, 3, 1)
        layout.addWidget(QLabel("État :"), 3, 2)
        layout.addWidget(self.status_label, 3, 3)

        layout.addWidget(QLabel("Fichier :"), 4, 0)
        layout.addWidget(self.file_bytes_label, 4, 1)
        layout.addWidget(QLabel("Global :"), 4, 2)
        layout.addWidget(self.job_bytes_label, 4, 3)

        layout.addWidget(QLabel("Débit :"), 5, 0)
        layout.addWidget(self.speed_label, 5, 1)
        layout.addWidget(QLabel("Écoulé :"), 5, 2)
        layout.addWidget(self.elapsed_label, 5, 3)

        layout.addWidget(QLabel("Temps restant :"), 6, 0)
        layout.addWidget(self.eta_label, 6, 1)

        layout.addWidget(self.progress, 7, 0, 1, 4)

    def transfer_started(self, job: TransferJob) -> None:
        self.job_label.setText(job.job_id)
        self.session_label.setText(job.session_id)
        self.peer_label.setText(
            format_remote_endpoint(job.remote_display_name, job.remote_ip_address)
        )
        self.file_label.setText("-")
        self.files_label.setText(f"0 / {job.file_count}")
        self.status_label.setText(job.status.value)
        self.file_bytes_label.setText("0 B / 0 B")
        self.job_bytes_label.setText(
            f"{format_bytes(job.transferred_bytes)} / {format_bytes(job.total_bytes)}"
        )
        self.speed_label.setText("-")
        self.elapsed_label.setText("00:00:00")
        self.eta_label.setText("-")
        self.progress.setValue(0)
        self.progress.setFormat("0.0 %")

    def transfer_progress(self, progress: TransferProgress) -> None:
        bounded_percent = max(0.0, min(100.0, progress.progress_percent))

        self.job_label.setText(progress.job_id)
        self.session_label.setText(progress.session_id)
        self.peer_label.setText(
            format_remote_endpoint(progress.remote_display_name, progress.remote_ip_address)
        )
        self.file_label.setText(progress.file_name or "-")
        self.files_label.setText(f"{progress.file_index} / {progress.file_count}")
        self.status_label.setText("RUNNING")
        self.file_bytes_label.setText(
            f"{format_bytes(progress.bytes_done)} / {format_bytes(progress.bytes_total)}"
        )
        self.job_bytes_label.setText(
            f"{format_bytes(progress.job_bytes_done)} / {format_bytes(progress.job_bytes_total)}"
        )
        self.speed_label.setText(format_speed(progress.speed_bps))
        self.elapsed_label.setText(format_duration(progress.elapsed_seconds))
        self.eta_label.setText(format_duration(progress.eta_seconds))
        self.progress.setValue(int(round(bounded_percent * 10)))
        self.progress.setFormat(format_percent(bounded_percent))

    def transfer_completed(self, job: TransferJob) -> None:
        self.job_label.setText(job.job_id)
        self.session_label.setText(job.session_id)
        self.peer_label.setText(
            format_remote_endpoint(job.remote_display_name, job.remote_ip_address)
        )
        self.file_label.setText(job.items[-1].relative_path.as_posix() if job.items else "-")
        self.files_label.setText(f"{job.completed_file_count} / {job.file_count}")
        self.status_label.setText(job.status.value)
        self.file_bytes_label.setText("-")
        self.job_bytes_label.setText(format_transfer_summary(job))
        self.speed_label.setText("-")
        self.elapsed_label.setText(format_duration(job.elapsed_seconds))
        self.eta_label.setText("00:00:00")
        self.progress.setValue(1000)
        self.progress.setFormat("100 %")

    def transfer_failed(self, job: TransferJob | None = None) -> None:
        if job is not None:
            self.job_label.setText(job.job_id)
            self.session_label.setText(job.session_id)
            self.peer_label.setText(
                format_remote_endpoint(job.remote_display_name, job.remote_ip_address)
            )
            self.files_label.setText(f"{job.completed_file_count} / {job.file_count}")
            self.status_label.setText(job.status.value)
            self.job_bytes_label.setText(format_transfer_summary(job))
            self.elapsed_label.setText(format_duration(job.elapsed_seconds))
        self.progress.setFormat("%p%")


class LogPanelWidget(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setReadOnly(True)
        self.setMaximumBlockCount(400)

    def append_log(self, message: str) -> None:
        self.appendPlainText(message)