from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame


class RateLimitToast(QFrame):
    auto_resume_clicked = pyqtSignal(str)
    reroute_clicked = pyqtSignal(str)
    dismiss_clicked = pyqtSignal(str)

    def __init__(self, account_id: str, account_name: str, provider: str, resets_at: str, parent=None):
        super().__init__(parent)
        self.account_id = account_id
        self._setup_ui(account_name, provider, resets_at)

    def _setup_ui(self, account_name: str, provider: str, resets_at: str):
        self.setObjectName("ToastCard")
        self.setStyleSheet("""
            #ToastCard {
                background-color: #141417;
                border: 1px solid #27272a;
                border-left: 5px solid #ef4444;
                border-radius: 6px;
            }
            QLabel {
                color: #f4f4f5;
                font-family: 'Ubuntu', 'DejaVu Sans', sans-serif;
                border: none;
            }
            QPushButton {
                background-color: #1f1f23;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 11px;
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
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel(f"Node Alert: {account_name} ({provider.capitalize()})")
        title.setStyleSheet("font-weight: bold; font-size: 12px; color: #f87171;")

        btn_close = QPushButton("×")
        btn_close.setFixedSize(22, 22)
        btn_close.clicked.connect(self.dismiss)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(btn_close)

        desc = QLabel(f"Injection failed or rate limit encountered. Cooldown resets at: <b>{resets_at}</b>.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #a1a1aa; font-size: 11px;")

        actions = QHBoxLayout()
        btn_resume = QPushButton("Auto-Retry (2m)")
        btn_resume.setObjectName("primaryBtn")
        btn_resume.clicked.connect(lambda: (self.auto_resume_clicked.emit(self.account_id), self.deleteLater()))

        btn_dismiss = QPushButton("Dismiss")
        btn_dismiss.clicked.connect(self.dismiss)

        actions.addWidget(btn_resume)
        actions.addWidget(btn_dismiss)
        actions.addStretch()

        layout.addLayout(header)
        layout.addWidget(desc)
        layout.addLayout(actions)

    def dismiss(self):
        self.dismiss_clicked.emit(self.account_id)
        self.deleteLater()
