"""
Project Hub UI Module
Displays saved projects on startup so existing workspaces and chat URLs are restored.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)

class ProjectHubDialog(QDialog):
    open_project = pyqtSignal(dict)
    create_new_clicked = pyqtSignal()

    def __init__(self, projects: list, parent=None):
        super().__init__(parent)
        self.projects = projects
        self.setWindowTitle("Nexus AI Orchestrator — Project Hub")
        self.resize(700, 420)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #09090b; color: #f4f4f5; font-family: 'Segoe UI', sans-serif; }
            QLabel { color: #e4e4e7; font-size: 13px; }
            QTableWidget {
                background-color: #18181b; color: #d4d4d8; border: 1px solid #27272a;
                border-radius: 6px; font-size: 12px;
            }
            QHeaderView::section { background-color: #27272a; color: #ffffff; padding: 6px; border: none; font-weight: bold; }
            QPushButton { background-color: #27272a; color: #ffffff; border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #3f3f46; }
            QPushButton#primaryBtn { background-color: #7c3aed; }
            QPushButton#primaryBtn:hover { background-color: #6d28d9; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Saved Project Workspaces")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        
        btn_new = QPushButton("+ New Project")
        btn_new.setObjectName("primaryBtn")
        btn_new.clicked.connect(self._on_new)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(btn_new)
        layout.addLayout(header)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Project Name", "Accounts Linked", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 130)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, stretch=1)

        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(len(self.projects))
        for row, proj in enumerate(self.projects):
            name_item = QTableWidgetItem(proj.get("name", "Untitled"))
            acc_list = proj.get("accounts", [])
            providers = ", ".join([a.get("platform", "").capitalize() for a in acc_list])
            acc_item = QTableWidgetItem(f"{len(acc_list)} accounts ({providers})")
            
            btn_open = QPushButton("Open Workspace")
            btn_open.setStyleSheet("padding: 4px 8px; font-size: 11px; background-color: #7c3aed;")
            btn_open.clicked.connect(lambda _, p=proj: self._on_open(p))

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, acc_item)
            self.table.setCellWidget(row, 2, btn_open)

    def _on_open(self, project):
        self.open_project.emit(project)
        self.accept()

    def _on_new(self):
        self.create_new_clicked.emit()
        self.accept()
