"""
Scheduler Dialog UI Module
Modal for scheduling automated prompt alarms with target AM/PM times.
"""

from PyQt6.QtCore import Qt, QTime, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QTextEdit, QTimeEdit, QFrame
)

class TaskSchedulerDialog(QDialog):
    task_scheduled = pyqtSignal(dict)

    def __init__(self, accounts: list, parent=None):
        super().__init__(parent)
        self.accounts = accounts
        self.setWindowTitle("Schedule Automated Task")
        self.resize(500, 420)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #09090b; color: #f4f4f5; font-family: 'Segoe UI', sans-serif; }
            QLabel { color: #e4e4e7; font-size: 13px; font-weight: bold; }
            QComboBox, QTimeEdit {
                background-color: #18181b; border: 1px solid #27272a; border-radius: 4px;
                color: #ffffff; padding: 6px; font-size: 13px;
            }
            QTextEdit {
                background-color: #18181b; border: 1px solid #27272a; border-radius: 4px;
                color: #ffffff; padding: 8px; font-size: 12px;
            }
            QPushButton {
                background-color: #27272a; color: #ffffff; border: none;
                border-radius: 4px; padding: 8px 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #3f3f46; }
            QPushButton#primaryBtn { background-color: #7c3aed; }
            QPushButton#primaryBtn:hover { background-color: #6d28d9; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Title
        title_lbl = QLabel("⏰ Schedule Automated Prompt")
        title_lbl.setStyleSheet("font-size: 16px; color: #ffffff;")
        layout.addWidget(title_lbl)

        # Account Target Dropdown
        layout.addWidget(QLabel("Target Account:"))
        self.combo_target = QComboBox()
        self.combo_target.addItem("Broadcast to All Accounts", "all")
        for acc in self.accounts:
            self.combo_target.addItem(f"{acc['account_name']} ({acc['platform'].capitalize()})", acc['id'])
        layout.addWidget(self.combo_target)

        # Execution Time (AM/PM Picker)
        layout.addWidget(QLabel("Execution Time (Alarm):"))
        self.time_picker = QTimeEdit()
        self.time_picker.setDisplayFormat("hh:mm AP")
        # Default to 5 minutes from now
        self.time_picker.setTime(QTime.currentTime().addSecs(300))
        layout.addWidget(self.time_picker)

        # Prompt Input Textarea
        layout.addWidget(QLabel("Prompt to Send:"))
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText("Enter the prompt that will automatically trigger at the scheduled time...")
        layout.addWidget(self.prompt_text)

        # Actions
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        
        btn_schedule = QPushButton("Set Schedule Alarm")
        btn_schedule.setObjectName("primaryBtn")
        btn_schedule.clicked.connect(self._on_schedule)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_schedule)
        layout.addLayout(btn_layout)

    def _on_schedule(self):
        prompt = self.prompt_text.toPlainText().strip()
        if not prompt:
            return

        data = {
            "target_id": self.combo_target.currentData(),
            "target_time": self.time_picker.time(),
            "prompt": prompt
        }
        self.task_scheduled.emit(data)
        self.accept()