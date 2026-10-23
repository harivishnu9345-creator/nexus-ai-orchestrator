import os
from PyQt6.QtCore import Qt, QTime
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QComboBox, QSplitter, QLabel,
    QFrame, QFileDialog, QMessageBox, QScrollArea, QStatusBar
)

from ui.web_pane import AIPane
from ui.task_table import TaskTable
from ui.scheduler_dialog import TaskSchedulerDialog
from ui.toast_notification import RateLimitToast
from core.dom_scraper import DOMScraper
from core.swarm_orchestrator import SwarmOrchestrator
from core.code_harvester import CodeHarvester


class MainWindow(QMainWindow):
    def __init__(self, project_data, session_manager, project_manager, injector, scheduler):
        super().__init__()
        self.project_data = project_data
        self.session_manager = session_manager
        self.project_manager = project_manager
        self.injector = injector
        self.scheduler = scheduler
        self.panes = {}
        self.attached_file_path = None

        self.dom_scraper = DOMScraper()
        self.orchestrator = SwarmOrchestrator(self.scheduler)
        self.harvester = CodeHarvester()

        self.setWindowTitle(f"Nexus AI Orchestrator — {self.project_data['name']} [Swarm Workstation]")
        self.resize(1440, 900)
        self._apply_classic_linux_theme()

        self._setup_menubar()
        self._setup_ui()
        self._initialize_panes()
        self._setup_statusbar()

        self.scheduler.queue_updated.connect(self.task_table.update_tasks)
        self.scheduler.task_due.connect(self._execute_scheduled_task)
        self.dom_scraper.scrape_complete.connect(self._on_scrape_complete)
        self.orchestrator.orchestration_complete.connect(self._on_orchestration_success)
        self.orchestrator.orchestration_error.connect(self._on_orchestration_error)

    def _apply_classic_linux_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #dcdad5; font-family: 'Ubuntu', sans-serif; }
            QMenuBar { background-color: #2e3436; color: #eeeeec; border-bottom: 1px solid #1c1f21; }
            QMenuBar::item:selected { background-color: #4a90d9; color: #ffffff; }
            QMenu { background-color: #f6f5f4; color: #2e3436; border: 1px solid #a7a59f; }
            QMenu::item:selected { background-color: #4a90d9; color: #ffffff; }
            QStatusBar { background-color: #d3d0c9; color: #2e3436; border-top: 1px solid #b5b2ac; font-size: 11px; }
            QScrollBar:horizontal { border: 1px solid #b5b2ac; background: #e6e5e2; height: 14px; margin: 0 14px; }
            QScrollBar::handle:horizontal { background: #9a9790; min-width: 30px; border-radius: 2px; }
            QScrollBar::handle:horizontal:hover { background: #77746d; }
        """)

    def _setup_menubar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        act_attach = QAction("Attach Document...", self)
        act_attach.triggered.connect(self._on_attach_file)
        file_menu.addAction(act_attach)
        file_menu.addAction("Exit Workstation", self.close)

        swarm_menu = menubar.addMenu("&Swarm")
        swarm_menu.addAction("Direct Send", self._on_direct_send)
        swarm_menu.addAction("1. Dispatch Master Directive", self._on_send_master)
        swarm_menu.addAction("2. Extract DOM && Delegate", self._on_extract)
        
        sched_menu = menubar.addMenu("&Scheduler")
        sched_menu.addAction("Schedule Task...", self._open_scheduler_dialog)
        sched_menu.addAction("Clear Completed", self.scheduler.clear_completed)
        
        view_menu = menubar.addMenu("&View")
        view_menu.addAction("Toggle Task Log", lambda: self.task_table.toggle_minimize())
        view_menu.addAction("Reload All Nodes", self._reload_all_panes)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.cmd_bar = QFrame()
        self.cmd_bar.setFixedHeight(58)
        self.cmd_bar.setStyleSheet("""
            QFrame { background-color: #e8e6e3; border-bottom: 1px solid #a7a59f; }
            QLabel { color: #2e3436; font-weight: bold; font-size: 12px; }
            QLineEdit, QComboBox { background-color: #ffffff; border: 1px solid #a7a59f; border-radius: 3px; padding: 5px 8px; }
            QPushButton { background-color: #f4f3f1; font-weight: bold; padding: 6px 12px; border: 1px solid #a7a59f; border-radius: 3px;}
            QPushButton:hover { background-color: #ffffff; }
            QPushButton#directBtn { background-color: #3584e4; color: #ffffff; border: 1px solid #1b6ACB; }
            QPushButton#masterBtn { background-color: #77216f; color: #ffffff; border: 1px solid #5e2750; }
            QPushButton#extractBtn { background-color: #5a8e3e; color: #ffffff; border: 1px solid #46712f; }
            QPushButton#harvestBtn { background-color: #c46200; color: #ffffff; border: 1px solid #8f4700; }
        """)

        cmd_layout = QHBoxLayout(self.cmd_bar)
        cmd_layout.addWidget(QLabel("Master / Target Node:"))
        self.master_combo = QComboBox()
        self.master_combo.setMinimumWidth(190)
        for acc in self.project_data['accounts']:
            self.master_combo.addItem(f"{acc['account_name']} (Claude)", acc['id'])

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Enter directive or prompt payload...")
        self.prompt_input.returnPressed.connect(self._on_direct_send)

        self.btn_attach = QPushButton("Attach File...")
        self.btn_attach.clicked.connect(self._on_attach_file)
        self.btn_schedule = QPushButton("Schedule...")
        self.btn_schedule.clicked.connect(self._open_scheduler_dialog)
        
        self.btn_direct = QPushButton("Direct Send")
        self.btn_direct.setObjectName("directBtn")
        self.btn_direct.clicked.connect(self._on_direct_send)
        
        self.btn_send_master = QPushButton("1. Send Master Directive")
        self.btn_send_master.setObjectName("masterBtn")
        self.btn_send_master.clicked.connect(self._on_send_master)
        
        self.btn_extract = QPushButton("2. Extract && Delegate")
        self.btn_extract.setObjectName("extractBtn")
        self.btn_extract.clicked.connect(self._on_extract)
        
        self.btn_harvest = QPushButton("3. Harvest && Build")
        self.btn_harvest.setObjectName("harvestBtn")
        self.btn_harvest.clicked.connect(self._on_harvest)

        cmd_layout.addWidget(self.master_combo)
        cmd_layout.addWidget(self.prompt_input, stretch=1)
        cmd_layout.addWidget(self.btn_attach)
        cmd_layout.addWidget(self.btn_schedule)
        cmd_layout.addWidget(self.btn_direct)
        cmd_layout.addWidget(self.btn_send_master)
        cmd_layout.addWidget(self.btn_extract)
        cmd_layout.addWidget(self.btn_harvest)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(5)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #b5b2ac; border-left: 1px solid #dcdad5; }")
        self.scroll_area.setWidget(self.splitter)

        self.task_table = TaskTable()
        self.task_table.clear_clicked.connect(self.scheduler.clear_completed)

        layout.addWidget(self.cmd_bar)
        layout.addWidget(self.scroll_area, stretch=1)
        layout.addWidget(self.task_table)

    def _setup_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(f"System Ready | Workspace: {self.project_data['name']} | Turnstile Poll: 2000ms")

    def _initialize_panes(self):
        for acc in self.project_data['accounts']:
            prof = self.session_manager.get_or_create_profile(acc['profile_id'])
            start_url = acc.get('current_url') or "https://claude.ai/new"
            pane = AIPane(acc['id'], acc['account_name'], "claude", prof, start_url)
            pane.setMinimumWidth(460)
            pane.url_changed.connect(lambda aid, url: self.project_manager.update_account_url(self.project_data['id'], aid, url))
            self.panes[acc['id']] = pane
            self.splitter.addWidget(pane)

    def _reload_all_panes(self):
        for pane in self.panes.values(): pane.reload_page()

    def _get_worker_accounts(self, master_id: str):
        return [acc for acc in self.project_data['accounts'] if acc['id'] != master_id]

    def _on_attach_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Attachment", "", "All Files (*.*)")
        if file_path:
            self.attached_file_path = file_path
            self.btn_attach.setStyleSheet("background-color: #5a8e3e; color: #ffffff;")
            self.btn_attach.setText(f"File: {os.path.basename(file_path)[:13]}...")

    def _reset_attach_button(self):
        self.attached_file_path = None
        self.btn_attach.setStyleSheet("")
        self.btn_attach.setText("Attach File...")

    def _open_scheduler_dialog(self):
        dlg = TaskSchedulerDialog(self.project_data['accounts'], self)
        dlg.task_scheduled.connect(self._on_dialog_task_scheduled)
        dlg.exec()

    def _on_dialog_task_scheduled(self, data: dict):
        if data["target_id"] == "all":
            for idx, acc in enumerate(self.project_data['accounts']):
                self.scheduler.add_task(acc['id'], "claude", data["prompt"], data["target_time"].addSecs(idx * 3), data.get("file_path"))
        else:
            self.scheduler.add_task(data["target_id"], "claude", data["prompt"], data["target_time"], data.get("file_path"))

    def _on_direct_send(self):
        prompt = self.prompt_input.text().strip()
        if not prompt and not self.attached_file_path: return
        self.scheduler.add_task(self.master_combo.currentData(), "claude", prompt, QTime.currentTime(), self.attached_file_path)
        self.prompt_input.clear()
        self._reset_attach_button()

    def _on_send_master(self):
        prompt = self.prompt_input.text().strip()
        if not prompt: return
        master_id = self.master_combo.currentData()
        workers = self._get_worker_accounts(master_id)
        if not workers:
            QMessageBox.warning(self, "Swarm Warning", "Swarm requires 1 Master and 1+ Workers.")
            return
        master_directive = self.orchestrator.build_master_directive(prompt, workers)
        self.scheduler.add_task(master_id, "claude", master_directive, QTime.currentTime(), self.attached_file_path)
        self.prompt_input.clear()
        self._reset_attach_button()

    def _on_extract(self):
        master_id = self.master_combo.currentData()
        master_pane = self.panes.get(master_id)
        if master_pane:
            self.status_bar.showMessage(f"Extracting latest DOM response from Master ({master_id})...")
            self.dom_scraper.extract_latest_response(master_pane.get_page(), master_id, "master_extraction")

    def _on_harvest(self):
        self.status_bar.showMessage("Harvesting code from all active nodes...")
        for aid, pane in self.panes.items():
            page = pane.get_page()
            if page:
                page.runJavaScript(
                    "document.body.innerText;", 
                    lambda text, p_id=aid: self._process_harvest(text, p_id)
                )

    def _process_harvest(self, text, account_id):
        if text:
            files = self.harvester.parse_and_write_files(text, self.project_data['name'])
            if files:
                reply = QMessageBox.question(
                    self, "Harvest Complete", 
                    f"Materialized {len(files)} files from node {account_id}!\nOpen project directory in VS Code?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.harvester.open_in_vscode(self.project_data['name'])

    def _on_scrape_complete(self, account_id, task_id, result):
        if not result.get("success"):
            QMessageBox.warning(self, "DOM Error", f"Failed to read node:\n{result.get('error')}")
            return
        self.orchestrator.process_master_response(result.get("text", ""), self._get_worker_accounts(self.master_combo.currentData()))

    def _on_orchestration_success(self, task_count):
        self.status_bar.showMessage(f"Delegation Complete: {task_count} tasks queued.")

    def _on_orchestration_error(self, error_msg):
        QMessageBox.warning(self, "Delegation Failed", error_msg)

    def _execute_scheduled_task(self, task):
        pane = self.panes.get(task['account_id'])
        if not pane:
            self.scheduler.update_task_status(task['id'], "failed")
            return
        pane.set_status("running")
        self.scroll_area.ensureWidgetVisible(pane)
        self.injector.send_prompt(
            page=pane.get_page(), platform=pane.provider.lower(),
            prompt_text=task['prompt_text'], file_path=task.get('file_path'),
            main_hwnd=int(self.winId()), view=pane.web_view,
            callback=lambda res: self._on_injection_result(task['id'], task['account_id'], res)
        )

    def _on_injection_result(self, task_id, account_id, result):
        if result.get("success"):
            self.scheduler.update_task_status(task_id, "success")
            if account_id in self.panes: self.panes[account_id].set_status("ready")
        else:
            self.scheduler.update_task_status(task_id, "failed")
            if account_id in self.panes: self.panes[account_id].set_status("rate_limited")

    def closeEvent(self, event):
        for pane in self.panes.values(): pane.cleanup()
        super().closeEvent(event)