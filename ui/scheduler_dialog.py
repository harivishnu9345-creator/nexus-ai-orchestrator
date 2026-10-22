import os
from PyQt6.QtCore import Qt, QTime, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QTimeEdit, QFileDialog
)


class TaskSchedulerDialog(QDialog):
    task_scheduled = pyqtSignal(dict)

    def __init__(self, accounts: list, parent=None):
        super().__init__(parent)
        self.accounts = accounts
        self.attached_file_path = None
        self.setWindowTitle("Schedule Automated Prompt")
        self.resize(480, 440)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #dcdad5;
                color: #2e3436;
                font-family: 'Ubuntu', 'Cantarell', 'DejaVu Sans', sans-serif;
            }
            QLabel {
                color: #2e3436;
                font-size: 12px;
                font-weight: bold;
            }
            QComboBox, QTimeEdit, QTextEdit {
                background-color: #ffffff;
                border: 1px solid #a7a59f;
                border-radius: 3px;
                color: #2e3436;
                padding: 5px;
                font-size: 12px;
            }
            QPushButton {
                background-color: #f4f3f1;
                color: #2e3436;
                border: 1px solid #a7a59f;
                border-radius: 3px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ffffff;
            }
            QPushButton#primaryBtn {
                background-color: #3584e4;
                color: #ffffff;
                border: 1px solid #1b6acb;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Target Node:"))
        self.combo_target = QComboBox()
        self.combo_target.addItem("Broadcast to All Active Nodes", "all")
        for acc in self.accounts:
            self.combo_target.addItem(f"{acc['account_name']} ({acc['platform'].capitalize()})", acc['id'])
        layout.addWidget(self.combo_target)

        layout.addWidget(QLabel("Scheduled Execution Time:"))
        self.time_picker = QTimeEdit()
        self.time_picker.setDisplayFormat("hh:mm:ss AP")
        self.time_picker.setTime(QTime.currentTime().addSecs(60))
        layout.addWidget(self.time_picker)

        layout.addWidget(QLabel("Prompt Payload:"))
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText("Enter prompt to dispatch at scheduled time...")
        layout.addWidget(self.prompt_text)

        self.btn_attach = QPushButton("Attach Document to Task...")
        self.btn_attach.clicked.connect(self._on_attach_file)
        layout.addWidget(self.btn_attach)

        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_schedule = QPushButton("Queue Scheduled Task")
        btn_schedule.setObjectName("primaryBtn")
        btn_schedule.clicked.connect(self._on_schedule)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_schedule)
        layout.addLayout(btn_layout)

    def _on_attach_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Document", "", "All Files (*.*)")
        if file_path:
            self.attached_file_path = file_path
            self.btn_attach.setStyleSheet("background-color: #5a8e3e; color: white;")
            self.btn_attach.setText(f"Attached: {os.path.basename(file_path)}")

    def _on_schedule(self):
        prompt = self.prompt_text.toPlainText().strip()
        if not prompt and not self.attached_file_path:
            return
        self.task_scheduled.emit({
            "target_id": self.combo_target.currentData(),
            "target_time": self.time_picker.time(),
            "prompt": prompt,
            "file_path": self.attached_file_path
        })
        self.accept()