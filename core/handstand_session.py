"""
HandstandSessionManager — tracks the current handstand hold on the main thread.

Lifecycle:
  handstand_started → record start time, emit state_changed("BALANCING")
  handstand_lost    → compute duration, save to DB, emit session_saved + state_changed("FALLING")
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from db.database import save_handstand_session


class HandstandSessionManager(QObject):
    session_saved = pyqtSignal(float, str, str)   # duration, started_at ISO, ended_at ISO
    state_changed = pyqtSignal(str)               # "BALANCING" | "FALLING"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._started_at: datetime | None = None

    def on_handstand_started(self) -> None:
        self._started_at = datetime.now()
        self.state_changed.emit("BALANCING")

    def on_handstand_lost(self) -> None:
        if self._started_at is None:
            return
        ended_at = datetime.now()
        duration = (ended_at - self._started_at).total_seconds()
        save_handstand_session(self._started_at, ended_at, duration)
        self.session_saved.emit(duration, self._started_at.isoformat(), ended_at.isoformat())
        self.state_changed.emit("FALLING")
        self._started_at = None
