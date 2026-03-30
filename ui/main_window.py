"""
MainWindow — full-screen camera feed with overlaid HUD and history button.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, QRect
from PyQt6.QtGui import QImage, QPixmap, QFont, QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QSizePolicy,
)

from core.camera import CameraThread
from core.session import SessionManager
from db.database import init_db


class VideoWidget(QLabel):
    """
    Displays camera frames scaled to fill the available space.
    Paints a large rep counter on top of the frame via paintEvent.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #0d0d0d;")
        self._pixmap: QPixmap | None = None
        self._count: int = 0

    def set_frame(self, image: QImage) -> None:
        self._pixmap = QPixmap.fromImage(image)
        self.update()           # triggers paintEvent

    def set_count(self, n: int) -> None:
        self._count = n
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)

        # ── background ──────────────────────────────────────────────────
        painter.fillRect(self.rect(), QColor("#0d0d0d"))

        # ── video frame ─────────────────────────────────────────────────
        if self._pixmap:
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

        # ── rep counter ─────────────────────────────────────────────────
        if self._count > 0:
            text = str(self._count)

            font_px = max(100, self.height() // 3)
            font = QFont("Monospace", font_px, QFont.Weight.Black)
            painter.setFont(font)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(text)
            text_h = fm.height()

            pad_x, pad_y = 48, 20
            pill_w = text_w + pad_x * 2
            pill_h = text_h + pad_y * 2
            pill_x = (self.width() - pill_w) // 2
            pill_y = (self.height() - pill_h) // 2

            # Semi-transparent dark pill
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 170))
            painter.drawRoundedRect(pill_x, pill_y, pill_w, pill_h, pill_h // 2, pill_h // 2)

            # Green border
            painter.setPen(QPen(QColor(16, 185, 129, 140), 4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(pill_x, pill_y, pill_w, pill_h, pill_h // 2, pill_h // 2)

            # Number
            painter.setPen(QColor(16, 185, 129))
            painter.drawText(pill_x + pad_x, pill_y + pad_y + fm.ascent(), text)

        painter.end()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Squat Counter")
        self.showFullScreen()

        init_db()
        self._build_ui()
        self._setup_backend()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        root.setStyleSheet("background-color: #0d0d0d;")

        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addLayout(self._make_top_bar())

        self._video = VideoWidget()
        layout.addWidget(self._video, stretch=1)

        layout.addLayout(self._make_bottom_bar())

    def _make_top_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(16, 8, 16, 8)

        title = QLabel("Squat Counter")
        title.setFont(QFont("Sans Serif", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #e0e0e0;")

        self._status_dot = QLabel("⬤  No person")
        self._status_dot.setStyleSheet("color: #6b7280; font-size: 13px;")

        history_btn = QPushButton("History")
        history_btn.setFixedSize(QSize(100, 32))
        history_btn.setStyleSheet("""
            QPushButton {
                background: #4f46e5; color: white;
                border: none; border-radius: 6px; font-size: 13px;
            }
            QPushButton:hover { background: #6366f1; }
        """)
        history_btn.clicked.connect(self._open_history)

        quit_btn = QPushButton("Quit")
        quit_btn.setFixedSize(QSize(70, 32))
        quit_btn.setStyleSheet("""
            QPushButton {
                background: #374151; color: #e5e7eb;
                border: none; border-radius: 6px; font-size: 13px;
            }
            QPushButton:hover { background: #6b7280; }
        """)
        quit_btn.clicked.connect(self.close)

        row.addWidget(title)
        row.addStretch()
        row.addWidget(self._status_dot)
        row.addSpacing(24)
        row.addWidget(history_btn)
        row.addSpacing(8)
        row.addWidget(quit_btn)
        return row

    def _make_bottom_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(16, 6, 16, 10)

        self._session_info = QLabel("Waiting for activity...")
        self._session_info.setStyleSheet("color: #9ca3af; font-size: 13px;")

        row.addWidget(self._session_info, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addStretch()
        return row

    def _setup_backend(self) -> None:
        self._session = SessionManager(self)
        self._session.reps_updated.connect(self._on_reps_updated)
        self._session.session_saved.connect(self._on_session_saved)
        self._session.session_ended.connect(self._camera_reset)

        self._camera = CameraThread(camera_index=0, parent=self)
        self._camera.frame_ready.connect(self._video.set_frame)
        self._camera.person_detected.connect(self._on_person_detected)
        self._camera.person_detected.connect(self._session.on_person_detected)
        self._camera.rep_counted.connect(self._session.on_rep_counted)
        self._camera.start()

    def _on_person_detected(self, detected: bool) -> None:
        if detected:
            self._status_dot.setText("⬤  Person detected")
            self._status_dot.setStyleSheet("color: #10b981; font-size: 13px;")
            self._session_info.setText("Session active — start squatting!")
        else:
            self._status_dot.setText("⬤  No person")
            self._status_dot.setStyleSheet("color: #6b7280; font-size: 13px;")

    def _on_reps_updated(self, count: int) -> None:
        self._video.set_count(count)
        if count == 0:
            self._session_info.setText("Waiting for activity...")

    def _on_session_saved(self, reps: int, started_at: str, ended_at: str) -> None:
        self._session_info.setText(f"Session saved: {reps} rep{'s' if reps != 1 else ''}")

    def _camera_reset(self) -> None:
        self._camera.reset_session()

    def _open_history(self) -> None:
        from ui.history_view import HistoryDialog
        dlg = HistoryDialog(self)
        dlg.exec()

    def closeEvent(self, event) -> None:
        self._camera.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        super().keyPressEvent(event)
