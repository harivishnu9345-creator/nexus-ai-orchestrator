from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QFrame
)


class ProjectHubDialog(QDialog):
    open_project = pyqtSignal(dict)
    create_new_clicked = pyqtSignal()

    def __init__(self, projects: list, parent=None):
        super().__init__(parent)
        self.projects = projects
        self.setWindowTitle("Nexus AI Orchestrator — Workspace Manager")
        self.resize(720, 440)
        self._setup_ui()

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
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f6f5f4;
                color: #2e3436;
                border: 1px solid #a7a59f;
                gridline-color: #d3d0c9;
                font-size: 12px;
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

        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #2e3436; border-radius: 3px; padding: 6px;")
        header = QHBoxLayout(header_frame)
        title = QLabel("Saved Swarm Workspaces")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")

        btn_new = QPushButton("+ New Workspace")
        btn_new.setObjectName("primaryBtn")
        btn_new.clicked.connect(self._on_new)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(btn_new)
        layout.addWidget(header_frame)

        self.table = QTableWidget(0, 3)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels(["Workspace Name", "Configured Nodes", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 140)
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
            acc_item = QTableWidgetItem(f"{len(acc_list)} nodes ({providers})")

            btn_open = QPushButton("Load Workspace")
            btn_open.setStyleSheet(
                "padding: 3px 8px; font-size: 11px; background-color: #3584e4; color: #ffffff; border: 1px solid #1b6acb;"
            )
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