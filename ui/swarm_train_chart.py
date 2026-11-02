import os
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QRadioButton, QButtonGroup, QCheckBox,
    QScrollArea, QFrame, QComboBox
)


class StageNodeWidget(QFrame):
    force_complete_clicked = pyqtSignal(str)

    def __init__(self, stage_idx: int, account_id: str, account_name: str, assigned_files: list, parent=None):
        super().__init__(parent)
        self.stage_idx = stage_idx
        self.account_id = account_id
        self.account_name = account_name
        self.assigned_files = assigned_files or []
        self.status = "waiting"
        self._setup_ui()
        self.set_status("waiting")

    def _setup_ui(self):
        self.setFixedWidth(230)
        self.setMinimumHeight(155)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.lbl_stage = QLabel(f"STAGE {self.stage_idx}: {self.account_name}")
        self.lbl_stage.setStyleSheet("font-weight: bold; font-size: 12px; color: #f4f4f5; border: none;")

        self.lbl_status = QLabel("STATUS: WAITING")
        self.lbl_status.setStyleSheet("font-size: 10px; font-weight: bold; color: #71717a; border: none;")

        files_title = QLabel("Target Outputs:")
        files_title.setStyleSheet("font-size: 10px; color: #71717a; border: none;")

        layout.addWidget(self.lbl_stage)
        layout.addWidget(self.lbl_status)
        layout.addWidget(files_title)

        self.files_box = QVBoxLayout()
        self.files_box.setSpacing(2)
        if not self.assigned_files:
            lbl = QLabel("- (Dynamic Extraction)")
            lbl.setStyleSheet("color: #71717a; font-family: Consolas; font-size: 10px; border: none;")
            self.files_box.addWidget(lbl)
        else:
            for f in self.assigned_files:
                lbl = QLabel(f"- {f}")
                lbl.setStyleSheet("color: #d4d4d8; font-family: Consolas; font-size: 10px; border: none;")
                self.files_box.addWidget(lbl)

        layout.addLayout(self.files_box)
        layout.addStretch()

        self.btn_force = QPushButton("Force Complete Stage")
        self.btn_force.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_force.setStyleSheet("""
            QPushButton {
                background-color: #27272a; color: #e4e4e7;
                border: 1px solid #52525b; border-radius: 3px;
                padding: 4px 6px; font-size: 10px; font-weight: bold;
            }
            QPushButton:hover { background-color: #3f3f46; color: #ffffff; }
        """)
        self.btn_force.clicked.connect(lambda: self.force_complete_clicked.emit(self.account_id))
        self.btn_force.setVisible(False)
        layout.addWidget(self.btn_force)

    def set_status(self, status: str):
        self.status = status
        if status == "waiting":
            border = "#27272a"
            bg = "#121215"
            badge_color = "#71717a"
            self.btn_force.setVisible(False)
        elif status == "running":
            border = "#a1a1aa"
            bg = "#1c1c21"
            badge_color = "#f4f4f5"
            self.btn_force.setVisible(True)
        elif status == "completed":
            border = "#52525b"
            bg = "#18181b"
            badge_color = "#d4d4d8"
            self.btn_force.setVisible(False)
        else:
            border = "#52525b"
            bg = "#18181b"
            badge_color = "#a1a1aa"
            self.btn_force.setVisible(False)

        self.setStyleSheet(f"""
            StageNodeWidget {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
        """)
        self.lbl_status.setText(f"STATUS: {status.upper()}")
        self.lbl_status.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {badge_color}; border: none;")


class RelayGateWidget(QFrame):
    gate_approved = pyqtSignal(int, dict)

    def __init__(self, gate_index: int, from_account: str, to_account: str, parent=None):
        super().__init__(parent)
        self.gate_index = gate_index
        self.from_account = from_account
        self.to_account = to_account
        self.available_file_paths = {}  # key -> full_path
        self.file_checkboxes = {}       # key -> QCheckBox
        self.is_waiting_approval = False
        self._setup_ui()
        self.set_gate_state("locked")

    def _setup_ui(self):
        self.setFixedWidth(310)
        self.setMinimumHeight(155)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self.lbl_title = QLabel(f"--> RELAY GATE #{self.gate_index + 1} -->")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #d4d4d8; border: none;")
        layout.addWidget(self.lbl_title)

        self.chk_summary = QCheckBox("Inject Short ===SUMMARY===")
        self.chk_summary.setChecked(True)
        self.chk_summary.setStyleSheet("color: #d4d4d8; font-size: 10px; border: none;")
        layout.addWidget(self.chk_summary)

        self.lbl_files_hdr = QLabel("Attach Harvested Files (Cumulative Pool):")
        self.lbl_files_hdr.setStyleSheet("color: #71717a; font-size: 10px; border: none;")
        layout.addWidget(self.lbl_files_hdr)

        self.files_layout = QVBoxLayout()
        self.files_layout.setSpacing(2)
        self.lbl_no_files = QLabel("  (Waiting for Stage harvest...)")
        self.lbl_no_files.setStyleSheet("color: #52525b; font-size: 10px; font-style: italic; border: none;")
        self.files_layout.addWidget(self.lbl_no_files)
        layout.addLayout(self.files_layout)

        layout.addStretch()

        self.btn_approve = QPushButton("Approve && Fire Next Stage")
        self.btn_approve.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_approve.clicked.connect(self._on_approve_clicked)
        layout.addWidget(self.btn_approve)

    def populate_harvested_files(self, file_entries: list):
        """
        file_entries can be:
          - list of dicts: [{"path": full_path, "stage_num": 1, "account_name": "Harivishnu0558", "recommended": True}, ...]
          - or list of raw path strings for backward compatibility.
        """
        while self.files_layout.count():
            item = self.files_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.available_file_paths.clear()
        self.file_checkboxes.clear()

        if not file_entries:
            lbl = QLabel("  No physical files harvested")
            lbl.setStyleSheet("color: #71717a; font-size: 10px; border: none;")
            self.files_layout.addWidget(lbl)
            return

        # Sort so [Recommended] files appear at the top of the gate list
        normalized = []
        for idx, entry in enumerate(file_entries):
            if isinstance(entry, dict):
                normalized.append(entry)
            else:
                normalized.append({
                    "path": str(entry),
                    "stage_num": self.gate_index + 1,
                    "account_name": "Upstream",
                    "recommended": True
                })

        normalized.sort(key=lambda e: (not e.get("recommended", False), e.get("stage_num", 1)))

        for idx, item_info in enumerate(normalized):
            full_path = item_info.get("path", "")
            fname = os.path.basename(full_path)
            stage_num = item_info.get("stage_num", 1)
            acc_name = item_info.get("account_name", "Worker")
            is_rec = item_info.get("recommended", False)

            rec_tag = " [Recommended]" if is_rec else ""
            display_label = f"{fname} (Stage {stage_num}: {acc_name}){rec_tag}"

            key = f"{idx}_{fname}"
            self.available_file_paths[key] = full_path
            chk = QCheckBox(display_label)
            chk.setChecked(bool(is_rec))
            text_color = "#f4f4f5" if is_rec else "#a1a1aa"
            chk.setStyleSheet(f"color: {text_color}; font-family: Consolas; font-size: 10px; border: none;")
            self.files_layout.addWidget(chk)
            self.file_checkboxes[key] = chk

    def set_gate_state(self, state: str):
        if state == "locked":
            self.is_waiting_approval = False
            self.btn_approve.setEnabled(False)
            self.btn_approve.setText("Waiting for Prev Stage...")
            self.setStyleSheet("""
                RelayGateWidget {
                    background-color: #121215;
                    border: 1px dashed #27272a;
                    border-radius: 6px;
                }
            """)
            self.btn_approve.setStyleSheet("""
                QPushButton {
                    background-color: #18181b; color: #52525b;
                    border: 1px solid #27272a; border-radius: 4px;
                    padding: 4px; font-size: 10px; font-weight: bold;
                }
            """)
        elif state == "awaiting_approval":
            self.is_waiting_approval = True
            self.btn_approve.setEnabled(True)
            self.btn_approve.setText("Approve && Fire Next Stage")
            self.setStyleSheet("""
                RelayGateWidget {
                    background-color: #1c1c21;
                    border: 1px solid #a1a1aa;
                    border-radius: 6px;
                }
            """)
            self.btn_approve.setStyleSheet("""
                QPushButton {
                    background-color: #3f3f46; color: #ffffff;
                    border: 1px solid #71717a; border-radius: 4px;
                    padding: 5px; font-size: 10px; font-weight: bold;
                }
                QPushButton:hover { background-color: #52525b; color: #ffffff; }
            """)
        elif state == "relayed":
            self.is_waiting_approval = False
            self.btn_approve.setEnabled(False)
            self.btn_approve.setText("Relay Dispatched")
            self.setStyleSheet("""
                RelayGateWidget {
                    background-color: #141417;
                    border: 1px solid #3f3f46;
                    border-radius: 6px;
                }
            """)
            self.btn_approve.setStyleSheet("""
                QPushButton {
                    background-color: #27272a; color: #a1a1aa;
                    border: 1px solid #3f3f46; border-radius: 4px;
                    padding: 4px; font-size: 10px; font-weight: bold;
                }
            """)

    def get_selected_payload(self) -> dict:
        selected_files = [
            self.available_file_paths[k]
            for k, chk in self.file_checkboxes.items()
            if chk.isChecked() and k in self.available_file_paths
        ]
        return {
            "send_summary": self.chk_summary.isChecked(),
            "files": selected_files
        }

    def _on_approve_clicked(self):
        payload = self.get_selected_payload()
        self.set_gate_state("relayed")
        self.gate_approved.emit(self.gate_index, payload)


class SwarmTrainChartWidget(QWidget):
    relay_gate_approved = pyqtSignal(int, dict)
    execution_mode_changed = pyqtSignal(str)
    approval_mode_changed = pyqtSignal(bool)
    force_stage_complete = pyqtSignal(str)
    session_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stage_widgets = {}
        self.gate_widgets = []
        self.final_card = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.ctrl_bar = QFrame()
        self.ctrl_bar.setFixedHeight(36)
        self.ctrl_bar.setStyleSheet("""
            QFrame {
                background-color: #141417;
                border-bottom: 1px solid #27272a;
            }
            QLabel {
                color: #d4d4d8;
                font-size: 11px;
                font-weight: bold;
                border: none;
            }
            QComboBox {
                background-color: #09090b;
                color: #f4f4f5;
                border: 1px solid #3f3f46;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QRadioButton {
                color: #a1a1aa;
                font-size: 11px;
                font-weight: bold;
                spacing: 5px;
            }
            QRadioButton:checked {
                color: #f4f4f5;
            }
        """)
        ctrl_layout = QHBoxLayout(self.ctrl_bar)
        ctrl_layout.setContentsMargins(10, 4, 10, 4)
        ctrl_layout.setSpacing(10)

        ctrl_layout.addWidget(QLabel("Session History:"))
        self.combo_sessions = QComboBox()
        self.combo_sessions.setFixedWidth(250)
        self.combo_sessions.currentIndexChanged.connect(self._on_session_combo_changed)
        ctrl_layout.addWidget(self.combo_sessions)

        sep0 = QLabel("|")
        sep0.setStyleSheet("color: #3f3f46;")
        ctrl_layout.addWidget(sep0)

        ctrl_layout.addWidget(QLabel("Strategy:"))
        self.mode_group = QButtonGroup(self)
        self.rb_pipeline = QRadioButton("Sequential Pipeline (DAG)")
        self.rb_parallel = QRadioButton("Instant Parallel")
        self.rb_pipeline.setChecked(True)
        self.mode_group.addButton(self.rb_pipeline)
        self.mode_group.addButton(self.rb_parallel)
        self.rb_pipeline.toggled.connect(self._on_mode_toggled)
        ctrl_layout.addWidget(self.rb_pipeline)
        ctrl_layout.addWidget(self.rb_parallel)

        sep = QLabel("|")
        sep.setStyleSheet("color: #3f3f46;")
        ctrl_layout.addWidget(sep)

        ctrl_layout.addWidget(QLabel("Gate Relay:"))
        self.approval_group = QButtonGroup(self)
        self.rb_pause = QRadioButton("Pause for Approval")
        self.rb_auto = QRadioButton("Auto-Relay")
        self.rb_pause.setChecked(True)
        self.approval_group.addButton(self.rb_pause)
        self.approval_group.addButton(self.rb_auto)
        self.rb_pause.toggled.connect(self._on_approval_toggled)
        ctrl_layout.addWidget(self.rb_pause)
        ctrl_layout.addWidget(self.rb_auto)

        ctrl_layout.addStretch()

        self.lbl_telemetry = QLabel("Pipeline Idle")
        self.lbl_telemetry.setStyleSheet("color: #d4d4d8; font-size: 11px; font-weight: bold;")
        ctrl_layout.addWidget(self.lbl_telemetry)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(150)
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #09090b;
                border: 1px solid #3f3f46;
                border-radius: 3px;
                text-align: center;
                color: #f4f4f5;
                font-size: 9px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #52525b;
                border-radius: 2px;
            }
        """)
        ctrl_layout.addWidget(self.progress_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll.setStyleSheet("""
            QScrollArea {
                background-color: #09090b;
                border: none;
            }
            QScrollBar:horizontal {
                background: #141417;
                height: 14px;
                border-top: 1px solid #27272a;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #52525b;
                min-width: 60px;
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

        self.canvas = QWidget()
        self.canvas.setStyleSheet("background-color: #09090b;")
        self.train_layout = QHBoxLayout(self.canvas)
        self.train_layout.setContentsMargins(16, 10, 16, 10)
        self.train_layout.setSpacing(14)
        self.train_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.scroll.setWidget(self.canvas)

        layout.addWidget(self.ctrl_bar)
        layout.addWidget(self.scroll, stretch=1)

    def _on_session_combo_changed(self, idx: int):
        if idx >= 0:
            self.session_selected.emit(idx)

    def set_session_list(self, labels: list, current_index: int):
        self.combo_sessions.blockSignals(True)
        self.combo_sessions.clear()
        for lbl in labels:
            self.combo_sessions.addItem(lbl)
        if 0 <= current_index < len(labels):
            self.combo_sessions.setCurrentIndex(current_index)
        self.combo_sessions.blockSignals(False)

    def _auto_scroll_to_widget(self, widget: QWidget):
        if widget:
            QTimer.singleShot(50, lambda: self.scroll.ensureWidgetVisible(widget, 80, 0))

    def _on_mode_toggled(self):
        mode = "pipeline" if self.rb_pipeline.isChecked() else "parallel"
        self.execution_mode_changed.emit(mode)

    def _on_approval_toggled(self):
        pause_required = self.rb_pause.isChecked()
        self.approval_mode_changed.emit(pause_required)
        if not pause_required:
            for gate in self.gate_widgets:
                if gate.is_waiting_approval:
                    gate._on_approve_clicked()

    def is_pause_for_approval(self) -> bool:
        return self.rb_pause.isChecked()

    def get_execution_mode(self) -> str:
        return "pipeline" if self.rb_pipeline.isChecked() else "parallel"

    def build_train_pipeline(
        self,
        worker_accounts: list,
        file_assignments: dict = None,
        stage_statuses: dict = None,
        gate_states: list = None
    ):
        while self.train_layout.count():
            item = self.train_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.stage_widgets.clear()
        self.gate_widgets.clear()
        file_assignments = file_assignments or {}
        stage_statuses = stage_statuses or {}
        gate_states = gate_states or []

        for idx, acc in enumerate(worker_accounts):
            acc_id = acc["id"]
            files = file_assignments.get(acc_id, [])
            stage_node = StageNodeWidget(idx + 1, acc_id, acc["account_name"], files)
            stage_node.set_status(stage_statuses.get(acc_id, "waiting"))
            stage_node.force_complete_clicked.connect(self.force_stage_complete.emit)
            self.train_layout.addWidget(stage_node)
            self.stage_widgets[acc_id] = stage_node

            if idx < len(worker_accounts) - 1:
                next_acc = worker_accounts[idx + 1]
                gate = RelayGateWidget(idx, acc_id, next_acc["id"])
                if idx < len(gate_states):
                    g_info = gate_states[idx]
                    gate.populate_harvested_files(g_info.get("files", []))
                    gate.set_gate_state(g_info.get("state", "locked"))
                gate.gate_approved.connect(self._on_gate_approved_internal)
                self.train_layout.addWidget(gate)
                self.gate_widgets.append(gate)

        self.final_card = QFrame()
        self.final_card.setFixedWidth(185)
        self.final_card.setMinimumHeight(155)
        self.final_card.setStyleSheet("""
            QFrame {
                background-color: #141417;
                border: 1px solid #3f3f46;
                border-radius: 6px;
            }
            QLabel { border: none; color: #d4d4d8; }
        """)
        fl = QVBoxLayout(self.final_card)
        lbl_f1 = QLabel("FINAL STAGE")
        lbl_f1.setStyleSheet("font-weight: bold; font-size: 12px; color: #f4f4f5;")
        lbl_f2 = QLabel("Assemble Project Map\n& Build Archive (.zip)")
        lbl_f2.setWordWrap(True)
        lbl_f2.setStyleSheet("font-size: 10px; color: #a1a1aa;")
        fl.addWidget(lbl_f1)
        fl.addWidget(lbl_f2)
        fl.addStretch()
        self.train_layout.addWidget(self.final_card)
        self.train_layout.addStretch()

        self.set_progress(0, "Blueprint Loaded â€” Ready")
        if worker_accounts:
            first_id = worker_accounts[0]["id"]
            self._auto_scroll_to_widget(self.stage_widgets.get(first_id))

    def _on_gate_approved_internal(self, gate_index: int, payload: dict):
        self.relay_gate_approved.emit(gate_index, payload)
        if 0 <= gate_index < len(self.gate_widgets):
            next_acc_id = self.gate_widgets[gate_index].to_account
            if next_acc_id in self.stage_widgets:
                self._auto_scroll_to_widget(self.stage_widgets[next_acc_id])

    def set_stage_status(self, account_id: str, status: str):
        if account_id in self.stage_widgets:
            widget = self.stage_widgets[account_id]
            widget.set_status(status)
            if status in ("running", "completed"):
                self._auto_scroll_to_widget(widget)

    def activate_gate(self, gate_index: int, file_entries: list):
        if 0 <= gate_index < len(self.gate_widgets):
            gate = self.gate_widgets[gate_index]
            gate.populate_harvested_files(file_entries)
            if self.is_pause_for_approval():
                gate.set_gate_state("awaiting_approval")
                self._auto_scroll_to_widget(gate)
                self.set_progress(
                    int(((gate_index + 1) / (len(self.gate_widgets) + 1)) * 100),
                    f"Paused at Gate #{gate_index + 1} â€” Select files & click Approve"
                )
            else:
                gate._on_approve_clicked()

    def set_progress(self, percent: int, message: str):
        self.progress_bar.setValue(max(0, min(100, percent)))
        self.lbl_telemetry.setText(message)
        if percent >= 100 and self.final_card:
            self._auto_scroll_to_widget(self.final_card)
