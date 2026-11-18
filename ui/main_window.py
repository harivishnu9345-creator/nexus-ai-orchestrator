import os
import re
import hashlib
from datetime import datetime
from PyQt6.QtGui import QAction, QColor, QBrush, QPainter, QNativeGestureEvent
from PyQt6.QtCore import Qt, QTime, QDateTime, QTimer, QEvent, QObject
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QScrollArea,
    QSplitter, QTabWidget, QFileDialog, QMessageBox, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog,
    QAbstractItemView, QGraphicsView
)

from core.session_manager import SessionManager
from core.project_manager import ProjectManager
from core.scheduler import TaskScheduler
from core.dom_scraper import DOMScraper
from core.dom_watcher import DOMWatcher
from core.swarm_orchestrator import SwarmOrchestrator
from core.code_harvester import CodeHarvester

from ui.web_pane import AIPane
from ui.file_vault_tab import ProjectFileVaultTab
from ui.model_monitor_tab import ModelEfficiencyMonitorTab
from ui.task_table import TaskTable
from ui.swarm_mind_map import SwarmMindMapWidget
from ui.binary_tree_relay_graph import BinaryTreeRelayGraphWidget
from ui.scheduler_dialog import TaskSchedulerDialog
from ui.toast_notification import RateLimitToast
from ui.project_hub import ProjectHubDialog
from ui.onboarding_dialog import OnboardingDialog

TEMPLATE_DUMMY_FILENAMES = {
    "filename.ext", "raw_filename.ext", "filename1.ext", "filename2.ext",
    "exact_filename1", "exact_filename2", "name.ext"
}


class MainWindow(QMainWindow):
    def __init__(self, config: dict, workspace_data: dict = None):
        super().__init__()
        self.config = config
        self.workspace_data = workspace_data or {}
        self.project_name = self.workspace_data.get("name", "Untitled_Workspace")

        app_cfg = config.get("app", {})
        self.setWindowTitle(f"{app_cfg.get('name', 'Nexus AI Orchestrator')} - {self.project_name} [Swarm Workstation]")
        self.resize(1600, 960)

        self.session_mgr = SessionManager(app_cfg.get("storage_root", "~/.nexus_orchestrator"))
        self.project_mgr = ProjectManager()
        self.scheduler = TaskScheduler(config, self)
        self.injector = self.scheduler.primary_injector
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
        self.worker_dependencies = {}
        self.assigned_files_display = {}
        self.harvested_stage_files = {}
        self.harvested_stage_summaries = {}
        self.current_node_statuses = {}
        self.current_stage_statuses = {}
        self.current_gate_states = []

        self.pipeline_sessions = []
        self.viewing_session_idx = -1
        self._live_harvest_seen = set()
        self._completed_stages_triggered = set()

        self._apply_carbon_black_theme()
        self._setup_menu_bar()
        self._setup_ui()
        self._connect_signals()
        self._load_initial_workspace()

        # Start live on-the-spot code & summary harvester timer (every 4.0s)
        self._live_harvest_timer = QTimer(self)
        self._live_harvest_timer.timeout.connect(self._poll_live_code_harvest)
        self._live_harvest_timer.start(4000)

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
        act_open_json = QAction("Open Project JSON...", self)
        act_open_json.setShortcut("Ctrl+O")
        act_open_json.triggered.connect(self._action_open_project_json)
        file_menu.addAction(act_open_json)

        act_save_proj = QAction("Save Project", self)
        act_save_proj.setShortcut("Ctrl+S")
        act_save_proj.triggered.connect(self._action_save_project)
        file_menu.addAction(act_save_proj)

        act_save_as_proj = QAction("Save Project As...", self)
        act_save_as_proj.setShortcut("Ctrl+Shift+S")
        act_save_as_proj.triggered.connect(self._action_save_project_as)
        file_menu.addAction(act_save_as_proj)

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
        view_menu.addAction("Project Files & Context Vault", lambda: self.bottom_tabs.setCurrentIndex(3))
        view_menu.addAction("Model Modes & Usage Monitor", lambda: self.bottom_tabs.setCurrentIndex(4))

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
        self.combo_master.setFixedWidth(185)
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

        # ROW 3: Splitter (Top Browser Panes + Bottom 5-Tab Control Center)
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        self.h_scroll = QScrollArea()
        self.h_scroll.setWidgetResizable(True)
        self.h_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.h_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.h_scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: #09090b; }
            QScrollBar:horizontal {
                background: #141417; height: 14px;
                border-top: 1px solid #27272a; border-bottom: 1px solid #27272a; margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #52525b; min-width: 80px; border-radius: 4px; margin: 2px 4px;
            }
            QScrollBar::handle:horizontal:hover { background: #71717a; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
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
        self.bottom_tabs.setMinimumHeight(250)

        # Tab 1: System Task Queue & Execution Log
        self.task_table = TaskTable(self)
        self.bottom_tabs.addTab(self.task_table, "System Task Queue && Execution Log")

        # Tab 2: Task Assignment Mind-Map
        self.mind_map_tab = SwarmMindMapWidget(self)
        self.bottom_tabs.addTab(self.mind_map_tab, "Task Assignment Mind-Map")

        # Tab 4 (created before Tab 3 so Tab 3 can reference self.file_vault_tab): Project Files & Context Vault
        self.file_vault_tab = ProjectFileVaultTab(
            injector=self.injector,
            get_panes_fn=lambda: self.panes,
            get_project_fn=self._get_active_project_dict,
            save_project_fn=self.project_mgr.save_project,
            parent=self
        )

        # Tab 3: Execution Flow & File Relay (Unified 3-Mode Binary Tree / DAG / Parallel Graph)
        self.binary_tree_graph = BinaryTreeRelayGraphWidget(
            injector=self.injector,
            get_panes_fn=lambda: self.panes,
            get_project_fn=self._get_active_project_dict,
            get_vault_tab_fn=lambda: self.file_vault_tab,
            parent=self
        )
        self.train_chart_tab = self.binary_tree_graph
        self.bottom_tabs.addTab(self.binary_tree_graph, "Execution Flow && File Relay")

        # Add Tab 4 & Tab 5
        self.bottom_tabs.addTab(self.file_vault_tab, "Project Files && Context Vault")

        self.model_monitor_tab = ModelEfficiencyMonitorTab(
            get_panes_fn=lambda: self.panes,
            parent=self
        )
        self.bottom_tabs.addTab(self.model_monitor_tab, "Model Modes && Usage Monitor")

        self.splitter.addWidget(self.bottom_tabs)
        self.splitter.setSizes([590, 290])
        main_layout.addWidget(self.splitter, stretch=1)

        # ROW 4: Status Bar
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

        self._enhance_mind_map_zoom_and_fit()
        self._mount_mind_map_url_tracer_drawer()

    def _connect_signals(self):
        self.scheduler.queue_updated.connect(self._on_queue_updated)
        self.scheduler.task_status_changed.connect(self._on_node_status_changed)
        self.scheduler.rate_limit_detected.connect(self._show_rate_limit_toast)
        self.scheduler.sub_injector_telemetry.connect(
            lambda msg: self.binary_tree_graph.set_progress(self.binary_tree_graph.progress_bar.value(), msg)
        )
        self.scheduler.stage_dispatched.connect(self._on_stage_prompt_dispatched)
        self.task_table.clear_clicked.connect(self.scheduler.clear_completed)
        self.dom_watcher.generation_complete.connect(self._on_worker_generation_complete)

        self.binary_tree_graph.relay_gate_approved.connect(self._on_relay_gate_approved)
        self.binary_tree_graph.execution_mode_changed.connect(self._on_execution_mode_switched)
        self.binary_tree_graph.strategy_topology_changed.connect(self.mind_map_tab.set_topology_mode)
        self.binary_tree_graph.force_stage_complete.connect(self._on_worker_generation_complete)

        self.mind_map_tab.session_selected.connect(self._on_session_history_selected)
        self.binary_tree_graph.session_selected.connect(self._on_session_history_selected)

        self.file_vault_tab.explicit_file_request_detected.connect(
            self.binary_tree_graph.on_explicit_file_request
        )
        self.file_vault_tab.recommendations_updated.connect(
            lambda _recs: self.binary_tree_graph.refresh_dropdowns()
        )

    def _get_active_project_dict(self) -> dict:
        if isinstance(self.workspace_data, dict):
            return self.workspace_data
        self.workspace_data = {
            "id": "proj_local",
            "name": self.project_name,
            "accounts": self.accounts,
            "file_vault": {"files": [], "folders": []}
        }
        return self.workspace_data

    # ==========================================================================
    # Workspace & Pane Lifecycle
    # ==========================================================================
    def _clear_current_panes(self):
        for pane in self.panes.values():
            pane.cleanup()
            pane.deleteLater()
        self.panes.clear()
        while self.strip_layout.count():
            item = self.strip_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

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
            self.workspace_data["accounts"] = self.accounts

        self.input_project_name.setText(self.project_name)
        self.setWindowTitle(f"Nexus AI Orchestrator - {self.project_name} [Swarm Workstation]")

        self.combo_target.blockSignals(True)
        self.combo_master.blockSignals(True)
        self.combo_target.clear()
        self.combo_master.clear()
        self.combo_target.addItem("Broadcast to All Active Nodes", "all")

        default_zoom = self.config.get("app", {}).get("default_zoom", 0.75)
        node_urls = self.workspace_data.setdefault("node_urls", {})

        for acc in self.accounts:
            acc_id = acc["id"]
            platform = acc.get("platform", "claude").lower()
            plat_cfg = self.config.get("platforms", {}).get(platform, {})
            start_url = (
                node_urls.get(acc_id)
                or acc.get("current_url")
                or acc.get("last_url")
                or plat_cfg.get("home_url", "https://claude.ai/new")
            )

            profile_key = acc.get("profile_id") or acc_id
            profile = self.session_mgr.get_or_create_profile(profile_key, self)
            pane = AIPane(acc_id, acc["account_name"], platform, profile, start_url, default_zoom, self)
            pane.url_changed.connect(self._on_pane_url_changed)
            if hasattr(pane, "url_changed_trace"):
                pane.url_changed_trace.connect(self._on_pane_url_changed_trace)
            pane.move_requested.connect(self._on_move_pane_requested)

            self.strip_layout.addWidget(pane)
            self.strip_layout.setStretchFactor(pane, 1)
            self.panes[acc_id] = pane
            self.scheduler.register_pane(acc_id, pane, acc)

            label = f"{acc['account_name']} ({platform.capitalize()})"
            self.combo_target.addItem(label, acc_id)
            self.combo_master.addItem(label, acc_id)

        self.combo_target.blockSignals(False)
        self.combo_master.blockSignals(False)

        saved_master_id = self.workspace_data.get("master_node_id")
        if saved_master_id:
            m_idx = self.combo_master.findData(saved_master_id)
            if m_idx >= 0:
                self.combo_master.blockSignals(True)
                self.combo_master.setCurrentIndex(m_idx)
                self.combo_master.blockSignals(False)

        # 1. Restore Persistent Task Queue History
        saved_tasks = self.workspace_data.get("task_history", [])
        self.scheduler.load_serialized_tasks(saved_tasks)

        # 2. Restore Persistent Pipeline Sessions
        saved_sessions = self.workspace_data.get("pipeline_sessions", [])
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

            self.active_master_id = self.combo_master.currentData()
            self.workspace_data["master_node_id"] = self.active_master_id

            self.pipeline_worker_order = latest.get("worker_accounts") or [
                a for a in self.accounts if a["id"] != self.active_master_id
            ]
            self.assigned_files_display = dict(latest.get("assigned_files") or {})
            self.current_node_statuses = dict(latest.get("node_statuses") or {})
            self.current_stage_statuses = dict(latest.get("stage_statuses") or {})
            self.current_gate_states = list(latest.get("gate_states") or [])

            self._on_session_history_selected(latest_idx)
        else:
            self.pipeline_sessions = []
            self._on_master_architect_changed()

        self.file_vault_tab.refresh_targets_and_view()
        self.model_monitor_tab.rebuild_node_rows()
        self._refresh_mindmap_url_trace_table()

        self.lbl_status_bar.setText(
            f"System Ready | Workspace: {self.project_name} | Active Nodes: {len(self.accounts)} (Horizontal Scroll Enabled) | Turnstile Poll: 2000ms"
        )

    # ==========================================================================
    # Master Architect Sync & Session History Management
    # ==========================================================================
    def _on_master_architect_changed(self, _index: int = 0):
        if not self.accounts:
            return
        master_id = self.combo_master.currentData()
        if not master_id:
            return

        self.active_master_id = master_id
        self.workspace_data["master_node_id"] = master_id

        master_acc = next((a for a in self.accounts if a["id"] == master_id), self.accounts[0])
        workers = [a for a in self.accounts if a["id"] != master_id] or [master_acc]

        self.pipeline_worker_order = list(workers)
        self.assigned_files_display = {}
        self.current_node_statuses = {master_id: "idle"}
        self.current_stage_statuses = {w["id"]: "waiting" for w in workers}
        self.current_gate_states = [{"state": "locked", "files": []} for _ in range(max(0, len(workers) - 1))]

        self.mind_map_tab.build_mind_map(master_acc, workers, self.assigned_files_display, self.current_node_statuses)
        self.binary_tree_graph.set_master_and_workers(
            master_account=master_acc,
            worker_accounts=workers,
            assigned_files=self.assigned_files_display,
            stage_statuses=self.current_stage_statuses,
            gate_states=self.current_gate_states
        )
        self._save_or_update_current_session(create_new=False)

    def _save_or_update_current_session(self, create_new: bool = False, label_suffix: str = ""):
        if not self.accounts:
            return
        master_id = self.combo_master.currentData() or self.accounts[0]["id"]
        master_acc = next((a for a in self.accounts if a["id"] == master_id), self.accounts[0])
        workers = self.pipeline_worker_order or [a for a in self.accounts if a["id"] != master_id]

        if create_new or not self.pipeline_sessions:
            ts = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            session_num = len(self.pipeline_sessions) + 1
            title = f"Session #{session_num} - {ts} (Master: {master_acc['account_name']})"
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

        labels = [s["title"].replace("\u00e2\u20ac\u201d", "-").replace("\u2014", "-") for s in self.pipeline_sessions]
        self.mind_map_tab.set_session_list(labels, self.viewing_session_idx)
        self.binary_tree_graph.set_session_list(labels, self.viewing_session_idx)

        if self.workspace_data and self.workspace_data.get("id"):
            self.project_mgr.save_pipeline_sessions(self.workspace_data["id"], self.pipeline_sessions)

    def _on_session_history_selected(self, idx: int):
        if not (0 <= idx < len(self.pipeline_sessions)):
            return
        self.viewing_session_idx = idx
        snap = self.pipeline_sessions[idx]

        labels = [s["title"].replace("\u00e2\u20ac\u201d", "-").replace("\u2014", "-") for s in self.pipeline_sessions]
        self.mind_map_tab.set_session_list(labels, idx)
        self.binary_tree_graph.set_session_list(labels, idx)

        master_acc = snap.get("master_account") or (self.accounts[0] if self.accounts else {})
        workers = snap.get("worker_accounts") or []
        assigned_files = snap.get("assigned_files") or {}
        node_statuses = snap.get("node_statuses") or {}
        stage_statuses = snap.get("stage_statuses") or {}
        gate_states = snap.get("gate_states") or []

        if master_acc.get("id"):
            self.workspace_data["master_node_id"] = master_acc["id"]

        self.mind_map_tab.build_mind_map(master_acc, workers, assigned_files, node_statuses)
        self.binary_tree_graph.set_master_and_workers(
            master_account=master_acc,
            worker_accounts=workers,
            assigned_files=assigned_files,
            stage_statuses=stage_statuses,
            gate_states=gate_states
        )

        is_latest = (idx == len(self.pipeline_sessions) - 1)
        if not is_latest:
            self.binary_tree_graph.set_progress(100, f"Viewing Historical Snapshot: {snap.get('title', '')}")

    # ==========================================================================
    # Swarm Pipeline Actions (1. Send Directive, 2. Extract & Delegate, 3. Harvest)
    # ==========================================================================
    def _on_send_master_directive(self):
        user_goal = self.input_prompt.text().strip()
        if not user_goal:
            QMessageBox.warning(self, "Missing Goal", "Enter your high-level project specification in the prompt bar.")
            return

        master_id = self.combo_master.currentData()
        self.active_master_id = master_id
        self.workspace_data["master_node_id"] = master_id

        master_acc = next((a for a in self.accounts if a["id"] == master_id), self.accounts[0])
        worker_accounts = [a for a in self.accounts if a["id"] != master_id] or [master_acc]

        project_name = self.input_project_name.text().strip() or self.project_name
        strategy_topo = self.binary_tree_graph.get_strategy_topology()
        directive = self.orchestrator.build_master_directive(
            user_goal, project_name, worker_accounts, strategy_mode=strategy_topo
        )

        self.pipeline_worker_order = list(worker_accounts)
        self.assigned_files_display = {}
        self.current_node_statuses = {master_id: "active"}
        self.current_stage_statuses = {w["id"]: "waiting" for w in worker_accounts}
        self.current_gate_states = [{"state": "locked", "files": []} for _ in range(max(0, len(worker_accounts) - 1))]

        self.mind_map_tab.build_mind_map(master_acc, worker_accounts, {}, self.current_node_statuses)
        self.binary_tree_graph.set_master_and_workers(
            master_account=master_acc,
            worker_accounts=worker_accounts,
            assigned_files={},
            stage_statuses=self.current_stage_statuses,
            gate_states=self.current_gate_states
        )
        self._save_or_update_current_session(create_new=True, label_suffix="Directive Sent")
        self.bottom_tabs.setCurrentWidget(self.mind_map_tab)

        self.scheduler.add_task(master_id, directive, target_datetime=QDateTime.currentDateTime())
        self.input_prompt.clear()

    def _on_extract_and_delegate(self):
        # Automatically find whichever open pane contains the blueprint (===TASK_START=== or ===MAP_START===)
        panes = getattr(self, "panes", {})
        if not panes:
            return

        master_id = self.combo_master.currentData()
        if master_id not in panes:
            master_id = list(panes.keys())[0]

        # Scan all panes in parallel to find the one with the blueprint
        results = {}
        pending = len(panes)
        scraped_master_id = [master_id]

        def _check_all():
            chosen_id = scraped_master_id[0]
            chosen_txt = results.get(chosen_id, "")
            if "TASK_START" not in chosen_txt:
                for aid, txt in results.items():
                    if "TASK_START" in txt or "MAP_START" in txt:
                        chosen_id = aid
                        chosen_txt = txt
                        break

            if "TASK_START" not in chosen_txt and hasattr(self, "_fallback_extract_and_delegate_from_any_master"):
                self._fallback_extract_and_delegate_from_any_master()
                return

            self.active_master_id = chosen_id
            self.workspace_data["master_node_id"] = chosen_id
            m_idx = self.combo_master.findData(chosen_id)
            if m_idx >= 0:
                self.combo_master.blockSignals(True)
                self.combo_master.setCurrentIndex(m_idx)
                self.combo_master.blockSignals(False)

            self._process_master_blueprint(chosen_id, chosen_txt)

        for aid, pane in panes.items():
            def _make_cb(acc_id=aid):
                nonlocal pending
                def _on_txt(t):
                    nonlocal pending
                    results[acc_id] = t or ""
                    pending -= 1
                    if pending == 0:
                        _check_all()
                return _on_txt
            DOMScraper.scrape_page_text(pane.get_page(), _make_cb(aid))

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
        self._completed_stages_triggered.clear()
        self.worker_tasks_prompts = dict(tasks_by_worker)
        self.worker_dependencies = self.orchestrator.get_worker_dependencies()
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
        self.binary_tree_graph.set_master_and_workers(
            master_account=master_acc,
            worker_accounts=self.pipeline_worker_order,
            assigned_files=self.assigned_files_display,
            stage_statuses=self.current_stage_statuses,
            gate_states=self.current_gate_states
        )
        self._save_or_update_current_session(create_new=True, label_suffix="Pipeline Delegated")

        self.bottom_tabs.setCurrentWidget(self.binary_tree_graph)
        mode = self.binary_tree_graph.get_execution_mode()
        topo = self.binary_tree_graph.get_strategy_topology()

        dispatched_names = []
        for stage_idx, acc in enumerate(self.pipeline_worker_order):
            wid = acc["id"]
            if wid not in tasks_by_worker:
                continue
            prompt = tasks_by_worker[wid]
            deps = self.worker_dependencies.get(wid, {})
            req_files = deps.get("required_files", [])
            req_sums = deps.get("required_summaries", [])

            if mode == "parallel":
                hold_gate = False
            elif topo == "binary_tree":
                # In Binary Tree mode: L1 Left (idx 0) and L1 Right (idx 1) run simultaneously
                # UNLESS L1 Right explicitly requires a file/summary from L1 Left!
                if stage_idx == 0:
                    hold_gate = False
                elif stage_idx == 1 and not req_files and not req_sums:
                    hold_gate = False
                else:
                    hold_gate = True
            else:
                # Sequential DAG mode: Stage 1 runs immediately; Stage 2+ wait at their gates
                hold_gate = (stage_idx > 0)

            if not hold_gate:
                dispatched_names.append(acc["account_name"])

            self.scheduler.add_task(
                target_id=wid,
                prompt=prompt,
                target_datetime=QDateTime.currentDateTime(),
                hold_for_gate=hold_gate,
                stage_index=stage_idx
            )

        if dispatched_names:
            self.binary_tree_graph.set_progress(12, f"Dispatched Active Branch(es): {', '.join(dispatched_names[:2])}")
        else:
            self.binary_tree_graph.set_progress(25, "Swarm Dispatched (2s Turnstile)")

    def _on_stage_prompt_dispatched(self, account_id: str):
        if account_id not in self.panes:
            return
        if account_id == self.combo_master.currentData():
            self.current_node_statuses[account_id] = "active"
            self.mind_map_tab.update_node_status(account_id, "active")
            self.binary_tree_graph.set_stage_status(account_id, "RUNNING")
            self._save_or_update_current_session(create_new=False)
            return

        acc = next((a for a in self.accounts if a["id"] == account_id), None)
        if not acc:
            return

        self.current_node_statuses[account_id] = "active"
        self.current_stage_statuses[account_id] = "running"
        self.mind_map_tab.update_node_status(account_id, "active")
        self.binary_tree_graph.set_stage_status(account_id, "RUNNING")
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
        Builds the cumulative pool of all files harvested up to `up_to_stage_idx`.
        Strictly marks a file as `recommended = True` ONLY if the Master Architect
        specified it in `required_files` for the next stage or the next stage's prompt
        explicitly names that file! Other generated files remain `recommended = False` (unchecked).
        """
        next_stage_idx = up_to_stage_idx + 1
        next_prompt = ""
        master_req_files_low = set()
        if next_stage_idx < len(self.pipeline_worker_order):
            next_wid = self.pipeline_worker_order[next_stage_idx]["id"]
            next_prompt = (self.worker_tasks_prompts.get(next_wid) or "").lower()
            deps = self.worker_dependencies.get(next_wid, {})
            master_req_files_low = {f.lower() for f in deps.get("required_files", [])}

        entries = []
        any_explicit_rec = False

        for s_idx in range(up_to_stage_idx + 1):
            if s_idx >= len(self.pipeline_worker_order):
                break
            w_acc = self.pipeline_worker_order[s_idx]
            w_id = w_acc["id"]
            w_name = w_acc["account_name"]

            # Merge files from CodeHarvester AND live_cache so zero files are missed
            stage_paths = list(self.harvested_stage_files.get(w_id, []))
            if w_id in self.binary_tree_graph.node_items:
                for c_path in self.binary_tree_graph.node_items[w_id].cached_files.values():
                    if c_path not in stage_paths and os.path.exists(c_path):
                        stage_paths.append(c_path)

            for f_path in stage_paths:
                fname = os.path.basename(f_path)
                if fname.lower() in TEMPLATE_DUMMY_FILENAMES:
                    continue
                is_master_required = (fname.lower() in master_req_files_low) or bool(next_prompt and fname.lower() in next_prompt)
                if is_master_required:
                    any_explicit_rec = True
                entries.append({
                    "path": f_path,
                    "filename": fname,
                    "stage_num": s_idx + 1,
                    "account_name": w_name,
                    "mentioned": is_master_required,
                    "from_immediate_prev": (s_idx == up_to_stage_idx),
                    "recommended": is_master_required
                })

        # Fallback: If the Master prompt didn't name any specific upstream file at all,
        # recommend only the first non-manifest code file from the immediately preceding stage
        if not any_explicit_rec and entries:
            prev_entries = [e for e in entries if e["from_immediate_prev"]]
            code_prev = [e for e in prev_entries if not e["filename"].lower().endswith(".json")]
            target_rec = code_prev[0] if code_prev else (prev_entries[0] if prev_entries else entries[-1])
            target_rec["recommended"] = True

        return entries

    def _harvest_stage_and_trigger_gate(self, account_id: str, raw_text: str):
        project_name = self.input_project_name.text().strip() or self.project_name
        created_files = [
            fp for fp in self.harvester.parse_and_write_files(raw_text, project_name, account_id)
            if os.path.basename(fp).lower() not in TEMPLATE_DUMMY_FILENAMES
        ]

        # Also include any files already caught in live_cache for this account
        if account_id in self.binary_tree_graph.node_items:
            for c_path in self.binary_tree_graph.node_items[account_id].cached_files.values():
                if c_path not in created_files and os.path.exists(c_path):
                    created_files.append(c_path)

        summary_text = self.harvester.extract_summary(raw_text)

        self.harvested_stage_files[account_id] = created_files
        if summary_text:
            self.harvested_stage_summaries[account_id] = summary_text

        for fpath in created_files:
            self.binary_tree_graph.on_file_harvested_live(account_id, os.path.basename(fpath), fpath)

        self.current_node_statuses[account_id] = "done"
        self.current_stage_statuses[account_id] = "completed"
        self.mind_map_tab.update_node_status(account_id, "done")
        self.binary_tree_graph.set_stage_status(account_id, "COMPLETED")

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
                "state": "awaiting_approval" if self.binary_tree_graph.is_pause_for_approval() else "relayed",
                "files": cumulative_entries
            }
            self._save_or_update_current_session(create_new=False)

            if self.binary_tree_graph.get_execution_mode() == "pipeline":
                self.binary_tree_graph.activate_gate(curr_idx, cumulative_entries)
        else:
            self._save_or_update_current_session(create_new=False)
            zip_path = self.harvester.create_project_zip(project_name)
            self.binary_tree_graph.set_progress(100, f"Pipeline Complete! Built Archive: {os.path.basename(zip_path)}")

    def _on_relay_gate_approved(self, gate_index: int, payload: dict):
        if gate_index + 1 >= len(self.pipeline_worker_order):
            return

        if 0 <= gate_index < len(self.current_gate_states):
            self.current_gate_states[gate_index]["state"] = "relayed"
            self._save_or_update_current_session(create_new=False)

        upstream_acc = self.pipeline_worker_order[gate_index]
        downstream_acc = self.pipeline_worker_order[gate_index + 1]

        send_summary = payload.get("send_summary", False)
        custom_summary_text = (payload.get("custom_summary_text") or "").strip()
        selected_files = [
            f for f in payload.get("files", [])
            if os.path.basename(f).lower() not in TEMPLATE_DUMMY_FILENAMES and os.path.exists(f)
        ]

        if send_summary:
            summary_to_inject = custom_summary_text or self.harvested_stage_summaries.get(upstream_acc["id"], "")
        else:
            summary_to_inject = ""

        pct = int(((gate_index + 1) / len(self.pipeline_worker_order)) * 100)
        self.binary_tree_graph.set_progress(pct, f"Relaying {len(selected_files)} file(s) -> {downstream_acc['account_name']}...")

        self.scheduler.release_stage_task(
            account_id=downstream_acc["id"],
            appended_summary=summary_to_inject,
            relay_files=selected_files
        )

    def _on_execution_mode_switched(self, mode: str):
        if mode == "parallel":
            self.scheduler.release_all_held_tasks()
            self.binary_tree_graph.recompute_true_progress("Parallel Swarm Active - Held Stages Released")
        else:
            self.binary_tree_graph.recompute_true_progress()

    def _on_harvest_all_nodes(self):
        project_name = self.input_project_name.text().strip() or self.project_name
        master_id = self.combo_master.currentData()
        worker_ids = [a["id"] for a in self.accounts if a["id"] != master_id] or [master_id]

        remaining = len(worker_ids)
        all_written = []

        def _on_scraped(acc_id, text):
            nonlocal remaining
            files = [
                fp for fp in self.harvester.parse_and_write_files(text, project_name, acc_id)
                if os.path.basename(fp).lower() not in TEMPLATE_DUMMY_FILENAMES
            ]
            for fp in files:
                self.binary_tree_graph.on_file_harvested_live(acc_id, os.path.basename(fp), fp)
            all_written.extend(files)
            remaining -= 1
            if remaining == 0:
                zip_path = self.harvester.create_project_zip(project_name)
                self.binary_tree_graph.set_progress(100, f"Harvested {len(all_written)} files -> {os.path.basename(zip_path)}")
                QMessageBox.information(
                    self, "Workspace Harvested & Zipped",
                    f"Harvested {len(all_written)} files into:\n{self.harvester.get_project_build_dir(project_name)}\n\n"
                    f"Compiled Archive:\n{zip_path}"
                )

        for wid in worker_ids:
            if wid in self.panes:
                DOMScraper.scrape_page_text(self.panes[wid].get_page(), lambda txt, w=wid: _on_scraped(w, txt))

    # ==========================================================================
    # Live On-the-Spot Code & Summary Harvester (Auto-Advances Gate on ===END_SUMMARY===)
    # ==========================================================================
    def _poll_live_code_harvest(self):
        if not self.panes or not hasattr(self, "binary_tree_graph"):
            return

        proj = self._get_active_project_dict()
        proj_name = re.sub(r"[^a-zA-Z0-9_-]", "_", proj.get("name", self.project_name))
        cache_dir = os.path.abspath(os.path.join("builds", proj_name, "_live_cache"))
        os.makedirs(cache_dir, exist_ok=True)

        file_block_rx = re.compile(
            r"={1,3}[ \t]*FILE:[ \t]*([^=\r\n]+?)[ \t]*={1,3}[ \t]*\r?\n"
            r"(?:```[a-zA-Z0-9_-]*[ \t]*\r?\n)?"
            r"(.*?)"
            r"(?:\r?\n```[ \t]*(?=\s*={1,3}[ \t]*(?:FILE:|SUMMARY|END_SUMMARY|TASK_END)|\s*\Z)|"
            r"\r?\n[ \t]*={1,3}[ \t]*(?:FILE:|SUMMARY|END_SUMMARY|TASK_END))",
            re.DOTALL
        )
        summary_rx = re.compile(
            r"={1,3}[ \t]*SUMMARY[ \t]*={1,3}\s*(.*?)\s*={1,3}[ \t]*END_SUMMARY[ \t]*={1,3}",
            re.DOTALL | re.IGNORECASE
        )

        for aid, pane in self.panes.items():
            def _make_cb(acc_id=aid):
                def _on_text(text: str):
                    if not text:
                        return
                    # 1. Harvest any ===SUMMARY=== ... ===END_SUMMARY=== blocks
                    s_matches = summary_rx.findall(text)
                    if s_matches:
                        clean_sum = s_matches[-1].strip()
                        if clean_sum and "Bullet summary of exact APIs" not in clean_sum:
                            self.harvested_stage_summaries[acc_id] = clean_sum

                    # 2. Harvest any ===FILE: ...=== blocks
                    if "FILE:" in text:
                        for m in file_block_rx.finditer(text):
                            raw_fname = os.path.basename(m.group(1).strip())
                            if raw_fname.lower() in TEMPLATE_DUMMY_FILENAMES:
                                continue
                            code_body = m.group(2).strip()
                            code_body = re.sub(r"(?:^|\r?\n)```[a-zA-Z0-9_-]*[ \t]*$", "", code_body).strip()
                            if not raw_fname or len(code_body) < 10 or "// full code here" in code_body:
                                continue
                            body_hash = hashlib.sha256(code_body.encode("utf-8", errors="ignore")).hexdigest()[:16]
                            sig = f"{acc_id}:{raw_fname}:{body_hash}"
                            if sig not in self._live_harvest_seen:
                                self._live_harvest_seen.add(sig)
                                out_path = os.path.join(cache_dir, raw_fname)
                                try:
                                    with open(out_path, "w", encoding="utf-8") as f:
                                        f.write(code_body + "\n")
                                    self.harvested_stage_files.setdefault(acc_id, [])
                                    if out_path not in self.harvested_stage_files[acc_id]:
                                        self.harvested_stage_files[acc_id].append(out_path)
                                    self.binary_tree_graph.on_file_harvested_live(acc_id, raw_fname, out_path)
                                except Exception:
                                    pass

                    # 3. Auto-trigger Stage Gate if worker finished ===END_SUMMARY=== and has harvested files!
                    if (
                        acc_id != self.combo_master.currentData()
                        and acc_id not in self._completed_stages_triggered
                        and self.harvested_stage_files.get(acc_id)
                        and acc_id in self.harvested_stage_summaries
                    ):
                        self._completed_stages_triggered.add(acc_id)
                        self._harvest_stage_and_trigger_gate(acc_id, text)
                return _on_text

            DOMScraper.scrape_page_text(pane.get_page(), _make_cb())

    # ==========================================================================
    # Mind-Map Zoom & URL Trace Drawer Helpers
    # ==========================================================================
    def _enhance_mind_map_zoom_and_fit(self):
        found_gvs = self.mind_map_tab.findChildren(QGraphicsView)
        if not found_gvs:
            return
        gv = found_gvs[0]
        self._mind_map_gv = gv
        gv.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        gv.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        gv.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        gv.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def _mount_mind_map_url_tracer_drawer(self):
        mm_layout = self.mind_map_tab.layout()
        if mm_layout is None:
            return

        top_bar_lay = None
        for btn in self.mind_map_tab.findChildren(QPushButton):
            if "Center" in (btn.text() or "") or "100%" in (btn.text() or ""):
                if btn.parentWidget() and isinstance(btn.parentWidget().layout(), QHBoxLayout):
                    top_bar_lay = btn.parentWidget().layout()
                    break

        self.btn_toggle_url_trace = QPushButton("\U0001f517 Show URL Tracing (OFF)")
        self.btn_toggle_url_trace.setCheckable(True)
        self.btn_toggle_url_trace.setChecked(False)
        self.btn_toggle_url_trace.setStyleSheet("""
            QPushButton { background-color: #1e293b; color: #38bdf8; border: 1px solid #0284c7; border-radius: 3px; padding: 4px 10px; font-size: 11px; font-weight: bold; }
            QPushButton:checked { background-color: #0284c7; color: #ffffff; border: 1px solid #38bdf8; }
        """)
        self.btn_toggle_url_trace.toggled.connect(self._on_toggle_mindmap_url_tracer)

        self.btn_import_chat_url = QPushButton("\U0001f4e5 Import / Change Node URL...")
        self.btn_import_chat_url.setStyleSheet("""
            QPushButton { background-color: #ea580c; color: #ffffff; border: 1px solid #f97316; border-radius: 3px; padding: 4px 10px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background-color: #c2410c; }
        """)
        self.btn_import_chat_url.clicked.connect(self._on_import_chat_url_dialog)

        if top_bar_lay is not None:
            top_bar_lay.insertWidget(0, self.btn_import_chat_url)
            top_bar_lay.insertWidget(0, self.btn_toggle_url_trace)

        self.url_trace_drawer = QFrame(self.mind_map_tab)
        self.url_trace_drawer.setFixedHeight(135)
        self.url_trace_drawer.setVisible(False)
        self.url_trace_drawer.setStyleSheet("""
            QFrame { background-color: #141417; border: 1px solid #27272a; border-radius: 4px; }
            QLabel { color: #38bdf8; font-size: 11px; font-weight: bold; border: none; }
        """)
        dl = QVBoxLayout(self.url_trace_drawer)
        dl.setContentsMargins(6, 4, 6, 4)
        dl.setSpacing(3)

        hdr_lay = QHBoxLayout()
        self.lbl_trace_header = QLabel("\U0001f517 Live Mind-Map URL Tracing & Chat Session History (Double-click any row to edit/import URL)")
        btn_clear_trace = QPushButton("Clear Trace Log")
        btn_clear_trace.setFixedWidth(105)
        btn_clear_trace.clicked.connect(self._clear_url_trace_history)
        hdr_lay.addWidget(self.lbl_trace_header)
        hdr_lay.addStretch()
        hdr_lay.addWidget(btn_clear_trace)
        dl.addLayout(hdr_lay)

        self.url_trace_table = QTableWidget(0, 5, self.url_trace_drawer)
        self.url_trace_table.setHorizontalHeaderLabels([
            "Node / Account", "Platform", "Current Live Chat URL (Editable)", "Previous URL -> Transition Trail", "Last Changed"
        ])
        self.url_trace_table.setAlternatingRowColors(True)
        self.url_trace_table.setStyleSheet("""
            QTableWidget { background-color: #09090b; alternate-background-color: #121215; color: #f4f4f5; gridline-color: #27272a; border: 1px solid #27272a; font-size: 10px; font-family: Consolas, monospace; }
            QHeaderView::section { background-color: #18181b; color: #a1a1aa; padding: 3px 6px; border: none; border-right: 1px solid #27272a; border-bottom: 1px solid #27272a; font-weight: bold; font-size: 10px; }
        """)
        th = self.url_trace_table.horizontalHeader()
        th.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        th.setStretchLastSection(True)
        self.url_trace_table.setColumnWidth(0, 145)
        self.url_trace_table.setColumnWidth(1, 70)
        self.url_trace_table.setColumnWidth(2, 340)
        self.url_trace_table.setColumnWidth(3, 340)
        self.url_trace_table.verticalHeader().setVisible(False)
        self.url_trace_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.url_trace_table.cellDoubleClicked.connect(self._on_trace_table_double_clicked)

        dl.addWidget(self.url_trace_table, stretch=1)
        mm_layout.addWidget(self.url_trace_drawer)

    def _on_toggle_mindmap_url_tracer(self, checked: bool):
        self.btn_toggle_url_trace.setText(f"\U0001f517 Show URL Tracing ({'ON' if checked else 'OFF'})")
        self.url_trace_drawer.setVisible(checked)
        self._refresh_mindmap_url_trace_table()

    def _refresh_mindmap_url_trace_table(self):
        if not hasattr(self, "url_trace_table") or self.url_trace_table is None:
            return
        proj = self._get_active_project_dict()
        node_urls = proj.setdefault("node_urls", {})
        trace_map = proj.setdefault("node_url_trails", {})

        self.url_trace_table.setRowCount(len(self.panes))
        for r, (aid, pane) in enumerate(self.panes.items()):
            is_gemini = pane.platform == "gemini"
            col = QColor("#38bdf8") if is_gemini else QColor("#f97316")

            curr_url = node_urls.get(aid) or (pane.web_view.url().toString() if hasattr(pane, "web_view") else "")
            trail = trace_map.get(aid, [])
            if len(trail) >= 2:
                short_chain = " -> ".join(
                    t["url"].replace("https://", "").replace("claude.ai", "").replace("gemini.google.com", "")
                    for t in trail[-3:]
                )
                last_time = trail[-1].get("time", "")
            elif len(trail) == 1:
                short_chain = f"Initial -> {trail[0]['url'].replace('https://', '')}"
                last_time = trail[0].get("time", "Active")
            else:
                short_chain = "No URL changes yet (on landing page)"
                last_time = "Initial"

            it_name = QTableWidgetItem(pane.account_name)
            it_name.setData(256, aid)
            it_name.setForeground(QBrush(col))

            it_plat = QTableWidgetItem(pane.platform.capitalize())
            it_plat.setForeground(QBrush(col))

            it_curr = QTableWidgetItem(curr_url)
            it_curr.setForeground(QBrush(QColor("#10b981" if ("/chat/" in curr_url or "/app/" in curr_url) else "#f4f4f5")))

            it_trail = QTableWidgetItem(short_chain)
            it_trail.setForeground(QBrush(QColor("#e4e4e7")))

            it_time = QTableWidgetItem(last_time)
            it_time.setForeground(QBrush(QColor("#a1a1aa")))

            self.url_trace_table.setItem(r, 0, it_name)
            self.url_trace_table.setItem(r, 1, it_plat)
            self.url_trace_table.setItem(r, 2, it_curr)
            self.url_trace_table.setItem(r, 3, it_trail)
            self.url_trace_table.setItem(r, 4, it_time)

    def _on_trace_table_double_clicked(self, row: int, _col: int):
        it_name = self.url_trace_table.item(row, 0)
        if it_name:
            self._prompt_and_set_node_url(it_name.data(256))

    def _on_import_chat_url_dialog(self):
        if not self.panes:
            return
        items = [f"{p.account_name} [{p.platform.capitalize()}] ({aid})" for aid, p in self.panes.items()]
        choice, ok = QInputDialog.getItem(
            self, "Select Node to Import Existing Chat URL",
            "Choose which AI pane should load the existing chat URL:", items, 0, False
        )
        if ok and choice:
            aid = choice.rsplit("(", 1)[-1].rstrip(")")
            self._prompt_and_set_node_url(aid)

    def _prompt_and_set_node_url(self, aid: str):
        if aid not in self.panes:
            return
        pane = self.panes[aid]
        curr_url = pane.web_view.url().toString() if hasattr(pane, "web_view") else ""
        new_url, ok = QInputDialog.getText(
            self,
            f"Import / Change Chat URL - {pane.account_name}",
            f"Paste existing {pane.platform.capitalize()} chat URL for {pane.account_name}:",
            text=curr_url
        )
        if ok and new_url.strip():
            pane.navigate_to_url(new_url.strip())

    def _clear_url_trace_history(self):
        proj = self._get_active_project_dict()
        proj["node_url_trails"] = {}
        self._refresh_mindmap_url_trace_table()

    # ==========================================================================
    # Project Save / Export / Open / Close & Task Queue
    # ==========================================================================
    def _on_queue_updated(self, tasks: list):
        self.task_table.update_tasks(tasks)
        if self.workspace_data and self.workspace_data.get("id"):
            self.project_mgr.save_task_history(self.workspace_data["id"], self.scheduler.serialize_tasks())

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

    def _on_move_pane_requested(self, account_id: str, direction: int):
        if account_id not in self.panes:
            return
        pane_keys = list(self.panes.keys())
        idx = pane_keys.index(account_id)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(pane_keys):
            return

        pane_widget = self.panes[account_id]
        self.strip_layout.removeWidget(pane_widget)
        self.strip_layout.insertWidget(new_idx, pane_widget)

        pane_keys[idx], pane_keys[new_idx] = pane_keys[new_idx], pane_keys[idx]
        self.panes = {k: self.panes[k] for k in pane_keys}

        acc_map = {a.get("id"): a for a in self.accounts}
        if all(k in acc_map for k in pane_keys):
            self.accounts = [acc_map[k] for k in pane_keys]
            self.workspace_data["accounts"] = self.accounts

        self.model_monitor_tab.rebuild_node_rows()
        self.file_vault_tab.refresh_targets_and_view()
        self.binary_tree_graph.rebuild_and_layout_graph()

    def _on_pane_url_changed(self, account_id: str, new_url: str):
        if not new_url or "login" in new_url.lower() or "accounts.google.com" in new_url.lower():
            return
        
        # NEVER overwrite a valid active chat session URL with a generic landing URL like claude.ai/new
        lower_u = new_url.lower()
        is_generic_landing = (
            lower_u.endswith("/new") or 
            lower_u.endswith("/app") or 
            lower_u == "https://claude.ai" or 
            lower_u == "https://claude.ai/" or 
            lower_u == "https://gemini.google.com" or 
            lower_u == "https://gemini.google.com/"
        )
        
        proj = self._get_active_project_dict()
        node_urls = proj.setdefault("node_urls", {})
        existing_u = node_urls.get(account_id, "")
        
        if is_generic_landing and existing_u and not existing_u.lower().endswith(("/new", "/app")):
            return  # Ignore generic redirect so active chat URL is preserved!

        node_urls[account_id] = new_url
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

    def _on_pane_url_changed_trace(self, acc_id: str, new_url: str):
        if not new_url:
            return
        proj = self._get_active_project_dict()
        node_urls = proj.setdefault("node_urls", {})
        trace_map = proj.setdefault("node_url_trails", {})

        old_url = node_urls.get(acc_id, "")
        if old_url == new_url:
            return

        node_urls[acc_id] = new_url
        trail = trace_map.setdefault(acc_id, [])
        stamp = datetime.now().strftime("%H:%M:%S")
        if not trail or trail[-1].get("url") != new_url:
            trail.append({"url": new_url, "old_url": old_url or "initial", "time": stamp})
            if len(trail) > 12:
                trail[:] = trail[-12:]

        proj["_is_dirty"] = True
        try:
            self.project_mgr.save_project(proj, force_disk=True)
        except Exception:
            pass
        self._refresh_mindmap_url_trace_table()

    def _snapshot_current_project_state(self):
        proj = self._get_active_project_dict()
        for acc in self.accounts:
            acc_id = acc.get("id")
            if acc_id in self.panes:
                curr_u = self.panes[acc_id].web_view.url().toString()
                if curr_u and "login" not in curr_u.lower() and "accounts.google.com" not in curr_u.lower():
                    acc["current_url"] = curr_u
        proj["accounts"] = self.accounts
        proj["master_node_id"] = self.combo_master.currentData()
        proj["pipeline_sessions"] = self.pipeline_sessions
        proj["task_history"] = self.scheduler.serialize_tasks()

    def _action_save_project(self) -> bool:
        proj = self._get_active_project_dict()
        self._snapshot_current_project_state()
        proj["_is_saved"] = True
        proj["_is_dirty"] = False
        self.project_mgr.save_project(proj, force_disk=True)
        proj_name = proj.get("name", self.project_name)
        self.setWindowTitle(f"Nexus AI Orchestrator - {proj_name} [Saved in Software]")
        QMessageBox.information(self, "Project Saved", f"Project '{proj_name}' has been saved locally in the software.")
        return True

    def _action_save_project_as(self) -> bool:
        proj = self._get_active_project_dict()
        self._snapshot_current_project_state()
        default_name = f"{proj.get('name', 'workspace')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Project Workspace As JSON File", default_name, "JSON Project Files (*.json)"
        )
        if not file_path:
            return False
        if not file_path.lower().endswith(".json"):
            file_path += ".json"
        proj["name"] = os.path.splitext(os.path.basename(file_path))[0]
        self.project_mgr.save_project(proj, force_disk=True, custom_file_path=file_path)
        self.setWindowTitle(f"Nexus AI Orchestrator - {proj['name']} [Exported JSON]")
        return True

    def _action_open_project_json(self):
        if not self._confirm_unsaved_project():
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Saved Project JSON", "", "JSON Project Files (*.json)"
        )
        if not file_path:
            return
        proj = self.project_mgr.load_project_from_file(file_path)
        if not proj:
            QMessageBox.critical(self, "Open Failed", "Could not parse the selected Project JSON file.")
            return
        self.workspace_data = proj
        self._load_initial_workspace()

    def _confirm_unsaved_project(self) -> bool:
        proj = self._get_active_project_dict()
        proj_name = proj.get("name", "Untitled")
        msg = QMessageBox(self)
        msg.setWindowTitle("Save Project Locally in Software?")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(f"Do you want to save project '{proj_name}' locally in Nexus AI Orchestrator before closing?")
        msg.setInformativeText(
            "Clicking 'Save in Software' stores all chat URLs, attached vault files, and pipeline state inside your internal Project Hub."
        )
        btn_save = msg.addButton("Save in Software", QMessageBox.ButtonRole.AcceptRole)
        btn_export = msg.addButton("Export JSON (Save As...)", QMessageBox.ButtonRole.ActionRole)
        btn_discard = msg.addButton("Don't Save", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == btn_save:
            return self._action_save_project()
        elif clicked == btn_export:
            return self._action_save_project_as()
        elif clicked == btn_discard:
            return True
        return False

    def closeEvent(self, event):
        if not self._confirm_unsaved_project():
            event.ignore()
            return
        self._clear_current_panes()
        event.accept()