from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QMessageBox, QAbstractItemView, QFrame
)
from core.profile_scanner import ChromeProfileScanner


class OnboardingDialog(QDialog):
    project_configured = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nexus AI Orchestrator — Configure Swarm Workspace")
        self.resize(760, 520)
        self.scanner = ChromeProfileScanner()
        self._setup_ui()
        self._load_discovered_accounts()

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #dcdad5;
                color: #2e3436;
                font-family: 'Ubuntu', 'Cantarell', 'DejaVu Sans', 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #2e3436;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #a7a59f;
                border-radius: 3px;
                color: #2e3436;
                padding: 6px 8px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #4a90d9;
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
                background-color: #5a8e3e;
                color: #ffffff;
                border: 1px solid #46712f;
            }
            QPushButton#primaryBtn:hover {
                background-color: #689d4a;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        banner = QFrame()
        banner.setStyleSheet("background-color: #2e3436; border-radius: 3px; padding: 8px;")
        b_layout = QVBoxLayout(banner)
        title_lbl = QLabel("Initialize Multi-Agent Swarm Workspace")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        desc_lbl = QLabel(
            "Select the Chromium profiles to mount inside this workspace. "
            "Unlimited profiles are supported via the horizontal viewport scroller."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #d3d7cf; font-size: 11px;")
        b_layout.addWidget(title_lbl)
        b_layout.addWidget(desc_lbl)
        layout.addWidget(banner)

        name_layout = QHBoxLayout()
        name_lbl = QLabel("Workspace Name:")
        name_lbl.setStyleSheet("font-weight: bold;")
        self.proj_name_input = QLineEdit("New Swarm Workspace")

        name_layout.addWidget(name_lbl)
        name_layout.addWidget(self.proj_name_input, stretch=1)
        layout.addLayout(name_layout)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Mount", "Chromium Profile Directory", "Account Email", "Engine"])
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f6f5f4;
                color: #2e3436;
                gridline-color: #d3d0c9;
                border: 1px solid #a7a59f;
            }
            QHeaderView::section {
                background-color: #e8e6e3;
                color: #2e3436;
                padding: 5px;
                border: none;
                border-right: 1px solid #b5b2ac;
                border-bottom: 1px solid #a7a59f;
                font-weight: bold;
            }
        """)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 100)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        layout.addWidget(self.table, stretch=1)

        actions_layout = QHBoxLayout()
        btn_add = QPushButton("+ Add Custom Profile")
        btn_add.clicked.connect(self._add_custom_row)
        actions_layout.addWidget(btn_add)
        actions_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_launch = QPushButton("Launch Workstation")
        btn_launch.setObjectName("primaryBtn")
        btn_launch.clicked.connect(self._on_launch)

        actions_layout.addWidget(btn_cancel)
        actions_layout.addWidget(btn_launch)
        layout.addLayout(actions_layout)

    def _load_discovered_accounts(self):
        profiles = self.scanner.scan_profiles()
        if not profiles:
            profiles = [{"profile_dir": "Default", "display_name": "Default Profile", "email": "user@gmail.com"}]

        self.table.setRowCount(len(profiles))
        for row, p in enumerate(profiles):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked if row < 2 else Qt.CheckState.Unchecked)

            prof = QTableWidgetItem(f"{p['display_name']} ({p['profile_dir']})")
            prof.setData(Qt.ItemDataRole.UserRole, p['profile_dir'])
            prof.setFlags(prof.flags() & ~Qt.ItemFlag.ItemIsEditable)

            email = QTableWidgetItem(p['email'])
            email.setFlags(email.flags() & ~Qt.ItemFlag.ItemIsEditable)

            plat = QTableWidgetItem("Claude")
            plat.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            plat.setFlags(plat.flags() & ~Qt.ItemFlag.ItemIsEditable)
            plat.setForeground(QBrush(QColor("#3b7a20")))

            self.table.setItem(row, 0, chk)
            self.table.setItem(row, 1, prof)
            self.table.setItem(row, 2, email)
            self.table.setItem(row, 3, plat)

    def _add_custom_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)

        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk.setCheckState(Qt.CheckState.Checked)

        prof = QTableWidgetItem(f"Custom Profile {row + 1}")
        prof.setData(Qt.ItemDataRole.UserRole, f"custom_profile_{row + 1}")

        email = QTableWidgetItem(f"node_{row + 1}@workstation.local")

        plat = QTableWidgetItem("Claude")
        plat.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        plat.setFlags(plat.flags() & ~Qt.ItemFlag.ItemIsEditable)
        plat.setForeground(QBrush(QColor("#3b7a20")))

        self.table.setItem(row, 0, chk)
        self.table.setItem(row, 1, prof)
        self.table.setItem(row, 2, email)
        self.table.setItem(row, 3, plat)

    def _on_launch(self):
        proj_name = self.proj_name_input.text().strip() or "Untitled Swarm Workspace"

        selected_accounts = []
        for r in range(self.table.rowCount()):
            chk_item = self.table.item(r, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                prof_item = self.table.item(r, 1)
                email_item = self.table.item(r, 2)

                profile_id = prof_item.data(Qt.ItemDataRole.UserRole) or f"profile_{r}"
                email = email_item.text() if email_item else "unknown"

                selected_accounts.append({
                    "id": f"acc_{r}_{profile_id}",
                    "profile_id": profile_id,
                    "account_name": email.split("@")[0].capitalize(),
                    "email": email,
                    "platform": "claude",
                    "current_url": "https://claude.ai/new"
                })

        if len(selected_accounts) < 2:
            QMessageBox.warning(
                self,
                "Insufficient Nodes Selected",
                "Swarm architecture requires at least 2 accounts (1 Master and 1+ Worker)."
            )
            return

        self.project_configured.emit({"name": proj_name, "accounts": selected_accounts})
        self.accept()