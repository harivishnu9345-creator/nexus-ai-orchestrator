from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QMessageBox, QAbstractItemView, QFrame
)
from core.profile_scanner import ChromeProfileScanner
from core.project_manager import ProjectManager


class OnboardingDialog(QDialog):
    project_configured = pyqtSignal(dict)

    def __init__(self, parent=None, project_mgr: ProjectManager = None):
        super().__init__(parent)
        self.setWindowTitle("Nexus AI Orchestrator â€” Configure Swarm Workspace")
        self.resize(760, 520)
        self.scanner = ChromeProfileScanner()
        self.project_mgr = project_mgr or ProjectManager()
        self._setup_ui()
        self._load_discovered_accounts()

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #09090b;
                color: #f4f4f5;
                font-family: 'Ubuntu', 'Cantarell', 'DejaVu Sans', 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #e4e4e7;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #141417;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                color: #f4f4f5;
                padding: 6px 8px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
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
                background-color: #059669;
                color: #ffffff;
                border: 1px solid #10b981;
            }
            QPushButton#primaryBtn:hover {
                background-color: #047857;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        banner = QFrame()
        banner.setStyleSheet("background-color: #141417; border: 1px solid #27272a; border-radius: 4px; padding: 10px;")
        b_layout = QVBoxLayout(banner)
        title_lbl = QLabel("Initialize Multi-Agent Swarm Workspace")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #f4f4f5; border: none;")
        desc_lbl = QLabel(
            "Enter a project name and select the Chromium profiles to mount inside this workspace. "
            "Unlimited profiles are supported via the horizontal viewport scroller."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #a1a1aa; font-size: 11px; border: none;")
        b_layout.addWidget(title_lbl)
        b_layout.addWidget(desc_lbl)
        layout.addWidget(banner)

        name_layout = QHBoxLayout()
        name_lbl = QLabel("Project Workspace Name (Required):")
        name_lbl.setStyleSheet("font-weight: bold;")
        self.proj_name_input = QLineEdit("")
        self.proj_name_input.setPlaceholderText("Enter project name (e.g. YouTube_Ad_Skipper_v1)...")

        name_layout.addWidget(name_lbl)
        name_layout.addWidget(self.proj_name_input, stretch=1)
        layout.addLayout(name_layout)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Mount", "Chromium Profile Directory", "Account Email", "Engine"])
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #09090b;
                alternate-background-color: #121215;
                color: #e4e4e7;
                gridline-color: #27272a;
                border: 1px solid #27272a;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #18181b;
                color: #a1a1aa;
                padding: 6px;
                border: none;
                border-right: 1px solid #27272a;
                border-bottom: 1px solid #27272a;
                font-weight: bold;
                font-size: 11px;
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

        self.proj_name_input.setFocus()

    def _load_discovered_accounts(self):
        try:
            profiles = self.scanner.scan_profiles()
        except Exception:
            profiles = []
        if not profiles:
            profiles = [
                {"profile_dir": "Default", "display_name": "Harivishnu0558", "email": "harivishnu0558@gmail.com"},
                {"profile_dir": "Profile 1", "display_name": "Yasnax678", "email": "yasnax678@gmail.com"},
                {"profile_dir": "Profile 2", "display_name": "Batmanrock1357", "email": "batmanrock1357@gmail.com"},
                {"profile_dir": "Profile 3", "display_name": "Lgostv94", "email": "lgostv94@gmail.com"}
            ]

        self.table.setRowCount(len(profiles))
        for row, p in enumerate(profiles):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked)

            prof = QTableWidgetItem(f"{p['display_name']} ({p['profile_dir']})")
            prof.setData(Qt.ItemDataRole.UserRole, p['profile_dir'])
            prof.setFlags(prof.flags() & ~Qt.ItemFlag.ItemIsEditable)

            email = QTableWidgetItem(p['email'])
            email.setFlags(email.flags() & ~Qt.ItemFlag.ItemIsEditable)

            plat = QTableWidgetItem("Claude")
            plat.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            plat.setFlags(plat.flags() & ~Qt.ItemFlag.ItemIsEditable)
            plat.setForeground(QBrush(QColor("#10b981")))

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
        plat.setForeground(QBrush(QColor("#10b981")))

        self.table.setItem(row, 0, chk)
        self.table.setItem(row, 1, prof)
        self.table.setItem(row, 2, email)
        self.table.setItem(row, 3, plat)

    def _on_launch(self):
        proj_name = self.proj_name_input.text().strip()
        if not proj_name:
            QMessageBox.warning(
                self,
                "Project Name Required",
                "Please enter a name for this project workspace before launching."
            )
            self.proj_name_input.setFocus()
            return

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

        # Check if project name already exists
        existing_proj = self.project_mgr.find_project_by_name(proj_name)
        if existing_proj:
            msg = QMessageBox(self)
            msg.setWindowTitle("Workspace Name Already Exists")
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setText(f"A project workspace named '{proj_name}' already exists.")
            msg.setInformativeText("Would you like to change the name or continue with the existing workspace?")
            btn_change = msg.addButton("Change Name", QMessageBox.ButtonRole.RejectRole)
            btn_continue = msg.addButton("Continue with Existing", QMessageBox.ButtonRole.AcceptRole)
            msg.exec()

            if msg.clickedButton() == btn_change:
                self.proj_name_input.setFocus()
                self.proj_name_input.selectAll()
                return
            elif msg.clickedButton() == btn_continue:
                # Merge or load existing project data
                self.project_configured.emit(existing_proj)
                self.accept()
                return

        new_proj = self.project_mgr.create_project(proj_name, selected_accounts)
        self.project_configured.emit(new_proj)
        self.accept()

