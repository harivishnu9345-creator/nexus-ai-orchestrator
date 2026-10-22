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
                background-color: #f6f5f4;
                border: 1px solid #a7a59f;
                border-left: 5px solid #cc0000;
                border-radius: 3px;
            }
            QLabel {
                color: #2e3436;
                font-family: 'Ubuntu', 'DejaVu Sans', sans-serif;
                border: none;
            }
            QPushButton {
                background-color: #e8e6e3;
                color: #2e3436;
                border: 1px solid #a7a59f;
                border-radius: 2px;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 11px;
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
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel(f"Node Alert: {account_name} ({provider.capitalize()})")
        title.setStyleSheet("font-weight: bold; font-size: 12px; color: #cc0000;")

        btn_close = QPushButton("×")
        btn_close.setFixedSize(20, 20)
        btn_close.clicked.connect(self.dismiss)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(btn_close)

        desc = QLabel(f"Injection failed or rate limit encountered. Status: <b>{resets_at}</b>.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #555753; font-size: 11px;")

        actions = QHBoxLayout()
        btn_resume = QPushButton("Wait & Retry")
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