import os
from PyQt6.QtCore import Qt, QDateTime, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QDateTimeEdit, QFileDialog
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
                background-color: #09090b;
                color: #f4f4f5;
                font-family: 'Ubuntu', 'Cantarell', 'DejaVu Sans', sans-serif;
            }
            QLabel {
                color: #e4e4e7;
                font-size: 12px;
                font-weight: bold;
            }
            QComboBox, QDateTimeEdit, QTextEdit {
                background-color: #141417;
                border: 1px solid #27272a;
                border-radius: 4px;
                color: #f4f4f5;
                padding: 6px;
                font-size: 12px;
            }
            QComboBox:focus, QDateTimeEdit:focus, QTextEdit:focus {
                border: 1px solid #3b82f6;
            }
            QComboBox QAbstractItemView {
                background-color: #141417;
                color: #f4f4f5;
                selection-background-color: #2563eb;
                border: 1px solid #27272a;
            }
            QPushButton {
                background-color: #1f1f23;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #27272a;
                color: #ffffff;
            }
            QPushButton#primaryBtn {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #3b82f6;
            }
            QPushButton#primaryBtn:hover {
                background-color: #1d4ed8;
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

        layout.addWidget(QLabel("Scheduled Execution Date & Time:"))
        self.datetime_picker = QDateTimeEdit()
        self.datetime_picker.setCalendarPopup(True)
        self.datetime_picker.setDisplayFormat("yyyy-MM-dd hh:mm:ss AP")
        self.datetime_picker.setDateTime(QDateTime.currentDateTime().addSecs(60))
        layout.addWidget(self.datetime_picker)

        layout.addWidget(QLabel("Prompt Payload:"))
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText("Enter prompt to dispatch at scheduled date & time...")
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
            self.btn_attach.setStyleSheet("background-color: #065f46; color: #a7f3d0; border: 1px solid #10b981;")
            self.btn_attach.setText(f"Attached: {os.path.basename(file_path)}")

    def _on_schedule(self):
        prompt = self.prompt_text.toPlainText().strip()
        if not prompt and not self.attached_file_path:
            return
        dt = self.datetime_picker.dateTime()
        self.task_scheduled.emit({
            "target_id": self.combo_target.currentData(),
            "target_datetime": dt,
            "target_time": dt.time(),
            "prompt": prompt,
            "file_path": self.attached_file_path
        })
        self.accept()
