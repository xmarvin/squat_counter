"""
HandstandStatsDialog — shows all saved handstand sessions in a table.
Columns: Date | Time | Seconds
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy,
)

from db.database import get_all_handstand_sessions

_STYLE = """
QDialog {
    background-color: #111827;
}
QLabel {
    color: #e5e7eb;
}
QTableWidget {
    background-color: #1f2937;
    alternate-background-color: #111827;
    color: #e5e7eb;
    gridline-color: #374151;
    border: none;
    font-size: 13px;
}
QHeaderView::section {
    background-color: #374151;
    color: #9ca3af;
    padding: 6px;
    border: none;
    font-size: 12px;
}
QTableWidget::item:selected {
    background-color: #4f46e5;
    color: white;
}
QPushButton {
    background: #374151; color: #e5e7eb;
    border: none; border-radius: 6px;
    font-size: 13px; padding: 6px 16px;
}
QPushButton:hover { background: #6b7280; }
"""


class HandstandStatsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Handstand Sessions")
        self.resize(480, 400)
        self.setStyleSheet(_STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Handstand Sessions")
        title.setFont(QFont("Sans Serif", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Date", "Time", "Seconds"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._table, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._load_data()

    def _load_data(self) -> None:
        rows = get_all_handstand_sessions()
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            started = row["started_at"]
            # started_at is an ISO string: "2026-03-30T14:22:05.123456"
            try:
                date_str, time_str = started.split("T")
                time_str = time_str[:8]   # HH:MM:SS
            except ValueError:
                date_str = started
                time_str = ""

            duration_str = f"{row['duration']:.1f}s"

            self._table.setItem(i, 0, QTableWidgetItem(date_str))
            self._table.setItem(i, 1, QTableWidgetItem(time_str))
            dur_item = QTableWidgetItem(duration_str)
            dur_item.setData(Qt.ItemDataRole.UserRole, row["duration"])
            self._table.setItem(i, 2, dur_item)
