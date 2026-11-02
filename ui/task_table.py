from PyQt6.QtCore import Qt, pyqtSignal, QDateTime, QTime
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
        self.header_bar.setFixedHeight(32)
        self.header_bar.setStyleSheet("""
            QFrame {
                background-color: #141417;
                border-bottom: 1px solid #27272a;
            }
            QLabel {
                color: #e4e4e7;
                font-size: 11px;
                font-weight: bold;
                border: none;
            }
            QPushButton {
                background-color: #1f1f23;
                color: #d4d4d8;
                border: 1px solid #3f3f46;
                border-radius: 3px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27272a;
                color: #ffffff;
            }
        """)

        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(10, 3, 10, 3)

        self.title_label = QLabel("System Task Queue & Execution Log (Persistent Project History)")
        self.btn_clear = QPushButton("Clear Completed")
        self.btn_clear.clicked.connect(self.clear_clicked.emit)

        self.btn_toggle = QPushButton("â–¼")
        self.btn_toggle.setFixedWidth(28)
        self.btn_toggle.clicked.connect(self.toggle_minimize)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_clear)
        header_layout.addWidget(self.btn_toggle)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "Account ID", "Platform", "Status", "Task / Prompt Payload", "Scheduled Date & Time"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #09090b;
                alternate-background-color: #121215;
                color: #e4e4e7;
                gridline-color: #27272a;
                border: none;
                font-size: 12px;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #18181b;
                color: #a1a1aa;
                padding: 5px 8px;
                border: none;
                border-right: 1px solid #27272a;
                border-bottom: 1px solid #27272a;
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
        layout.addWidget(self.table, stretch=1)

    def toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.table.setVisible(False)
            self.btn_toggle.setText("â–²")
        else:
            self.table.setVisible(True)
            self.btn_toggle.setText("â–¼")

    def update_tasks(self, tasks: list):
        self.table.setRowCount(0)
        bold_font = QFont()
        bold_font.setBold(True)

        for task in tasks:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            status = task.get("status", "pending")
            color_map = {
                "queued": "#38bdf8",
                "held_for_gate": "#eab308",
                "running": "#f97316",
                "success": "#10b981",
                "rate_limited": "#ef4444",
                "failed": "#ef4444"
            }
            status_color = color_map.get(status, "#a1a1aa")

            acc_item = QTableWidgetItem(task.get("account_name") or task.get("account_id", "Unknown"))
            plat_item = QTableWidgetItem(task.get("platform", "Unknown"))

            status_item = QTableWidgetItem(status.upper())
            status_item.setForeground(QBrush(QColor(status_color)))
            status_item.setFont(bold_font)

            prompt_text = task.get("prompt_text", "").replace("\n", " ")
            if len(prompt_text) > 80:
                prompt_text = prompt_text[:77] + "..."

            file_paths = task.get("file_paths") or []
            if file_paths:
                prompt_text = f"[{len(file_paths)} file(s)] {prompt_text}"

            prompt_item = QTableWidgetItem(prompt_text)

            dt_str = task.get("target_datetime_str")
            t_dt = task.get("target_datetime")
            t_time = task.get("target_time")

            if isinstance(t_dt, QDateTime) and t_dt.isValid():
                time_str = t_dt.toString("yyyy-MM-dd hh:mm:ss AP")
            elif dt_str:
                time_str = dt_str
            elif isinstance(t_time, QTime) and t_time.isValid():
                today_str = QDateTime.currentDateTime().toString("yyyy-MM-dd")
                time_str = f"{today_str} {t_time.toString('hh:mm:ss AP')}"
            else:
                time_str = "--"

            if status == "held_for_gate":
                stage_num = task.get("stage_index", 0) + 1
                time_str = f"Waiting for Gate #{stage_num - 1} ({time_str})"

            time_item = QTableWidgetItem(time_str)

            if status == "rate_limited":
                time_item.setText(f"Resets: {task.get('cooldown_time', 'Unknown')}")
                time_item.setForeground(QBrush(QColor("#ef4444")))
            elif status == "held_for_gate":
                time_item.setForeground(QBrush(QColor("#eab308")))

            self.table.setItem(row_idx, 0, acc_item)
            self.table.setItem(row_idx, 1, plat_item)
            self.table.setItem(row_idx, 2, status_item)
            self.table.setItem(row_idx, 3, prompt_item)
            self.table.setItem(row_idx, 4, time_item)
