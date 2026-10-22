from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QAbstractItemView
)


class TaskTable(QWidget):
    clear_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_minimized = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header_bar = QFrame()
        self.header_bar.setFixedHeight(30)
        self.header_bar.setStyleSheet("""
            QFrame {
                background-color: #d3d0c9;
                border-top: 1px solid #9a9790;
                border-bottom: 1px solid #b5b2ac;
            }
            QLabel {
                color: #2e3436;
                font-size: 12px;
                font-weight: bold;
                border: none;
            }
            QPushButton {
                background-color: #e8e6e3;
                color: #2e3436;
                border: 1px solid #a7a59f;
                border-radius: 2px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ffffff;
            }
        """)

        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(10, 3, 10, 3)

        self.title_label = QLabel("System Task Queue & Execution Log")
        self.btn_clear = QPushButton("Clear Completed")
        self.btn_clear.clicked.connect(self.clear_clicked.emit)

        self.btn_toggle = QPushButton("▼")
        self.btn_toggle.setFixedWidth(28)
        self.btn_toggle.clicked.connect(self.toggle_minimize)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_clear)
        header_layout.addWidget(self.btn_toggle)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "Account ID", "Platform", "Status", "Task / Prompt Payload", "Scheduled Time"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f6f5f4;
                color: #2e3436;
                gridline-color: #d3d0c9;
                border: none;
                font-size: 12px;
                selection-background-color: #4a90d9;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #e8e6e3;
                color: #2e3436;
                padding: 4px 8px;
                border: none;
                border-right: 1px solid #b5b2ac;
                border-bottom: 1px solid #a7a59f;
                font-weight: bold;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 4px 6px;
            }
        """)

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)

        layout.addWidget(self.header_bar)
        layout.addWidget(self.table)
        self.setMaximumHeight(210)

    def toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.table.setVisible(False)
            self.btn_toggle.setText("▲")
            self.setMaximumHeight(30)
        else:
            self.table.setVisible(True)
            self.btn_toggle.setText("▼")
            self.setMaximumHeight(210)

    def update_tasks(self, tasks: list):
        self.table.setRowCount(0)
        bold_font = QFont()
        bold_font.setBold(True)

        for task in tasks:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            status = task.get("status", "pending")
            color_map = {
                "queued": "#555753",
                "running": "#c46200",
                "success": "#3b7a20",
                "rate_limited": "#cc0000",
                "failed": "#cc0000"
            }
            status_color = color_map.get(status, "#555753")

            acc_item = QTableWidgetItem(task.get("account_id", "Unknown"))
            plat_item = QTableWidgetItem(task.get("platform", "Unknown"))

            status_item = QTableWidgetItem(status.upper())
            status_item.setForeground(QBrush(QColor(status_color)))
            status_item.setFont(bold_font)

            prompt_text = task.get("prompt_text", "").replace("\n", " ")
            if len(prompt_text) > 75:
                prompt_text = prompt_text[:72] + "..."
            prompt_item = QTableWidgetItem(prompt_text)

            t_time = task.get("target_time")
            time_str = t_time.toString('hh:mm:ss AP') if t_time else "--"
            time_item = QTableWidgetItem(time_str)

            if status == "rate_limited":
                time_item.setText(f"Resets: {task.get('cooldown_time', 'Unknown')}")
                time_item.setForeground(QBrush(QColor("#cc0000")))

            self.table.setItem(row_idx, 0, acc_item)
            self.table.setItem(row_idx, 1, plat_item)
            self.table.setItem(row_idx, 2, status_item)
            self.table.setItem(row_idx, 3, prompt_item)
            self.table.setItem(row_idx, 4, time_item)