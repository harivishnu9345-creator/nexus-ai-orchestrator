"""
Toast Notification UI Module
Provides non-blocking alert cards for rate limits, cooldowns, and system actions
with clickable response buttons ([Wait & Auto-Resume], [Reroute], [Dismiss]).
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)

class RateLimitToast(QFrame):
    # Signals for user actions on the toast
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
                background-color: #18181b; 
                border: 1px solid #27272a; 
                border-left: 4px solid #ef4444; 
                border-radius: 6px; 
            }
            QLabel { 
                color: #f4f4f5; 
                font-family: 'Segoe UI', sans-serif; 
            }
            QPushButton { 
                background-color: #27272a; 
                color: #e4e4e7; 
                border: none; 
                border-radius: 4px; 
                padding: 4px 8px; 
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { 
                background-color: #3f3f46; 
                color: #ffffff; 
            }
            QPushButton#primaryBtn { 
                background-color: #7c3aed; 
                color: #ffffff; 
            }
            QPushButton#primaryBtn:hover { 
                background-color: #6d28d9; 
            }
        """)
        self.setFixedWidth(360)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header section
        header = QHBoxLayout()
        title = QLabel(f"⚠️ Rate Limit Reached: {account_name} ({provider.capitalize()})")
        title.setStyleSheet("font-weight: bold; font-size: 12px; color: #f87171;")
        
        btn_close = QPushButton("×")
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet("background: transparent; color: #a1a1aa; border: none; font-size: 14px;")
        btn_close.clicked.connect(self.dismiss)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(btn_close)

        # Description Message
        desc = QLabel(f"This account has hit its token limit. Cooldown resets at <b>{resets_at}</b>.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #a1a1aa; font-size: 11px;")

        # Actions Layout
        actions = QHBoxLayout()
        actions.setSpacing(6)
        
        btn_resume = QPushButton("Wait & Auto-Resume")
        btn_resume.setObjectName("primaryBtn")
        btn_resume.clicked.connect(lambda: (self.auto_resume_clicked.emit(self.account_id), self.deleteLater()))

        btn_reroute = QPushButton("Reroute Task")
        btn_reroute.clicked.connect(lambda: (self.reroute_clicked.emit(self.account_id), self.deleteLater()))

        btn_dismiss = QPushButton("Dismiss")
        btn_dismiss.clicked.connect(self.dismiss)

        actions.addWidget(btn_resume)
        actions.addWidget(btn_reroute)
        actions.addWidget(btn_dismiss)
        actions.addStretch()

        layout.addLayout(header)
        layout.addWidget(desc)
        layout.addLayout(actions)

    def dismiss(self):
        self.dismiss_clicked.emit(self.account_id)
        self.deleteLater()
