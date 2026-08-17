"""
Task Table UI Module
Displays tabular graphic data grid using QBrush for text styling to prevent crashes.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QAbstractItemView
)

class TaskTable(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_minimized = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header_bar = QFrame()
        self.header_bar.setStyleSheet("""
            QFrame { background-color: #18181b; border-top: 1px solid #27272a; }
            QLabel { color: #e4e4e7; font-size: 12px; font-weight: bold; font-family: 'Segoe UI', sans-serif;}
            QPushButton { background: transparent; color: #a1a1aa; border: none; font-weight: bold; }
            QPushButton:hover { color: #f4f4f5; }
        """)
        
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(12, 6, 12, 6)
        
        self.title_label = QLabel("Terminal & Task Queue")
        self.btn_toggle = QPushButton("▼")
        self.btn_toggle.setFixedWidth(30)
        self.btn_toggle.clicked.connect(self.toggle_minimize)
        
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_toggle)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Account", "Platform", "Status", "Task / Prompt", "Time / Cooldown"])
        
        self.table.setStyleSheet("""
            QTableWidget { background-color: #09090b; color: #a1a1aa; gridline-color: #27272a; border: none; font-size: 12px;}
            QHeaderView::section { background-color: #18181b; color: #e4e4e7; padding: 4px; border: none; border-right: 1px solid #27272a; border-bottom: 1px solid #27272a; font-weight: bold;}
            QTableWidget::item { padding: 4px; }
        """)
        
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)

        layout.addWidget(self.header_bar)
        layout.addWidget(self.table)
        self.setMaximumHeight(250)

    def toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.table.setVisible(False)
            self.btn_toggle.setText("▲")
            self.setMaximumHeight(35)
        else:
            self.table.setVisible(True)
            self.btn_toggle.setText("▼")
            self.setMaximumHeight(250)

    def update_tasks(self, tasks: list):
        self.table.setRowCount(0)
        bold_font = QFont()
        bold_font.setBold(True)
        
        for task in tasks:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            
            status = task.get("status", "pending")
            color_map = {"queued": "#a1a1aa", "running": "#eab308", "success": "#22c55e", "rate_limited": "#ef4444", "failed": "#ef4444"}
            status_color = color_map.get(status, "#a1a1aa")
            
            acc_item = QTableWidgetItem(task.get("account_id", "Unknown"))
            plat_item = QTableWidgetItem(task.get("platform", "Unknown"))
            
            status_item = QTableWidgetItem(status.upper())
            status_item.setForeground(QBrush(QColor(status_color)))
            status_item.setFont(bold_font)
            
            prompt_text = task.get("prompt_text", "")
            if len(prompt_text) > 60: prompt_text = prompt_text[:57] + "..."
            prompt_item = QTableWidgetItem(prompt_text)
            
            t_time = task.get("target_time")
            time_str = t_time.toString('hh:mm AP') if t_time else "--"
            time_item = QTableWidgetItem(time_str)
            
            if status == "rate_limited":
                time_item.setText(f"Resets: {task.get('cooldown_time', 'Unknown')}")
                time_item.setForeground(QBrush(QColor("#ef4444")))

            self.table.setItem(row_idx, 0, acc_item)
            self.table.setItem(row_idx, 1, plat_item)
            self.table.setItem(row_idx, 2, status_item)
            self.table.setItem(row_idx, 3, prompt_item)
            self.table.setItem(row_idx, 4, time_item)
