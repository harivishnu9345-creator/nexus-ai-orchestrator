import os
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, 
    QMessageBox, QAbstractItemView
)
from core.profile_scanner import ChromeProfileScanner

class OnboardingDialog(QDialog):
    project_configured = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nexus AI Orchestrator — Swarm Setup")
        self.resize(750, 520)
        self.scanner = ChromeProfileScanner()
        self._setup_ui()
        self._load_discovered_accounts()

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #09090b; color: #f4f4f5; font-family: 'Segoe UI', sans-serif; }
            QLabel { color: #e4e4e7; font-size: 13px; }
            QLineEdit { background-color: #18181b; border: 1px solid #27272a; border-radius: 4px; color: #f4f4f5; padding: 6px 10px; font-size: 12px; }
            QLineEdit:focus { border-color: #7c3aed; }
            QPushButton { background-color: #27272a; color: #e4e4e7; border: none; border-radius: 4px; padding: 8px 16px; font-weight: 600; font-size: 12px; }
            QPushButton:hover { background-color: #3f3f46; color: #ffffff; }
            QPushButton#primaryBtn { background-color: #7c3aed; color: #ffffff; }
            QPushButton#primaryBtn:hover { background-color: #6d28d9; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title_lbl = QLabel("Create Swarm Workspace")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        desc_lbl = QLabel(
            "Select the Chrome profiles you want to include in this project. "
            "For the MVP Swarm architecture, all accounts are strictly locked to Claude."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #a1a1aa; font-size: 12px;")

        layout.addWidget(title_lbl)
        layout.addWidget(desc_lbl)

        name_layout = QHBoxLayout()
        name_lbl = QLabel("Project Name:")
        name_lbl.setStyleSheet("font-weight: bold;")
        self.proj_name_input = QLineEdit("New Swarm Workspace")

        name_layout.addWidget(name_lbl)
        name_layout.addWidget(self.proj_name_input, stretch=1)
        layout.addLayout(name_layout)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Include", "Chrome Profile", "Signed-In Email", "Platform"])
        self.table.setStyleSheet("""
            QTableWidget { background-color: #18181b; color: #d4d4d8; gridline-color: #27272a; border: 1px solid #27272a; border-radius: 6px; }
            QHeaderView::section { background-color: #27272a; color: #f4f4f5; padding: 6px; border: none; font-weight: bold; }
            QTableWidget::item { padding: 6px; }
        """)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 100)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        layout.addWidget(self.table, stretch=1)

        actions_layout = QHBoxLayout()
        btn_add = QPushButton("+ Add Custom Account")
        btn_add.clicked.connect(self._add_custom_row)
        actions_layout.addWidget(btn_add)
        actions_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_launch = QPushButton("Launch Workspace")
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
            plat.setForeground(Qt.GlobalColor.green)

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

        email = QTableWidgetItem("custom_user@studio.io")

        plat = QTableWidgetItem("Claude")
        plat.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        plat.setFlags(plat.flags() & ~Qt.ItemFlag.ItemIsEditable)
        plat.setForeground(Qt.GlobalColor.green)

        self.table.setItem(row, 0, chk)
        self.table.setItem(row, 1, prof)
        self.table.setItem(row, 2, email)
        self.table.setItem(row, 3, plat)

    def _on_launch(self):
        proj_name = self.proj_name_input.text().strip()
        if not proj_name:
            proj_name = "Untitled Swarm Workspace"

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
                "Swarm Requirements Not Met", 
                "Swarm architecture requires at least 2 accounts (1 Master and at least 1 Worker). Please select at least 2 accounts."
            )
            return

        config = {
            "name": proj_name,
            "accounts": selected_accounts
        }
        self.project_configured.emit(config)
        self.accept()
