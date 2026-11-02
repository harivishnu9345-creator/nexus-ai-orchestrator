import os
from datetime import datetime
from PyQt6.QtCore import Qt, QTime, QDateTime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QScrollArea,
    QSplitter, QTabWidget, QFileDialog, QMessageBox, QFrame
)

from core.session_manager import SessionManager
from core.project_manager import ProjectManager
from core.scheduler import TaskScheduler
from core.dom_scraper import DOMScraper
from core.dom_watcher import DOMWatcher
from core.swarm_orchestrator import SwarmOrchestrator
from core.code_harvester import CodeHarvester

from ui.web_pane import AIPane
from ui.task_table import TaskTable
from ui.swarm_mind_map import SwarmMindMapWidget
from ui.swarm_train_chart import SwarmTrainChartWidget
from ui.scheduler_dialog import TaskSchedulerDialog
from ui.toast_notification import RateLimitToast
from ui.project_hub import ProjectHubDialog
from ui.onboarding_dialog import OnboardingDialog


class MainWindow(QMainWindow):
    def __init__(self, config: dict, workspace_data: dict = None):
        super().__init__()
        self.config = config
        self.workspace_data = workspace_data or {}
        self.project_name = self.workspace_data.get("name", "Untitled_Workspace")

        app_cfg = config.get("app", {})
        self.setWindowTitle(f"{app_cfg.get('name', 'Nexus AI Orchestrator')} â€” {self.project_name} [Swarm Workstation]")
        self.resize(1600, 960)

        self.session_mgr = SessionManager(app_cfg.get("storage_root", "~/.nexus_orchestrator"))
        self.project_mgr = ProjectManager()
        self.scheduler = TaskScheduler(config, self)
        self.dom_watcher = DOMWatcher(self)
        self.orchestrator = SwarmOrchestrator()
        self.harvester = CodeHarvester()

        if self.workspace_data and "id" not in self.workspace_data:
            self.project_mgr.save_project(self.workspace_data)

        self.panes = {}
        self.accounts = []
        self.attached_file_path = None
        self.active_master_id = None

        self.pipeline_worker_order = []
        self.worker_tasks_prompts = {}
        self.assigned_files_display = {}
        self.harvested_stage_files = {}
        self.harvested_stage_summaries = {}
        self.current_node_statuses = {}
        self.current_stage_statuses = {}
        self.current_gate_states = []

        self.pipeline_sessions = []
        self.viewing_session_idx = -1

        self._apply_carbon_black_theme()
        self._setup_menu_bar()
        self._setup_ui()
        self._connect_signals()
        self._load_initial_workspace()

    def _apply_carbon_black_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget#CentralWorkspace {
                background-color: #09090b;
                color: #f4f4f5;
                font-family: 'Ubuntu', 'Segoe UI', sans-serif;
            }
            QMenuBar {
                background-color: #141417;
                color: #e4e4e7;
                border-bottom: 1px solid #27272a;
                font-size: 12px;
                font-weight: bold;
                padding: 2px 6px;
            }
            QMenuBar::item {
                padding: 4px 10px;
                background: transparent;
            }
            QMenuBar::item:selected {
                background-color: #27272a;
            }
            QMenu {
                background-color: #141417;
                color: #f4f4f5;
                border: 1px solid #27272a;
            }
            QMenu::item {
                padding: 6px 20px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
            }
            QFrame#CommandBar, QFrame#SwarmBar {
                background-color: #141417;
                border-bottom: 1px solid #27272a;
            }
            QLabel {
                color: #e4e4e7;
                font-size: 12px;
                font-weight: bold;
            }
            QLineEdit, QComboBox {
                background-color: #09090b;
                color: #f4f4f5;
                border: 1px solid #27272a;
                border-radius: 3px;
                padding: 5px 8px;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #3b82f6;
            }
            QComboBox QAbstractItemView {
                background-color: #141417;
                color: #f4f4f5;
                selection-background-color: #2563eb;
                border: 1px solid #27272a;
            }
            QPushButton {
                background-color: #1f1f23;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 3px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27272a;
                color: #ffffff;
            }
            QPushButton#PrimaryBtn {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #3b82f6;
            }
            QPushButton#PrimaryBtn:hover {
                background-color: #1d4ed8;
            }
            QPushButton#SwarmBtn {
                background-color: #6d28d9;
                color: #ffffff;
                border: 1px solid #8b5cf6;
            }
            QPushButton#SwarmBtn:hover {
                background-color: #5b21b6;
            }
            QPushButton#HarvestBtn {
                background-color: #059669;
                color: #ffffff;
                border: 1px solid #10b981;
            }
            QPushButton#HarvestBtn:hover {
                background-color: #047857;
            }
            QTabWidget::pane {
                border-top: 1px solid #27272a;
                background-color: #09090b;
            }
            QTabBar::tab {
                background-color: #141417;
                color: #a1a1aa;
                border: 1px solid #27272a;
                border-bottom: none;
                padding: 6px 16px;
                font-size: 11px;
                font-weight: bold;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #09090b;
                color: #f4f4f5;
                border-top: 2px solid #71717a;
            }
            QSplitter::handle {
                background-color: #27272a;
                height: 3px;
            }
        """)

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("Switch Workspace (Project Hub)...", self._open_project_hub)
        file_menu.addAction("New Swarm Workspace...", self._open_onboarding_dialog)
        file_menu.addSeparator()
        file_menu.addAction(
            "Open Build Folder in VS Code",
            lambda: self.harvester.open_in_vscode(self.input_project_name.text().strip() or self.project_name)
        )
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        swarm_menu = menu_bar.addMenu("Swarm")
        swarm_menu.addAction("1. Send Master Directive", self._on_send_master_directive)
        swarm_menu.addAction("2. Extract & Delegate Pipeline", self._on_extract_and_delegate)
        swarm_menu.addAction("3. Harvest & Build ZIP", self._on_harvest_all_nodes)

        sched_menu = menu_bar.addMenu("Scheduler")
        sched_menu.addAction("Schedule Prompt Task...", self._open_scheduler_dialog)
        sched_menu.addAction("Clear Completed Tasks", self.scheduler.clear_completed)

        view_menu = menu_bar.addMenu("View")
        view_menu.addAction("Reload All Nodes", self._reload_all_nodes)
        view_menu.addAction("System Task Queue", lambda: self.bottom_tabs.setCurrentIndex(0))
        view_menu.addAction("Task Assignment Mind-Map", lambda: self.bottom_tabs.setCurrentIndex(1))
        view_menu.addAction("Execution Flow & File Relay", lambda: self.bottom_tabs.setCurrentIndex(2))

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("CentralWorkspace")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ROW 1: Command Bar
        self.cmd_bar = QFrame()
        self.cmd_bar.setObjectName("CommandBar")
        self.cmd_bar.setFixedHeight(46)
        cmd_layout = QHBoxLayout(self.cmd_bar)
        cmd_layout.setContentsMargins(10, 6, 10, 6)
        cmd_layout.setSpacing(8)

        cmd_layout.addWidget(QLabel("Target:"))
        self.combo_target = QComboBox()
        self.combo_target.setFixedWidth(185)
        cmd_layout.addWidget(self.combo_target)

        self.input_prompt = QLineEdit()
        self.input_prompt.setPlaceholderText("Enter direct prompt or broadcast command...")
        self.input_prompt.returnPressed.connect(self._on_send_immediate)
        cmd_layout.addWidget(self.input_prompt, stretch=1)

        self.btn_attach = QPushButton("Attach")
        self.btn_attach.clicked.connect(self._on_attach_file)
        cmd_layout.addWidget(self.btn_attach)

        self.btn_send = QPushButton("Send Now")
        self.btn_send.setObjectName("PrimaryBtn")
        self.btn_send.clicked.connect(self._on_send_immediate)
        cmd_layout.addWidget(self.btn_send)

        self.btn_schedule = QPushButton("Schedule...")
        self.btn_schedule.clicked.connect(self._open_scheduler_dialog)
        cmd_layout.addWidget(self.btn_schedule)

        main_layout.addWidget(self.cmd_bar)

        # ROW 2: Swarm Pipeline Bar
        self.swarm_bar = QFrame()
        self.swarm_bar.setObjectName("SwarmBar")
        self.swarm_bar.setFixedHeight(44)
        swarm_layout = QHBoxLayout(self.swarm_bar)
        swarm_layout.setContentsMargins(10, 5, 10, 5)
        swarm_layout.setSpacing(8)

        swarm_layout.addWidget(QLabel("Project:"))
        self.input_project_name = QLineEdit(self.project_name)
        self.input_project_name.setFixedWidth(150)
        swarm_layout.addWidget(self.input_project_name)

        self.btn_switch_ws = QPushButton("Switch")
        self.btn_switch_ws.clicked.connect(self._open_project_hub)
        swarm_layout.addWidget(self.btn_switch_ws)

        swarm_layout.addWidget(QLabel("Master Architect:"))
        self.combo_master = QComboBox()
        self.combo_master.setFixedWidth(175)
        self.combo_master.currentIndexChanged.connect(self._on_master_architect_changed)
        swarm_layout.addWidget(self.combo_master)

        self.btn_master_directive = QPushButton("1. Send Master Directive")
        self.btn_master_directive.setObjectName("SwarmBtn")
        self.btn_master_directive.clicked.connect(self._on_send_master_directive)
        swarm_layout.addWidget(self.btn_master_directive)

        self.btn_extract_delegate = QPushButton("2. Extract && Delegate Pipeline")
        self.btn_extract_delegate.setObjectName("SwarmBtn")
        self.btn_extract_delegate.clicked.connect(self._on_extract_and_delegate)
        swarm_layout.addWidget(self.btn_extract_delegate)

        self.btn_harvest_all = QPushButton("3. Harvest && Build ZIP")
        self.btn_harvest_all.setObjectName("HarvestBtn")
        self.btn_harvest_all.clicked.connect(self._on_harvest_all_nodes)
        swarm_layout.addWidget(self.btn_harvest_all)

        self.btn_open_vscode = QPushButton("Open Build in VS Code")
        self.btn_open_vscode.clicked.connect(
            lambda: self.harvester.open_in_vscode(self.input_project_name.text().strip() or self.project_name)
        )
        swarm_layout.addWidget(self.btn_open_vscode)
        swarm_layout.addStretch()

        main_layout.addWidget(self.swarm_bar)

        self.splitter = QSplitter(Qt.Orientation.Vertical)

        self.h_scroll = QScrollArea()
        self.h_scroll.setWidgetResizable(True)
        self.h_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.h_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.h_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #09090b;
            }
            QScrollBar:horizontal {
                background: #141417;
                height: 14px;
                border-top: 1px solid #27272a;
                border-bottom: 1px solid #27272a;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #52525b;
                min-width: 80px;
                border-radius: 4px;
                margin: 2px 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #71717a;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

        self.strip_container = QWidget()
        self.strip_container.setStyleSheet("background-color: #09090b;")
        self.strip_layout = QHBoxLayout(self.strip_container)
        self.strip_layout.setContentsMargins(6, 6, 6, 6)
        self.strip_layout.setSpacing(8)
        self.strip_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.h_scroll.setWidget(self.strip_container)
        self.splitter.addWidget(self.h_scroll)

        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setMinimumHeight(230)

        self.task_table = TaskTable(self)
        self.bottom_tabs.addTab(self.task_table, "System Task Queue && Execution Log")

        self.mind_map_tab = SwarmMindMapWidget(self)
        self.bottom_tabs.addTab(self.mind_map_tab, "Task Assignment Mind-Map")

        self.train_chart_tab = SwarmTrainChartWidget(self)
        self.bottom_tabs.addTab(self.train_chart_tab, "Execution Flow && File Relay")

        self.splitter.addWidget(self.bottom_tabs)
        self.splitter.setSizes([610, 260])
        main_layout.addWidget(self.splitter, stretch=1)

        self.status_bar_frame = QFrame()
        self.status_bar_frame.setFixedHeight(24)
        self.status_bar_frame.setStyleSheet("background-color: #141417; border-top: 1px solid #27272a;")
        sbl = QHBoxLayout(self.status_bar_frame)
        sbl.setContentsMargins(10, 2, 10, 2)
        self.lbl_status_bar = QLabel("")
        self.lbl_status_bar.setStyleSheet("color: #a1a1aa; font-size: 11px; border: none; font-weight: normal;")
        sbl.addWidget(self.lbl_status_bar)
        main_layout.addWidget(self.status_bar_frame)

        self.toast_container = QWidget(self)
        self.toast_layout = QVBoxLayout(self.toast_container)
        self.toast_layout.setContentsMargins(0, 0, 0, 0)
        self.toast_container.setFixedWidth(370)
        self.toast_container.hide()

    def _connect_signals(self):
        self.scheduler.queue_updated.connect(self._on_queue_updated)
        self.scheduler.task_status_changed.connect(self._on_node_status_changed)
        self.scheduler.rate_limit_detected.connect(self._show_rate_limit_toast)
        self.scheduler.sub_injector_telemetry.connect(
            lambda msg: self.train_chart_tab.set_progress(self.train_chart_tab.progress_bar.value(), msg)
        )
        self.scheduler.stage_dispatched.connect(self._on_stage_prompt_dispatched)
        self.task_table.clear_clicked.connect(self.scheduler.clear_completed)
        self.dom_watcher.generation_complete.connect(self._on_worker_generation_complete)
        self.train_chart_tab.relay_gate_approved.connect(self._on_relay_gate_approved)
        self.train_chart_tab.execution_mode_changed.connect(self._on_execution_mode_switched)
        self.train_chart_tab.force_stage_complete.connect(self._on_worker_generation_complete)

        self.mind_map_tab.session_selected.connect(self._on_session_history_selected)
        self.train_chart_tab.session_selected.connect(self._on_session_history_selected)

    def _on_queue_updated(self, tasks: list):
        self.task_table.update_tasks(tasks)
        if self.workspace_data and self.workspace_data.get("id"):
            self.project_mgr.save_task_history(self.workspace_data["id"], self.scheduler.serialize_tasks())

    def _save_or_update_current_session(self, create_new: bool = False, label_suffix: str = ""):
        if not self.accounts:
            return
        master_id = self.combo_master.currentData() or self.accounts[0]["id"]
        master_acc = next((a for a in self.accounts if a["id"] == master_id), self.accounts[0])
        workers = self.pipeline_worker_order or [a for a in self.accounts if a["id"] != master_id]

        if create_new or not self.pipeline_sessions:
            ts = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            session_num = len(self.pipeline_sessions) + 1
            title = f"Session #{session_num} â€” {ts} (Master: {master_acc['account_name']})"
            if label_suffix:
                title += f" [{label_suffix}]"
            snapshot = {
                "title": title,
                "master_account": master_acc,
                "worker_accounts": workers,
                "assigned_files": dict(self.assigned_files_display),
                "node_statuses": dict(self.current_node_statuses),
                "stage_statuses": dict(self.current_stage_statuses),
                "gate_states": list(self.current_gate_states)
            }
            self.pipeline_sessions.append(snapshot)
            self.viewing_session_idx = len(self.pipeline_sessions) - 1
        else:
            latest = self.pipeline_sessions[-1]
            latest["master_account"] = master_acc
            latest["worker_accounts"] = workers
            latest["assigned_files"] = dict(self.assigned_files_display)
            latest["node_statuses"] = dict(self.current_node_statuses)
            latest["stage_statuses"] = dict(self.current_stage_statuses)
            latest["gate_states"] = list(self.current_gate_states)
            self.viewing_session_idx = len(self.pipeline_sessions) - 1

        labels = [s["title"] for s in self.pipeline_sessions]
        self.mind_map_tab.set_session_list(labels, self.viewing_session_idx)
        self.train_chart_tab.set_session_list(labels, self.viewing_session_idx)

        if self.workspace_data and self.workspace_data.get("id"):
            self.project_mgr.save_pipeline_sessions(self.workspace_data["id"], self.pipeline_sessions)

    def _on_session_history_selected(self, idx: int):
        """Renders any historical or current session snapshot in the Mind-Map and Train Chart."""
        if not (0 <= idx < len(self.pipeline_sessions)):
            return
        self.viewing_session_idx = idx
        snap = self.pipeline_sessions[idx]

        labels = [s["title"] for s in self.pipeline_sessions]
        self.mind_map_tab.set_session_list(labels, idx)
        self.train_chart_tab.set_session_list(labels, idx)

        master_acc = snap.get("master_account") or (self.accounts[0] if self.accounts else {})
        workers = snap.get("worker_accounts") or []
        assigned_files = snap.get("assigned_files") or {}
        node_statuses = snap.get("node_statuses") or {}
        stage_statuses = snap.get("stage_statuses") or {}
        gate_states = snap.get("gate_states") or []

        self.mind_map_tab.build_mind_map(master_acc, workers, assigned_files, node_statuses)
        self.train_chart_tab.build_train_pipeline(workers, assigned_files, stage_statuses, gate_states)

        is_latest = (idx == len(self.pipeline_sessions) - 1)
        if not is_latest:
            self.train_chart_tab.set_progress(100, f"Viewing Historical Snapshot: {snap.get('title', '')}")

    def _clear_current_panes(self):
        for pane in self.panes.values():
            pane.cleanup()
            pane.deleteLater()
        self.panes.clear()
        while self.strip_layout.count():
            item = self.strip_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_pane_url_changed(self, account_id: str, new_url: str):
        if not new_url or "login" in new_url.lower() or "accounts.google.com" in new_url.lower():
            return

        self.session_mgr.update_last_url(account_id, new_url)

        for acc in self.accounts:
            if acc.get("id") == account_id:
                acc["current_url"] = new_url
                acc["last_url"] = new_url
                break

        if self.workspace_data:
            proj_id = self.workspace_data.get("id")
            if proj_id:
                self.project_mgr.update_account_url(proj_id, account_id, new_url)
            else:
                self.workspace_data["accounts"] = self.accounts
                self.project_mgr.save_project(self.workspace_data)

    def _on_master_architect_changed(self, _index: int = 0):
        if not self.accounts:
            return
        master_id = self.combo_master.currentData()
        if not master_id:
            return

        self.active_master_id = master_id
        master_acc = next((a for a in self.accounts if a["id"] == master_id), self.accounts[0])
        workers = [a for a in self.accounts if a["id"] != master_id] or [master_acc]

        self.pipeline_worker_order = list(workers)
        self.assigned_files_display = {}
        self.current_node_statuses = {master_id: "idle"}
        self.current_stage_statuses = {w["id"]: "waiting" for w in workers}
        self.current_gate_states = [{"state": "locked", "files": []} for _ in range(max(0, len(workers) - 1))]

        self.mind_map_tab.build_mind_map(master_acc, workers)
        self.train_chart_tab.build_train_pipeline(workers)
        self._save_or_update_current_session(create_new=False)

    def _load_initial_workspace(self):
        self._clear_current_panes()

        if self.workspace_data and self.workspace_data.get("accounts"):
            proj_id = self.workspace_data.get("id")
            if proj_id:
                fresh = self.project_mgr.load_project(proj_id)
                if fresh:
                    self.workspace_data = fresh
            self.accounts = self.workspace_data["accounts"]
            self.project_name = self.workspace_data.get("name", "Untitled_Workspace")
        else:
            self.accounts = self.session_mgr.load_accounts()

        self.input_project_name.setText(self.project_name)
        self.setWindowTitle(f"Nexus AI Orchestrator â€” {self.project_name} [Swarm Workstation]")

        self.combo_target.blockSignals(True)
        self.combo_master.blockSignals(True)
        self.combo_target.clear()
        self.combo_master.clear()
        self.combo_target.addItem("Broadcast to All Active Nodes", "all")

        default_zoom = self.config.get("app", {}).get("default_zoom", 0.75)

        for acc in self.accounts:
            acc_id = acc["id"]
            platform = acc.get("platform", "claude").lower()
            plat_cfg = self.config.get("platforms", {}).get(platform, {})
            start_url = acc.get("current_url") or acc.get("last_url") or plat_cfg.get("home_url", "https://claude.ai/new")

            profile_key = acc.get("profile_id") or acc_id
            profile = self.session_mgr.get_or_create_profile(profile_key, self)
            pane = AIPane(acc_id, acc["account_name"], platform, profile, start_url, default_zoom, self)
            pane.url_changed.connect(self._on_pane_url_changed)

            self.strip_layout.addWidget(pane)
            self.panes[acc_id] = pane
            self.scheduler.register_pane(acc_id, pane, acc)

            label = f"{acc['account_name']} ({platform.capitalize()})"
            self.combo_target.addItem(label, acc_id)
            self.combo_master.addItem(label, acc_id)

        self.combo_target.blockSignals(False)
        self.combo_master.blockSignals(False)

        # 1. Restore Persistent Task Queue History from Project JSON
        saved_tasks = self.workspace_data.get("task_history", []) if self.workspace_data else []
        self.scheduler.load_serialized_tasks(saved_tasks)

        # 2. Restore Persistent Pipeline Session Graphs (Mind-Map & Train Chart)
        saved_sessions = self.workspace_data.get("pipeline_sessions", []) if self.workspace_data else []
        if saved_sessions:
            self.pipeline_sessions = list(saved_sessions)
            latest_idx = len(self.pipeline_sessions) - 1
            latest = self.pipeline_sessions[latest_idx]

            master_acc = latest.get("master_account") or (self.accounts[0] if self.accounts else {})
            m_idx = self.combo_master.findData(master_acc.get("id"))
            if m_idx >= 0:
                self.combo_master.blockSignals(True)
                self.combo_master.setCurrentIndex(m_idx)
                self.combo_master.blockSignals(False)

            self.pipeline_worker_order = latest.get("worker_accounts") or [
                a for a in self.accounts if a["id"] != master_acc.get("id")
            ]
            self.assigned_files_display = dict(latest.get("assigned_files") or {})
            self.current_node_statuses = dict(latest.get("node_statuses") or {})
            self.current_stage_statuses = dict(latest.get("stage_statuses") or {})
            self.current_gate_states = list(latest.get("gate_states") or [])

            self._on_session_history_selected(latest_idx)
        else:
            self.pipeline_sessions = []
            self._on_master_architect_changed()

        self.lbl_status_bar.setText(
            f"System Ready | Workspace: {self.project_name} | Active Nodes: {len(self.accounts)} (Horizontal Scroll Enabled) | Turnstile Poll: 2000ms"
        )

    def _open_project_hub(self):
        projects = self.project_mgr.load_projects() if hasattr(self.project_mgr, "load_projects") else []
        hub = ProjectHubDialog(projects, self)
        hub.open_project.connect(self._switch_to_workspace)
        hub.create_new_clicked.connect(self._open_onboarding_dialog)
        hub.exec()

    def _open_onboarding_dialog(self):
        dlg = OnboardingDialog(self, self.project_mgr)
        dlg.project_configured.connect(self._on_new_project_configured)
        dlg.exec()

    def _on_new_project_configured(self, proj_data: dict):
        self.project_mgr.save_project(proj_data)
        self._switch_to_workspace(proj_data)

    def _switch_to_workspace(self, proj_data: dict):
        self.workspace_data = proj_data
        self._load_initial_workspace()

    def _reload_all_nodes(self):
        for pane in self.panes.values():
            pane.reload_page()

    def _on_attach_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Attach", "", "All Files (*.*)")
        if file_path:
            self.attached_file_path = file_path
            self.btn_attach.setText(f"Attached: {os.path.basename(file_path)}")
            self.btn_attach.setStyleSheet("background-color: #065f46; color: #a7f3d0; border: 1px solid #10b981;")

    def _on_send_immediate(self):
        prompt = self.input_prompt.text().strip()
        if not prompt and not self.attached_file_path:
            return
        target_id = self.combo_target.currentData()
        self.scheduler.add_task(
            target_id=target_id,
            prompt=prompt,
            target_datetime=QDateTime.currentDateTime(),
            file_path=self.attached_file_path
        )
        self.input_prompt.clear()
        self.attached_file_path = None
        self.btn_attach.setText("Attach")
        self.btn_attach.setStyleSheet("")

    def _open_scheduler_dialog(self):
        dlg = TaskSchedulerDialog(self.accounts, self)
        dlg.task_scheduled.connect(
            lambda data: self.scheduler.add_task(
                target_id=data["target_id"],
                prompt=data["prompt"],
                target_datetime=data.get("target_datetime", QDateTime.currentDateTime()),
                file_path=data["file_path"]
            )
        )
        dlg.exec()

    def _on_send_master_directive(self):
        user_goal = self.input_prompt.text().strip()
        if not user_goal:
            QMessageBox.warning(self, "Missing Goal", "Enter your high-level project specification in the prompt bar.")
            return

        master_id = self.combo_master.currentData()
        self.active_master_id = master_id
        master_acc = next((a for a in self.accounts if a["id"] == master_id), self.accounts[0])
        worker_accounts = [a for a in self.accounts if a["id"] != master_id] or [master_acc]

        project_name = self.input_project_name.text().strip() or self.project_name
        directive = self.orchestrator.build_master_directive(user_goal, project_name, worker_accounts)

        self.pipeline_worker_order = list(worker_accounts)
        self.assigned_files_display = {}
        self.current_node_statuses = {master_id: "active"}
        self.current_stage_statuses = {w["id"]: "waiting" for w in worker_accounts}
        self.current_gate_states = [{"state": "locked", "files": []} for _ in range(max(0, len(worker_accounts) - 1))]

        self.mind_map_tab.build_mind_map(master_acc, worker_accounts, {}, self.current_node_statuses)
        self.train_chart_tab.build_train_pipeline(worker_accounts, {}, self.current_stage_statuses, self.current_gate_states)
        self._save_or_update_current_session(create_new=True, label_suffix="Directive Sent")
        self.bottom_tabs.setCurrentWidget(self.mind_map_tab)

        self.scheduler.add_task(master_id, directive, target_datetime=QDateTime.currentDateTime())
        self.input_prompt.clear()

    def _on_extract_and_delegate(self):
        master_id = self.combo_master.currentData()
        self.active_master_id = master_id
        if master_id not in self.panes:
            return

        master_pane = self.panes[master_id]
        DOMScraper.scrape_page_text(
            master_pane.get_page(),
            lambda raw_text: self._process_master_blueprint(master_id, raw_text)
        )

    def _process_master_blueprint(self, master_id: str, raw_text: str):
        master_acc = next((a for a in self.accounts if a["id"] == master_id), self.accounts[0])
        worker_accounts = [a for a in self.accounts if a["id"] != master_id] or [master_acc]
        valid_worker_ids = [a["id"] for a in worker_accounts]

        tasks_by_worker, routing_map, assigned_files_display = self.orchestrator.parse_master_response(
            raw_text, valid_worker_ids
        )

        if not tasks_by_worker:
            QMessageBox.warning(self, "No Tasks Found", "Could not find ===TASK_START=== blocks in the Master Node yet.")
            return

        self.harvester.set_project_map(routing_map)
        self.harvested_stage_files.clear()
        self.harvested_stage_summaries.clear()
        self.worker_tasks_prompts = dict(tasks_by_worker)
        self.assigned_files_display = dict(assigned_files_display)

        matched_workers = [a for a in worker_accounts if a["id"] in tasks_by_worker]
        self.pipeline_worker_order = matched_workers if matched_workers else list(worker_accounts)

        self.current_node_statuses = {master_id: "done"}
        self.current_stage_statuses = {w["id"]: "waiting" for w in self.pipeline_worker_order}
        self.current_gate_states = [
            {"state": "locked", "files": []} for _ in range(max(0, len(self.pipeline_worker_order) - 1))
        ]

        self.mind_map_tab.build_mind_map(
            master_acc, self.pipeline_worker_order, self.assigned_files_display, self.current_node_statuses
        )
        self.train_chart_tab.build_train_pipeline(
            self.pipeline_worker_order, self.assigned_files_display, self.current_stage_statuses, self.current_gate_states
        )
        self._save_or_update_current_session(create_new=True, label_suffix="Pipeline Delegated")

        self.bottom_tabs.setCurrentWidget(self.train_chart_tab)
        mode = self.train_chart_tab.get_execution_mode()

        for stage_idx, acc in enumerate(self.pipeline_worker_order):
            wid = acc["id"]
            if wid not in tasks_by_worker:
                continue
            prompt = tasks_by_worker[wid]
            hold_gate = (mode == "pipeline" and stage_idx > 0)

            self.scheduler.add_task(
                target_id=wid,
                prompt=prompt,
                target_datetime=QDateTime.currentDateTime(),
                hold_for_gate=hold_gate,
                stage_index=stage_idx
            )

        if mode == "pipeline" and self.pipeline_worker_order:
            first_name = self.pipeline_worker_order[0]["account_name"]
            self.train_chart_tab.set_progress(10, f"Stage 1 Dispatched -> {first_name}")
        else:
            self.train_chart_tab.set_progress(25, "Parallel Swarm Dispatched (2s Turnstile)")

    def _on_stage_prompt_dispatched(self, account_id: str):
        if account_id not in self.panes:
            return
        if account_id == self.combo_master.currentData():
            self.current_node_statuses[account_id] = "active"
            self.mind_map_tab.update_node_status(account_id, "active")
            self._save_or_update_current_session(create_new=False)
            return

        acc = next((a for a in self.accounts if a["id"] == account_id), None)
        if not acc:
            return

        self.current_node_statuses[account_id] = "active"
        self.current_stage_statuses[account_id] = "running"
        self.mind_map_tab.update_node_status(account_id, "active")
        self.train_chart_tab.set_stage_status(account_id, "running")
        self._save_or_update_current_session(create_new=False)

        self.dom_watcher.start_watching(
            account_id=account_id, page=self.panes[account_id].get_page(),
            platform=acc["platform"], config=self.config
        )

    def _on_worker_generation_complete(self, account_id: str):
        self.dom_watcher.stop_watching(account_id)
        if account_id not in self.panes:
            return

        pane = self.panes[account_id]
        DOMScraper.scrape_page_text(
            pane.get_page(),
            lambda raw_text: self._harvest_stage_and_trigger_gate(account_id, raw_text)
        )

    def _build_cumulative_gate_file_entries(self, up_to_stage_idx: int) -> list:
        """
        Gathers ALL files harvested from Stage 1 up to up_to_stage_idx.
        Marks files as [Recommended] if:
          - They are explicitly mentioned in the next stage's Master task prompt, OR
          - They were produced by the immediately preceding stage (if no specific filename was mentioned).
        """
        next_stage_idx = up_to_stage_idx + 1
        next_prompt = ""
        if next_stage_idx < len(self.pipeline_worker_order):
            next_wid = self.pipeline_worker_order[next_stage_idx]["id"]
            next_prompt = (self.worker_tasks_prompts.get(next_wid) or "").lower()

        entries = []
        any_prompt_match = False

        for s_idx in range(up_to_stage_idx + 1):
            if s_idx >= len(self.pipeline_worker_order):
                break
            w_acc = self.pipeline_worker_order[s_idx]
            w_id = w_acc["id"]
            w_name = w_acc["account_name"]
            files = self.harvested_stage_files.get(w_id, [])

            for f_path in files:
                fname = os.path.basename(f_path)
                mentioned_in_next = bool(next_prompt and fname.lower() in next_prompt)
                if mentioned_in_next:
                    any_prompt_match = True
                entries.append({
                    "path": f_path,
                    "filename": fname,
                    "stage_num": s_idx + 1,
                    "account_name": w_name,
                    "mentioned": mentioned_in_next,
                    "from_immediate_prev": (s_idx == up_to_stage_idx),
                    "recommended": False
                })

        for entry in entries:
            if any_prompt_match:
                entry["recommended"] = entry["mentioned"] or entry["from_immediate_prev"]
            else:
                entry["recommended"] = entry["from_immediate_prev"]

        return entries

    def _harvest_stage_and_trigger_gate(self, account_id: str, raw_text: str):
        project_name = self.input_project_name.text().strip() or self.project_name
        created_files = self.harvester.parse_and_write_files(raw_text, project_name, account_id)
        summary_text = self.harvester.extract_summary(raw_text)

        self.harvested_stage_files[account_id] = created_files
        self.harvested_stage_summaries[account_id] = summary_text

        self.current_node_statuses[account_id] = "done"
        self.current_stage_statuses[account_id] = "completed"
        self.mind_map_tab.update_node_status(account_id, "done")
        self.train_chart_tab.set_stage_status(account_id, "completed")

        stage_indices = [i for i, a in enumerate(self.pipeline_worker_order) if a["id"] == account_id]
        if not stage_indices:
            self._save_or_update_current_session(create_new=False)
            return

        curr_idx = stage_indices[0]
        total_stages = len(self.pipeline_worker_order)

        if curr_idx < total_stages - 1:
            cumulative_entries = self._build_cumulative_gate_file_entries(curr_idx)
            while len(self.current_gate_states) <= curr_idx:
                self.current_gate_states.append({"state": "locked", "files": []})
            self.current_gate_states[curr_idx] = {
                "state": "awaiting_approval" if self.train_chart_tab.is_pause_for_approval() else "relayed",
                "files": cumulative_entries
            }
            self._save_or_update_current_session(create_new=False)

            if self.train_chart_tab.get_execution_mode() == "pipeline":
                self.train_chart_tab.activate_gate(curr_idx, cumulative_entries)
        else:
            self._save_or_update_current_session(create_new=False)
            zip_path = self.harvester.create_project_zip(project_name)
            self.train_chart_tab.set_progress(100, f"Pipeline Complete! Built Archive: {os.path.basename(zip_path)}")

    def _on_relay_gate_approved(self, gate_index: int, payload: dict):
        if gate_index + 1 >= len(self.pipeline_worker_order):
            return

        if 0 <= gate_index < len(self.current_gate_states):
            self.current_gate_states[gate_index]["state"] = "relayed"
            self._save_or_update_current_session(create_new=False)

        upstream_acc = self.pipeline_worker_order[gate_index]
        downstream_acc = self.pipeline_worker_order[gate_index + 1]

        send_summary = payload.get("send_summary", False)
        selected_files = payload.get("files", [])

        summary_to_inject = self.harvested_stage_summaries.get(upstream_acc["id"], "") if send_summary else ""

        pct = int(((gate_index + 1) / len(self.pipeline_worker_order)) * 100)
        self.train_chart_tab.set_progress(pct, f"Relaying {len(selected_files)} file(s) -> {downstream_acc['account_name']}...")

        self.scheduler.release_stage_task(
            account_id=downstream_acc["id"],
            appended_summary=summary_to_inject,
            relay_files=selected_files
        )

    def _on_execution_mode_switched(self, mode: str):
        if mode == "parallel":
            self.scheduler.release_all_held_tasks()
            self.train_chart_tab.set_progress(50, "Switched to Parallel Swarm â€” All Held Stages Released")

    def _on_harvest_all_nodes(self):
        project_name = self.input_project_name.text().strip() or self.project_name
        master_id = self.combo_master.currentData()
        worker_ids = [a["id"] for a in self.accounts if a["id"] != master_id] or [master_id]

        remaining = len(worker_ids)
        all_written = []

        def _on_scraped(acc_id, text):
            nonlocal remaining
            files = self.harvester.parse_and_write_files(text, project_name, acc_id)
            all_written.extend(files)
            remaining -= 1
            if remaining == 0:
                zip_path = self.harvester.create_project_zip(project_name)
                self.train_chart_tab.set_progress(100, f"Harvested {len(all_written)} files -> {os.path.basename(zip_path)}")
                QMessageBox.information(
                    self, "Workspace Harvested & Zipped",
                    f"Harvested {len(all_written)} files into:\n{self.harvester.get_project_build_dir(project_name)}\n\n"
                    f"Compiled Archive:\n{zip_path}"
                )

        for wid in worker_ids:
            if wid in self.panes:
                DOMScraper.scrape_page_text(self.panes[wid].get_page(), lambda txt, w=wid: _on_scraped(w, txt))

    def _on_node_status_changed(self, account_id: str, status: str):
        if account_id in self.panes:
            self.panes[account_id].set_status(status)

    def _show_rate_limit_toast(self, account_id: str, account_name: str, platform: str, resets_at: str):
        toast = RateLimitToast(account_id, account_name, platform, resets_at, self.toast_container)
        toast.auto_resume_clicked.connect(self.scheduler.schedule_auto_resume)
        self.toast_layout.addWidget(toast)
        self.toast_container.adjustSize()
        self.toast_container.move(
            self.width() - self.toast_container.width() - 20,
            self.height() - self.toast_container.height() - 20
        )
        self.toast_container.show()
