"""
HistoryDialog — shows a bar chart of daily squat totals for the last 30 days.
"""

from __future__ import annotations

from datetime import date, timedelta

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt

from db.database import get_daily_totals

DAYS_BACK = 30


class HistoryDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Squat History")
        self.resize(800, 450)
        self._build_ui()
        self._load_chart()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Squats per day — last 30 days")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(title)

        self._canvas = FigureCanvasQTAgg(Figure(figsize=(10, 4), facecolor="#1e1e2e"))
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._canvas)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _load_chart(self) -> None:
        today = date.today()
        from_date = today - timedelta(days=DAYS_BACK - 1)

        rows = get_daily_totals(from_date, today)
        data: dict[str, int] = {r[0]: r[1] for r in rows}

        # Fill all days in range (zeros for missing days)
        labels = []
        values = []
        for i in range(DAYS_BACK):
            d = from_date + timedelta(days=i)
            key = d.isoformat()
            labels.append(d.strftime("%m/%d"))
            values.append(data.get(key, 0))

        ax = self._canvas.figure.add_subplot(111, facecolor="#2a2a3e")
        bars = ax.bar(labels, values, color="#7c3aed", edgecolor="#a78bfa", linewidth=0.5)

        # Highlight today
        bars[-1].set_color("#10b981")
        bars[-1].set_edgecolor("#34d399")

        ax.set_xlabel("Date", color="#9ca3af", fontsize=9)
        ax.set_ylabel("Reps", color="#9ca3af", fontsize=9)
        ax.tick_params(colors="#9ca3af", labelsize=7)
        ax.spines["bottom"].set_color("#4b5563")
        ax.spines["left"].set_color("#4b5563")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Show every 5th label to avoid crowding
        for i, label in enumerate(ax.get_xticklabels()):
            if i % 5 != 0:
                label.set_visible(False)

        if any(v > 0 for v in values):
            ax.set_ylim(0, max(values) * 1.2)

        self._canvas.figure.tight_layout(pad=1.5)
        self._canvas.draw()
