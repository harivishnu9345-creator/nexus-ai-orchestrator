"""
Main Window UI Module
Assembles Top Command Bar, Splitter Panes, Task Table, File Uploader, and Scheduler.
"""

from PyQt6.QtCore import Qt, QTime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLineEdit, QComboBox, QSplitter, QLabel, QFrame, QFileDialog
)

from ui.web_pane import AIPane
from ui.task_table import TaskTable
from ui.toast_notification import RateLimitToast
from ui.scheduler_dialog import TaskSchedulerDialog

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
        
        self.setWindowTitle(f"Nexus AI Orchestrator - {self.project_data['name']}")
        self.resize(1400, 900)
        self.setStyleSheet("QMainWindow { background-color: #09090b; }")

        self._setup_ui()
        self._initialize_panes()
        
        self.scheduler.queue_updated.connect(self.task_table.update_tasks)
        self.scheduler.task_due.connect(self._execute_scheduled_task)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.cmd_bar = QFrame()
        self.cmd_bar.setFixedHeight(65)
        self.cmd_bar.setStyleSheet("""
            QFrame { background-color: #18181b; border-bottom: 1px solid #27272a; }
            QLabel { color: #ffffff; font-weight: bold; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
            QLineEdit, QComboBox { background-color: #27272a; color: #ffffff; border: 1px solid #3f3f46; border-radius: 4px; padding: 8px 12px; font-size: 13px;}
            QLineEdit:focus, QComboBox:focus { border-color: #7c3aed; }
            QPushButton { background-color: #27272a; color: #ffffff; font-weight: bold; padding: 8px 16px; border-radius: 4px; border: 1px solid #3f3f46;}
            QPushButton:hover { background-color: #3f3f46; }
            QPushButton#primaryBtn { background-color: #7c3aed; border: none; }
            QPushButton#primaryBtn:hover { background-color: #6d28d9; }
            QPushButton#attachBtn { background-color: #27272a; border: 1px dashed #71717a; }
            QPushButton#attachBtn:hover { background-color: #3f3f46; border-color: #a1a1aa; }
        """)
        
        cmd_layout = QHBoxLayout(self.cmd_bar)
        cmd_layout.setContentsMargins(20, 10, 20, 10)
        
        self.target_combo = QComboBox()
        self.target_combo.addItem("Broadcast: All Accounts", "all")
        for acc in self.project_data['accounts']:
            self.target_combo.addItem(f"{acc['account_name']} ({acc['platform'].capitalize()})", acc['id'])
            
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Type a prompt here to broadcast to multiple AIs at once...")
        self.prompt_input.returnPressed.connect(self._on_broadcast)
        
        self.btn_attach = QPushButton("📎 Attach File")
        self.btn_attach.setObjectName("attachBtn")
        self.btn_attach.clicked.connect(self._on_attach_file)

        btn_run = QPushButton("Run Broadcast")
        btn_run.setObjectName("primaryBtn")
        btn_run.clicked.connect(self._on_broadcast)

        btn_schedule = QPushButton("⏰ Schedule Task")
        btn_schedule.clicked.connect(self._open_schedule_dialog)
        
        cmd_layout.addWidget(QLabel(self.project_data['name']))
        cmd_layout.addSpacing(30)
        cmd_layout.addWidget(self.target_combo)
        cmd_layout.addWidget(self.prompt_input, stretch=1)
        cmd_layout.addWidget(self.btn_attach)
        cmd_layout.addWidget(btn_run)
        cmd_layout.addWidget(btn_schedule)

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
            pane = AIPane(acc['id'], acc['account_name'], acc['platform'], prof, start_url)
            pane.url_changed.connect(lambda aid, url: self.project_manager.update_account_url(self.project_data['id'], aid, url))
            self.panes[acc['id']] = pane
            self.splitter.addWidget(pane)

    def _on_attach_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Document to Upload", "", "All Files (*.*)")
        if file_path:
            self.attached_file_path = file_path
            self.btn_attach.setStyleSheet("background-color: #22c55e; color: white; border: none;")
            self.btn_attach.setText("📎 File Ready")

    def _on_broadcast(self):
        prompt = self.prompt_input.text().strip()
        if not prompt: return
        target_id = self.target_combo.currentData()
        self.prompt_input.clear()
        
        targets = [target_id] if target_id != "all" else list(self.panes.keys())
        for t in targets:
            pane = self.panes.get(t)
            if pane:
                self.scheduler.add_task(
                    account_id=t, platform=pane.provider, prompt_text=prompt,
                    target_time=QTime.currentTime(), file_path=self.attached_file_path
                )
        self.attached_file_path = None
        self.btn_attach.setStyleSheet("")
        self.btn_attach.setText("📎 Attach File")

    def _open_schedule_dialog(self):
        dialog = TaskSchedulerDialog(self.project_data['accounts'], self)
        dialog.task_scheduled.connect(self._on_task_scheduled)
        dialog.exec()

    def _on_task_scheduled(self, data):
        target_id = data["target_id"]
        targets = [target_id] if target_id != "all" else list(self.panes.keys())
        for t in targets:
            pane = self.panes.get(t)
            if pane:
                # Passing the file_path from the schedule modal
                self.scheduler.add_task(
                    account_id=t, platform=pane.provider, prompt_text=data["prompt"],
                    target_time=data["target_time"], file_path=data.get("file_path")
                )

    def _execute_scheduled_task(self, task):
        pane = self.panes.get(task['account_id'])
        if not pane: return
        pane.set_status("running")
        self.injector.send_prompt(
            page=pane.get_page(), platform=pane.provider.lower(), 
            prompt_text=task['prompt_text'], file_path=task.get('file_path'),
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
