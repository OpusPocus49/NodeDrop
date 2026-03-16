from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from gui.app_bridge import AppBridge


class TransferWorker(QObject):
    """
    Worker Qt used to launch a blocking transfer outside the UI thread.
    """

    started = Signal(str, str)          # peer_id, source_path
    finished = Signal(str, str)         # peer_id, source_path
    failed = Signal(str)                # error message

    def __init__(
        self,
        bridge: AppBridge,
        peer_id: str,
        source_path: str,
    ) -> None:
        super().__init__()
        self._bridge = bridge
        self._peer_id = peer_id
        self._source_path = source_path

    @Slot()
    def run(self) -> None:
        try:
            self.started.emit(self._peer_id, self._source_path)
            self._bridge.send_transfer(self._peer_id, self._source_path)
            self.finished.emit(self._peer_id, self._source_path)
        except Exception as exc:
            self.failed.emit(str(exc))