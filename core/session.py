"""
SessionManager — tracks the current exercise session on the main thread.

Lifecycle:
  person detected  → start session + begin IDLE_TIMEOUT_SEC countdown
  rep counted      → restart the countdown (keeps session alive while squatting)
  no rep for IDLE_TIMEOUT_SEC (or no person) → save session to DB and reset

The timer is driven by rep activity, not by person-leave events.
This fixes two bugs:
  - session never ending when person stays in frame but stops squatting
  - race condition where person-leave signal arrives after session reset
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from db.database import save_session

IDLE_TIMEOUT_SEC = 5


class SessionManager(QObject):
    session_saved = pyqtSignal(int, str, str)   # reps, started_at ISO, ended_at ISO
    session_ended = pyqtSignal()                # always fires when session resets (even 0 reps)
    reps_updated = pyqtSignal(int)              # live rep count for UI

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._reps = 0
        self._started_at: datetime | None = None

        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(IDLE_TIMEOUT_SEC * 1000)
        self._idle_timer.timeout.connect(self._on_idle_timeout)

    # ------------------------------------------------------------------
    # Slots wired by MainWindow
    # ------------------------------------------------------------------

    def on_person_detected(self, detected: bool) -> None:
        if detected and self._started_at is None:
            # First detection: start session and begin the idle countdown.
            # Reps will keep resetting it; this fires if person stands idle.
            self._started_at = datetime.now()
            self._idle_timer.start()

    def on_rep_counted(self, total_reps: int) -> None:
        if self._started_at is None:
            # Rep arrived before detection signal (edge case after camera reset)
            self._started_at = datetime.now()
        self._reps = total_reps
        self.reps_updated.emit(self._reps)
        # Restart the 5-sec countdown — person is actively squatting
        self._idle_timer.start()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_idle_timeout(self) -> None:
        if self._reps > 0 and self._started_at is not None:
            ended_at = datetime.now()
            save_session(self._reps, self._started_at, ended_at)
            self.session_saved.emit(
                self._reps,
                self._started_at.isoformat(),
                ended_at.isoformat(),
            )

        self._reps = 0
        self._started_at = None
        self.session_ended.emit()
        self.reps_updated.emit(0)
