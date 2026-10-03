from PyQt6.QtCore import Qt, QTime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLineEdit, QComboBox, QSplitter, QLabel, QFrame, QFileDialog, QMessageBox
)

from ui.web_pane import AIPane
from ui.task_table import TaskTable
from ui.scheduler_dialog import TaskSchedulerDialog
from ui.toast_notification import RateLimitToast
from core.dom_scraper import DOMScraper
from core.swarm_orchestrator import SwarmOrchestrator

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

        self.setWindowTitle(f"Nexus AI Orchestrator - {self.project_data['name']} (Swarm Mode)")
        self.resize(1400, 900)
        self.setStyleSheet("QMainWindow { background-color: #09090b; }")

        self._setup_ui()
        self._initialize_panes()

        self.scheduler.queue_updated.connect(self.task_table.update_tasks)
        self.scheduler.task_due.connect(self._execute_scheduled_task)
        
        self.dom_scraper.scrape_complete.connect(self._on_scrape_complete)
        self.orchestrator.orchestration_complete.connect(self._on_orchestration_success)
        self.orchestrator.orchestration_error.connect(self._on_orchestration_error)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.cmd_bar = QFrame()
        self.cmd_bar.setFixedHeight(75)
        self.cmd_bar.setStyleSheet("""
            QFrame { background-color: #18181b; border-bottom: 1px solid #27272a; }
            QLabel { color: #ffffff; font-weight: bold; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QLineEdit, QComboBox { background-color: #27272a; color: #ffffff; border: 1px solid #3f3f46; border-radius: 4px; padding: 6px 10px; font-size: 13px;}
            QPushButton { background-color: #27272a; color: #ffffff; font-weight: bold; padding: 8px 12px; border-radius: 4px; border: 1px solid #3f3f46;}
            QPushButton:hover { background-color: #3f3f46; }
            QPushButton#masterBtn { background-color: #7c3aed; border: none; }
            QPushButton#masterBtn:hover { background-color: #6d28d9; }
            QPushButton#extractBtn { background-color: #059669; border: none; }
            QPushButton#extractBtn:hover { background-color: #047857; }
        """)

        cmd_layout = QHBoxLayout(self.cmd_bar)
        cmd_layout.setContentsMargins(20, 10, 20, 10)

        cmd_layout.addWidget(QLabel("Master AI:"))
        self.master_combo = QComboBox()
        for acc in self.project_data['accounts']:
            self.master_combo.addItem(f"{acc['account_name']} (Claude)", acc['id'])

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Enter task idea here to generate the Master Plan...")

        self.btn_attach = QPushButton("📎 Attach File")
        self.btn_attach.clicked.connect(self._on_attach_file)

        self.btn_send_master = QPushButton("1. Send Master Directive")
        self.btn_send_master.setObjectName("masterBtn")
        self.btn_send_master.clicked.connect(self._on_send_master)

        self.btn_extract = QPushButton("2. Extract & Delegate")
        self.btn_extract.setObjectName("extractBtn")
        self.btn_extract.clicked.connect(self._on_extract)

        cmd_layout.addWidget(self.master_combo)
        cmd_layout.addSpacing(10)
        cmd_layout.addWidget(self.prompt_input, stretch=1)
        cmd_layout.addWidget(self.btn_attach)
        cmd_layout.addWidget(self.btn_send_master)
        cmd_layout.addWidget(self.btn_extract)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #27272a; width: 3px; }")
        self.task_table = TaskTable()

        layout.addWidget(self.cmd_bar)
        layout.addWidget(self.splitter, stretch=1)
        layout.addWidget(self.task_table)

    def _initialize_panes(self):
        for acc in self.project_data['accounts']:
            prof = self.session_manager.get_or_create_profile(acc['profile_id'])
            start_url = acc.get('current_url') or "https://claude.ai/new"
            pane = AIPane(acc['id'], acc['account_name'], "claude", prof, start_url)
            pane.url_changed.connect(lambda aid, url: self.project_manager.update_account_url(self.project_data['id'], aid, url))
            self.panes[acc['id']] = pane
            self.splitter.addWidget(pane)

    def _get_worker_accounts(self, master_id: str):
        return [acc for acc in self.project_data['accounts'] if acc['id'] != master_id]

    def _on_attach_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Document", "", "All Files (*.*)")
        if file_path:
            self.attached_file_path = file_path
            self.btn_attach.setStyleSheet("background-color: #22c55e; color: white; border: none;")
            self.btn_attach.setText("📎 File Ready")

    def _on_send_master(self):
        prompt = self.prompt_input.text().strip()
        if not prompt: return

        master_id = self.master_combo.currentData()
        workers = self._get_worker_accounts(master_id)

        if not workers:
            QMessageBox.warning(self, "Swarm Error", "You need at least 2 accounts to use Swarm Mode (1 Master, 1 Worker).")
            return

        master_directive = self.orchestrator.build_master_directive(prompt, workers)

        self.scheduler.add_task(
            account_id=master_id, 
            platform="claude", 
            prompt_text=master_directive,
            target_time=QTime.currentTime(), 
            file_path=self.attached_file_path
        )

        self.prompt_input.clear()
        self.attached_file_path = None
        self.btn_attach.setStyleSheet("")
        self.btn_attach.setText("📎 Attach File")

    def _on_extract(self):
        master_id = self.master_combo.currentData()
        master_pane = self.panes.get(master_id)

        if master_pane:
            self.dom_scraper.extract_latest_response(
                page=master_pane.get_page(),
                account_id=master_id,
                task_id="master_extraction"
            )

    def _on_scrape_complete(self, account_id, task_id, result):
        if not result.get("success"):
            QMessageBox.warning(self, "Extraction Failed", f"Could not read Claude's response: {result.get('error')}")
            return

        raw_text = result.get("text", "")
        master_id = self.master_combo.currentData()
        workers = self._get_worker_accounts(master_id)
        self.orchestrator.process_master_response(raw_text, workers)

    def _on_orchestration_success(self, task_count):
        QMessageBox.information(self, "Delegation Success", f"Successfully extracted and queued {task_count} subordinate tasks!")

    def _on_orchestration_error(self, error_msg):
        QMessageBox.warning(self, "Delegation Failed", error_msg)

    def _execute_scheduled_task(self, task):
        pane = self.panes.get(task['account_id'])
        if not pane: return
        pane.set_status("running")

        # Correctly pass the arguments matching your existing injector.py callback logic
        self.injector.send_prompt(
            page=pane.get_page(), 
            platform=pane.provider.lower(), 
            prompt_text=task['prompt_text'], 
            file_path=task.get('file_path'),
            callback=lambda res: self._on_injection_result(task['id'], task['account_id'], res)
        )

    def _on_injection_result(self, task_id, account_id, result):
        if result.get("success"):
            self.scheduler.update_task_status(task_id, "success")
            if account_id in self.panes: self.panes[account_id].set_status("ready")
        else:
            self.scheduler.update_task_status(task_id, "failed")
            if account_id in self.panes:
                self.panes[account_id].set_status("rate_limited")
                toast = RateLimitToast(account_id, self.panes[account_id].account_name, self.panes[account_id].provider, "Unknown", self)
                toast.move(self.width() - toast.width() - 30, self.height() - toast.height() - 50)
                toast.show()
