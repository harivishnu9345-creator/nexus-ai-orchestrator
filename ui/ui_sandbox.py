import sys
from PyQt6.QtCore import Qt, QTime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QStackedWidget, QPushButton, QLabel, QFrame, QLineEdit,
    QComboBox, QSplitter, QTabWidget, QMenuBar, QScrollArea, QSizePolicy
)

from ui.project_hub import ProjectHubDialog
from ui.onboarding_dialog import OnboardingDialog
from ui.scheduler_dialog import TaskSchedulerDialog
from ui.toast_notification import RateLimitToast
from ui.task_table import TaskTable
from ui.swarm_mind_map import SwarmMindMapWidget
from ui.swarm_train_chart import SwarmTrainChartWidget


MOCK_ACCOUNTS = [
    {"id": "acc_0", "account_name": "Harivishnu0558", "platform": "claude", "email": "harivishnu0558@gmail.com"},
    {"id": "acc_1", "account_name": "Yasnax678", "platform": "claude", "email": "yasnax678@gmail.com"},
    {"id": "acc_2", "account_name": "Batmanrock1357", "platform": "claude", "email": "batmanrock1357@gmail.com"},
    {"id": "acc_3", "account_name": "Lgostv94", "platform": "claude", "email": "lgostv94@gmail.com"},
    {"id": "acc_4", "account_name": "WorkerNode5", "platform": "claude", "email": "worker5@gmail.com"},
]

MOCK_PROJECTS = [
    {"name": "New Swarm Workspace", "accounts": MOCK_ACCOUNTS},
    {"name": "RupeeTrace_Engine", "accounts": MOCK_ACCOUNTS[:3]},
]


class MockWebPaneColumn(QFrame):
    """Exact side-by-side vertical browser column matching Screenshot 3 (image_539ad6.png)."""
    def __init__(self, account_name: str, provider: str, status: str = "ready"):
        super().__init__()
        self.setObjectName("PaneFrame")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setFixedWidth(450)
        self.setMinimumHeight(340)
        self.setStyleSheet("""
            QFrame#PaneFrame {
                background-color: #09090b;
                border: 1px solid #27272a;
                border-radius: 2px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(34)
        header.setStyleSheet("""
            QFrame { background-color: #18181b; border-bottom: 1px solid #27272a; }
            QLabel { color: #f4f4f5; border: none; font-size: 12px; font-weight: bold; }
            QPushButton { background-color: #27272a; color: #e4e4e7; border: 1px solid #3f3f46; padding: 2px 7px; border-radius: 2px; font-weight: bold; }
            QPushButton:hover { background-color: #3f3f46; color: #ffffff; }
        """)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(8, 4, 8, 4)
        hl.setSpacing(6)

        colors = {"ready": "#10b981", "running": "#f59e0b", "rate_limited": "#ef4444"}
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {colors.get(status, '#10b981')}; font-size: 13px;")
        title = QLabel(f"{account_name} [{provider.capitalize()}]")
        url = QLabel("claude.ai/new")
        url.setStyleSheet("background-color: #09090b; color: #a1a1aa; font-family: Consolas; font-size: 10px; padding: 2px 6px; border: 1px solid #27272a;")

        hl.addWidget(dot)
        hl.addWidget(title)
        hl.addWidget(url, stretch=1)
        hl.addWidget(QPushButton("-"))
        hl.addWidget(QPushButton("+"))
        hl.addWidget(QPushButton("↻"))

        body = QLabel(f"Afternoon, hari\n\n[{account_name}]")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setStyleSheet("color: #e4e4e7; font-size: 20px; font-family: Georgia, serif; background-color: #09090b;")

        layout.addWidget(header)
        layout.addWidget(body, stretch=1)


class UISandboxRunner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nexus AI Orchestrator — UI Component Sandbox")
        self.resize(1640, 940)
        self._apply_theme()
        self._build_sandbox()

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #09090b; color: #f4f4f5; font-family: 'Ubuntu', 'Segoe UI', sans-serif; }
            QListWidget { background-color: #141417; border: 1px solid #27272a; border-radius: 4px; padding: 6px; font-size: 12px; outline: none; }
            QListWidget::item { padding: 10px; border-bottom: 1px solid #1f1f23; color: #d4d4d8; font-weight: bold; }
            QListWidget::item:selected { background-color: #2563eb; color: #ffffff; border-radius: 3px; }
            QPushButton { background-color: #1f1f23; color: #e4e4e7; border: 1px solid #3f3f46; border-radius: 4px; padding: 6px 12px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #27272a; color: #ffffff; }
        """)

    def _build_sandbox(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Left Test Harness Drawer (Only exists in ui_sandbox.py)
        nav_panel = QVBoxLayout()
        lbl_nav = QLabel("SANDBOX TEST SELECTOR")
        lbl_nav.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: bold; padding: 4px;")
        nav_panel.addWidget(lbl_nav)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(230)
        self.sidebar.currentRowChanged.connect(lambda idx: self.stack.setCurrentIndex(idx))
        nav_panel.addWidget(self.sidebar, stretch=1)

        lbl_popups = QLabel("DIALOG POPUP TESTERS")
        lbl_popups.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: bold; padding-top: 8px;")
        nav_panel.addWidget(lbl_popups)

        btn_hub = QPushButton("1. Open ProjectHubDialog")
        btn_hub.clicked.connect(lambda: ProjectHubDialog(MOCK_PROJECTS, self).exec())
        nav_panel.addWidget(btn_hub)

        btn_onboard = QPushButton("2. Open OnboardingDialog")
        btn_onboard.clicked.connect(lambda: OnboardingDialog(self).exec())
        nav_panel.addWidget(btn_onboard)

        btn_sched = QPushButton("3. Open TaskSchedulerDialog")
        btn_sched.clicked.connect(lambda: TaskSchedulerDialog(MOCK_ACCOUNTS, self).exec())
        nav_panel.addWidget(btn_sched)

        layout.addLayout(nav_panel)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget { border: 1px solid #27272a; background-color: #09090b; }")
        layout.addWidget(self.stack, stretch=1)

        self._add_full_main_window_preview()
        self._add_task_table_preview()
        self._add_mind_map_preview()
        self._add_train_chart_preview()
        self._add_toast_preview()

        self.sidebar.setCurrentRow(0)

    def _add_page(self, title: str, widget: QWidget):
        self.sidebar.addItem(title)
        self.stack.addWidget(widget)

    def _add_full_main_window_preview(self):
        page = QWidget()
        vbox = QVBoxLayout(page)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # 1. Native Top Menu Bar matching Screenshot 3 (File | Swarm | Scheduler | View)
        menu_bar = QMenuBar()
        menu_bar.setStyleSheet("""
            QMenuBar { background-color: #141417; color: #e4e4e7; border-bottom: 1px solid #27272a; font-size: 12px; font-weight: bold; padding: 2px 6px; }
            QMenuBar::item { padding: 4px 10px; }
            QMenuBar::item:selected { background-color: #27272a; }
            QMenu { background-color: #141417; color: #f4f4f5; border: 1px solid #27272a; }
            QMenu::item:selected { background-color: #2563eb; }
        """)
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("Switch Workspace (Project Hub)...", lambda: ProjectHubDialog(MOCK_PROJECTS, self).exec())
        file_menu.addAction("New Swarm Workspace...", lambda: OnboardingDialog(self).exec())
        file_menu.addSeparator()
        file_menu.addAction("Exit")

        swarm_menu = menu_bar.addMenu("Swarm")
        swarm_menu.addAction("1. Send Master Directive")
        swarm_menu.addAction("2. Extract & Delegate Pipeline")
        swarm_menu.addAction("3. Harvest & Build ZIP")
        swarm_menu.addAction("Open Build in VS Code")

        sched_menu = menu_bar.addMenu("Scheduler")
        sched_menu.addAction("Schedule Task...", lambda: TaskSchedulerDialog(MOCK_ACCOUNTS, self).exec())
        sched_menu.addAction("Clear Completed Tasks")

        view_menu = menu_bar.addMenu("View")
        view_menu.addAction("Reload All Nodes")
        vbox.addWidget(menu_bar)

        # 2. Single Unified Command & Swarm Bar (Matching Screenshot 3)
        cmd_bar = QFrame()
        cmd_bar.setFixedHeight(48)
        cmd_bar.setStyleSheet("""
            QFrame { background-color: #141417; border-bottom: 1px solid #27272a; }
            QLabel { color: #e4e4e7; font-size: 12px; font-weight: bold; border: none; }
            QLineEdit, QComboBox { background-color: #09090b; color: #f4f4f5; border: 1px solid #27272a; border-radius: 3px; padding: 5px 8px; font-size: 12px; }
        """)
        cl = QHBoxLayout(cmd_bar)
        cl.setContentsMargins(10, 6, 10, 6)
        cl.setSpacing(8)

        cl.addWidget(QLabel("Master / Target Node:"))
        combo = QComboBox()
        for acc in MOCK_ACCOUNTS:
            combo.addItem(f"{acc['account_name']} (Claude)", acc["id"])
        combo.addItem("Broadcast to All Active Nodes", "all")
        combo.setFixedWidth(180)
        cl.addWidget(combo)

        inp = QLineEdit()
        inp.setPlaceholderText("Enter directive or prompt payload...")
        cl.addWidget(inp, stretch=1)

        cl.addWidget(QPushButton("Attach File..."))

        btn_sched = QPushButton("Schedule...")
        btn_sched.clicked.connect(lambda: TaskSchedulerDialog(MOCK_ACCOUNTS, self).exec())
        cl.addWidget(btn_sched)

        btn_send = QPushButton("Direct Send")
        btn_send.setStyleSheet("background-color: #2563eb; color: #ffffff; border: 1px solid #3b82f6;")
        cl.addWidget(btn_send)

        b1 = QPushButton("1. Send Master Directive")
        b1.setStyleSheet("background-color: #6d28d9; color: #ffffff; border: 1px solid #8b5cf6;")
        b2 = QPushButton("2. Extract && Delegate")
        b2.setStyleSheet("background-color: #059669; color: #ffffff; border: 1px solid #10b981;")
        b3 = QPushButton("3. Harvest && Build ZIP")
        b3.setStyleSheet("background-color: #27272a; color: #e4e4e7; border: 1px solid #52525b;")

        cl.addWidget(b1)
        cl.addWidget(b2)
        cl.addWidget(b3)
        vbox.addWidget(cmd_bar)

        # 3. Vertical Splitter: Top = Single-Row Horizontal Browser Strip, Bottom = Dock
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background-color: #27272a; height: 3px; }")

        # Single-Row Horizontal Browser Strip with Always-Visible Grey Scrollbar (Like Screenshot 3)
        h_scroll = QScrollArea()
        h_scroll.setWidgetResizable(True)
        h_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        h_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        h_scroll.setStyleSheet("""
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

        strip_container = QWidget()
        strip_container.setStyleSheet("background-color: #09090b;")
        strip_layout = QHBoxLayout(strip_container)
        strip_layout.setContentsMargins(6, 6, 6, 6)
        strip_layout.setSpacing(8)
        strip_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        for idx, acc in enumerate(MOCK_ACCOUNTS):
            st = "running" if idx == 1 else "ready"
            strip_layout.addWidget(MockWebPaneColumn(acc["account_name"], acc["platform"], st))

        h_scroll.setWidget(strip_container)
        splitter.addWidget(h_scroll)

        # 4. Bottom Dock Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border-top: 1px solid #27272a; background-color: #09090b; }
            QTabBar::tab { background-color: #141417; color: #a1a1aa; border: 1px solid #27272a; padding: 6px 16px; font-size: 11px; font-weight: bold; }
            QTabBar::tab:selected { background-color: #09090b; color: #f4f4f5; border-top: 2px solid #71717a; }
        """)
        t_table = TaskTable()
        t_table.update_tasks([
            {"account_id": "acc_0", "account_name": "Harivishnu0558", "platform": "Claude", "status": "success", "prompt_text": "Generate system architecture blueprint", "target_time": QTime.currentTime()},
            {"account_id": "acc_1", "account_name": "Yasnax678", "platform": "Claude", "status": "running", "prompt_text": "Build UI components in Carbon Black theme", "target_time": QTime.currentTime()},
            {"account_id": "acc_2", "account_name": "Batmanrock1357", "platform": "Claude", "status": "held_for_gate", "prompt_text": "Implement backend API routes", "target_time": QTime.currentTime(), "stage_index": 1},
        ])
        t_mind = SwarmMindMapWidget()
        t_mind.build_mind_map(MOCK_ACCOUNTS[0], MOCK_ACCOUNTS[1:], {
            "acc_1": ["ui/main_window.py", "ui/theme.css"],
            "acc_2": ["core/api.py", "main.py"],
            "acc_3": ["core/db.py"],
            "acc_4": ["tests/test_suite.py"]
        })

        t_train = SwarmTrainChartWidget()
        t_train.build_train_pipeline(MOCK_ACCOUNTS[1:], {
            "acc_1": ["ui/main_window.py"],
            "acc_2": ["core/api.py"],
            "acc_3": ["core/db.py"],
            "acc_4": ["tests/test_suite.py"]
        })
        t_train.set_stage_status("acc_1", "completed")
        t_train.activate_gate(0, ["C:/mock_build/ui/main_window.py", "C:/mock_build/ui/theme.css"])

        # Interactive simulation inside Sandbox: approving a gate advances & auto-scrolls!
        def _sim_gate_advance(gate_idx, _payload):
            workers = MOCK_ACCOUNTS[1:]
            if gate_idx + 1 < len(workers):
                next_id = workers[gate_idx + 1]["id"]
                t_train.set_stage_status(next_id, "running")

        def _sim_force_complete(acc_id):
            workers = MOCK_ACCOUNTS[1:]
            t_train.set_stage_status(acc_id, "completed")
            for idx, w in enumerate(workers):
                if w["id"] == acc_id:
                    if idx < len(workers) - 1:
                        t_train.activate_gate(idx, [f"C:/mock_build/stage_{idx+1}_output.py"])
                    else:
                        t_train.set_progress(100, "Pipeline Complete — ZIP Built")

        t_train.relay_gate_approved.connect(_sim_gate_advance)
        t_train.force_stage_complete.connect(_sim_force_complete)

        tabs.addTab(t_table, "System Task Queue & Execution Log")
        tabs.addTab(t_mind, "Task Assignment Mind-Map")
        tabs.addTab(t_train, "Execution Flow & File Relay")
        splitter.addWidget(tabs)
        splitter.setSizes([560, 250])
        vbox.addWidget(splitter, stretch=1)

        # 5. Bottom Status Bar matching Screenshot 3
        status_bar = QFrame()
        status_bar.setFixedHeight(24)
        status_bar.setStyleSheet("background-color: #141417; border-top: 1px solid #27272a;")
        sbl = QHBoxLayout(status_bar)
        sbl.setContentsMargins(10, 2, 10, 2)
        lbl_status = QLabel(
            f"System Ready | Workspace: New Swarm Workspace | Active Nodes: {len(MOCK_ACCOUNTS)} (Horizontal Scroll Enabled) | Turnstile Poll: 2000ms"
        )
        lbl_status.setStyleSheet("color: #a1a1aa; font-size: 11px; border: none;")
        sbl.addWidget(lbl_status)
        vbox.addWidget(status_bar)

        self._add_page("1. MainWindow (Horizontal Row)", page)

    def _add_task_table_preview(self):
        w = TaskTable()
        w.update_tasks([
            {"account_id": "acc_0", "account_name": "Harivishnu0558", "platform": "claude", "status": "success", "prompt_text": "Master blueprint generated", "target_time": QTime.currentTime()},
            {"account_id": "acc_1", "account_name": "Yasnax678", "platform": "claude", "status": "running", "prompt_text": "Generating frontend components", "file_paths": ["spec.md"], "target_time": QTime.currentTime()},
            {"account_id": "acc_2", "account_name": "Batmanrock1357", "platform": "claude", "status": "held_for_gate", "prompt_text": "Waiting for Stage 1 relay files", "target_time": QTime.currentTime(), "stage_index": 1},
            {"account_id": "acc_3", "account_name": "Lgostv94", "platform": "claude", "status": "rate_limited", "prompt_text": "Write unit tests", "cooldown_time": "04:30 PM", "target_time": QTime.currentTime()},
        ])
        self._add_page("2. TaskTable (All States)", w)

    def _add_mind_map_preview(self):
        w = SwarmMindMapWidget()
        w.build_mind_map(
            MOCK_ACCOUNTS[0],
            MOCK_ACCOUNTS[1:],
            {
                "acc_1": ["src/App.tsx", "src/components/Sidebar.tsx"],
                "acc_2": ["server/index.py", "server/routes.py"],
                "acc_3": ["core/db.py"],
                "acc_4": ["tests/test_all.py"]
            }
        )
        w.update_node_status("acc_1", "active")
        self._add_page("3. SwarmMindMapWidget", w)

    def _add_train_chart_preview(self):
        w = SwarmTrainChartWidget()
        w.build_train_pipeline(
            MOCK_ACCOUNTS[1:],
            {
                "acc_1": ["src/App.tsx", "src/styles.css"],
                "acc_2": ["server/index.py"],
                "acc_3": ["core/db.py"],
                "acc_4": ["tests/test_all.py"]
            }
        )
        w.set_stage_status("acc_1", "completed")
        w.activate_gate(0, ["C:/build/src/App.tsx", "C:/build/src/styles.css"])
        self._add_page("4. SwarmTrainChart (Auto-Scroll)", w)

    def _add_toast_preview(self):
        holder = QWidget()
        l = QVBoxLayout(holder)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toast = RateLimitToast("acc_1", "Yasnax678", "claude", "04:15 PM", holder)
        l.addWidget(toast)
        self._add_page("5. RateLimitToast Card", holder)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = UISandboxRunner()
    win.show()
    sys.exit(app.exec())