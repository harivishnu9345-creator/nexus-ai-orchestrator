import os
import re
from datetime import datetime
from typing import Dict, List, Callable
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QComboBox, QLineEdit, QFrame, QAbstractItemView, QMessageBox
)

from core.dom_scraper import DOMScraper

IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".idea", ".vscode"}
CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".md",
    ".txt", ".c", ".cpp", ".h", ".hpp", ".java", ".kt", ".rs", ".go", ".sql", ".sh", ".ps1", ".yaml", ".yml"
}


class ProjectFileVaultTab(QWidget):
    """Project-level File & Folder Vault with Strict AI File-Request Detection & Live Harvest Cache."""
    recommendations_updated = pyqtSignal(list)
    explicit_file_request_detected = pyqtSignal(str, str, str, str)  # (requester_id, requester_name, file_name, file_path)

    def __init__(self, injector, get_panes_fn: Callable, get_project_fn: Callable, save_project_fn: Callable, parent=None):
        super().__init__(parent)
        self.injector = injector
        self.get_panes = get_panes_fn
        self.get_project = get_project_fn
        self.save_project = save_project_fn
        self._setup_ui()

        self.request_scan_timer = QTimer(self)
        self.request_scan_timer.timeout.connect(self.scan_chats_for_file_requests)
        self.request_scan_timer.start(4000)

    def _setup_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #09090b; color: #f4f4f5; }
            QLabel { color: #e4e4e7; font-size: 11px; font-weight: bold; }
            QPushButton {
                background-color: #1f1f23; color: #e4e4e7; border: 1px solid #3f3f46;
                border-radius: 3px; padding: 5px 10px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #27272a; color: #ffffff; }
            QPushButton#OrangeBtn { background-color: #ea580c; color: #ffffff; border: 1px solid #f97316; }
            QPushButton#OrangeBtn:hover { background-color: #c2410c; }
            QPushButton#BlueBtn { background-color: #2563eb; color: #ffffff; border: 1px solid #3b82f6; }
            QPushButton#BlueBtn:hover { background-color: #1d4ed8; }
            QPushButton#PurpleBtn { background-color: #7c3aed; color: #ffffff; border: 1px solid #8b5cf6; }
            QPushButton#PurpleBtn:hover { background-color: #6d28d9; }
            QPushButton#GreenBtn { background-color: #059669; color: #ffffff; border: 1px solid #10b981; }
            QPushButton#GreenBtn:hover { background-color: #047857; }
            QLineEdit, QComboBox {
                background-color: #141417; color: #f4f4f5; border: 1px solid #3f3f46;
                border-radius: 3px; padding: 4px 8px; font-size: 11px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #141417; border: 1px solid #27272a; border-radius: 4px;")
        tl = QHBoxLayout(top_bar)
        tl.setContentsMargins(8, 6, 8, 6)
        tl.setSpacing(6)

        btn_add_files = QPushButton("+ Attach Files from Computer...")
        btn_add_files.clicked.connect(self._on_attach_files)

        btn_add_folder = QPushButton("\U0001f4c1 + Attach Folder from Computer...")
        btn_add_folder.clicked.connect(self._on_attach_folder)

        btn_select_all = QPushButton("Toggle All [\u2713]")
        btn_select_all.clicked.connect(self._toggle_all_checks)

        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self._remove_selected_files)

        btn_clear_reqs = QPushButton("Reset Request Flags")
        btn_clear_reqs.clicked.connect(self._clear_false_request_flags)

        btn_announce = QPushButton("\U0001f4e2 Prompt Master: Ask Which Nodes Need Which Vault Files")
        btn_announce.setObjectName("PurpleBtn")
        btn_announce.clicked.connect(self._prompt_ai_for_file_routing)

        btn_fulfill = QPushButton("\u26a1 Upload Explicitly Requested Files Only")
        btn_fulfill.setObjectName("GreenBtn")
        btn_fulfill.clicked.connect(self.upload_all_recommended_to_requesting_chats)

        tl.addWidget(btn_add_files)
        tl.addWidget(btn_add_folder)
        tl.addWidget(btn_select_all)
        tl.addWidget(btn_remove)
        tl.addWidget(btn_clear_reqs)
        tl.addWidget(btn_announce)
        tl.addWidget(btn_fulfill)
        layout.addWidget(top_bar)

        dispatch_bar = QFrame()
        dispatch_bar.setStyleSheet("background-color: #141417; border: 1px solid #27272a; border-radius: 4px;")
        dl = QHBoxLayout(dispatch_bar)
        dl.setContentsMargins(8, 6, 8, 6)
        dl.setSpacing(6)

        self.lbl_folders = QLabel("Attached Folders: None")
        self.lbl_folders.setStyleSheet("color: #f4f4f5; font-weight: bold; border: none;")
        dl.addWidget(self.lbl_folders)
        dl.addSpacing(8)

        dl.addWidget(QLabel("Target Chat(s):"))
        self.combo_target = QComboBox()
        self.combo_target.setFixedWidth(210)
        dl.addWidget(self.combo_target)

        self.input_note = QLineEdit()
        self.input_note.setPlaceholderText("Optional Accompanying Prompt (leave blank to only paste files)...")
        dl.addWidget(self.input_note, stretch=1)

        btn_send_master = QPushButton("\U0001f680 Paste Checked -> Master Architect")
        btn_send_master.setObjectName("OrangeBtn")
        btn_send_master.clicked.connect(self._paste_to_master)

        btn_send_target = QPushButton("\U0001f4ce Paste Checked -> Selected Target(s)")
        btn_send_target.setObjectName("BlueBtn")
        btn_send_target.clicked.connect(self._paste_to_selected_target)

        dl.addWidget(btn_send_master)
        dl.addWidget(btn_send_target)
        layout.addWidget(dispatch_bar)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Select [\u2713]", "File Name", "Full Disk Address", "Source / Producer",
            "Used In History (Nodes & Time)", "Explicit Request / Relay Status"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #09090b; alternate-background-color: #121215;
                color: #f4f4f5; gridline-color: #27272a; border: 1px solid #27272a; font-size: 11px;
            }
            QHeaderView::section {
                background-color: #18181b; color: #a1a1aa; padding: 5px;
                border: none; border-right: 1px solid #27272a; border-bottom: 1px solid #27272a;
                font-weight: bold; font-size: 11px;
            }
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 330)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 200)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, stretch=1)

    def refresh_targets_and_view(self, master_id: str = None):
        self.combo_target.clear()
        self.combo_target.addItem("All Active Nodes (Collision-Free Queue)", "all")
        self.combo_target.addItem("All Claude Nodes Only", "all_claude")
        self.combo_target.addItem("All Gemini Nodes Only", "all_gemini")

        panes = self.get_panes() or {}
        for acc_id, pane in panes.items():
            self.combo_target.addItem(f"{pane.account_name} [{pane.platform.capitalize()}]", acc_id)

        self._render_table()

    def _get_vault_data(self) -> Dict:
        proj = self.get_project()
        if not proj:
            return {"files": [], "folders": []}
        return proj.setdefault("file_vault", {"files": [], "folders": []})

    def _mark_dirty(self):
        proj = self.get_project()
        if proj:
            proj["_is_dirty"] = True

    def _clear_false_request_flags(self):
        vault = self._get_vault_data()
        for f in vault.get("files", []):
            f["requested_by_nodes"] = []
            f["requested_by_ids"] = []
            if not f.get("is_harvested"):
                f["planned_usage"] = "Ready in Vault"
        self._mark_dirty()
        self._render_table()
        self._emit_recommendations()

    def register_harvested_file(self, file_name: str, disk_path: str, producer_id: str, producer_name: str):
        vault = self._get_vault_data()
        norm_p = os.path.abspath(disk_path)
        for existing in vault.get("files", []):
            if existing.get("path") == norm_p or existing.get("name") == file_name:
                existing["path"] = norm_p
                existing["folder"] = f"Harvested ({producer_name})"
                existing["producer_id"] = producer_id
                existing["producer_name"] = producer_name
                existing["is_harvested"] = True
                if "Requested" not in existing.get("planned_usage", ""):
                    existing["planned_usage"] = f"Caught Live from {producer_name}"
                self._render_table()
                self._emit_recommendations()
                return

        vault.setdefault("files", []).append({
            "name": file_name,
            "path": norm_p,
            "folder": f"Harvested ({producer_name})",
            "producer_id": producer_id,
            "producer_name": producer_name,
            "is_harvested": True,
            "used_history": [],
            "requested_by_nodes": [],
            "requested_by_ids": [],
            "planned_usage": f"Caught Live from {producer_name}"
        })
        self._mark_dirty()
        self._render_table()
        self._emit_recommendations()

    def _prompt_ai_for_file_routing(self):
        vault = self._get_vault_data()
        files = vault.get("files", [])
        if not files:
            QMessageBox.information(self, "Vault Empty", "Please attach files or a folder to the vault first.")
            return

        panes = self.get_panes() or {}
        if not panes:
            return

        target_key = self.combo_target.currentData()
        proj = self.get_project() or {}
        master_id = proj.get("master_node_id")

        if target_key in panes:
            target_pane = panes[target_key]
        elif master_id and master_id in panes:
            target_pane = panes[master_id]
        else:
            target_pane = next(iter(panes.values()))

        worker_names = [f"{p.account_name} ({p.platform.capitalize()})" for p in panes.values()]
        file_names = [f["name"] for f in files]

        discovery_prompt = (
            "We are organizing our Binary Tree / Swarm execution pipeline.\n"
            f"Active AI Nodes: {', '.join(worker_names)}.\n"
            f"Available Files in Project Vault: {', '.join(file_names)}.\n\n"
            "Reply using these exact tags so the Live Graph Relay can route files automatically:\n"
            "1. Files you need uploaded right now: REQUEST_FILES: [exact_filename1, exact_filename2]\n"
            "2. Files each branch/leaf node needs: STAGE_FILES: NodeName -> [exact_filename1, exact_filename2]"
        )

        self.injector.send_prompt(
            page=target_pane.get_page(),
            platform=target_pane.platform,
            prompt_text=discovery_prompt,
            file_path=None,
            view=target_pane.web_view
        )

    def scan_chats_for_file_requests(self):
        vault = self._get_vault_data()
        files = vault.get("files", [])
        panes = self.get_panes() or {}
        if not files or not panes:
            return

        req_pattern = re.compile(
            r"(?:REQUEST_FILES|REQUIRED_FILES|NEED_FILE|NEED_FILES|UPLOAD_FILES)\s*:\s*\[?([^\n\]]+)\]?",
            re.IGNORECASE
        )
        stage_pattern = re.compile(
            r"STAGE_FILES\s*:\s*([A-Za-z0-9_.-]+)\s*->\s*\[?([^\n\]]+)\]?",
            re.IGNORECASE
        )

        name_to_pane = {p.account_name.lower(): (aid, p) for aid, p in panes.items()}

        for acc_id, pane in panes.items():
            def _make_cb(aid=acc_id, pname=pane.account_name):
                def _on_text(text: str):
                    if not text or len(text.strip()) < 15:
                        return
                    cleaned_lines = [
                        ln for ln in text.splitlines()
                        if "exact_filename1" not in ln and "Reply using these exact tags" not in ln
                    ]
                    clean_body = "\n".join(cleaned_lines)

                    changed = False
                    for match in req_pattern.finditer(clean_body):
                        raw_list = match.group(1).lower()
                        for entry in files:
                            fname = entry.get("name", "")
                            if fname and fname.lower() in raw_list:
                                req_by = entry.setdefault("requested_by_nodes", [])
                                if pname not in req_by:
                                    req_by.append(pname)
                                    req_ids = entry.setdefault("requested_by_ids", [])
                                    if aid not in req_ids:
                                        req_ids.append(aid)
                                    entry["planned_usage"] = f"Requested by: {', '.join(req_by)}"
                                    changed = True
                                    self.explicit_file_request_detected.emit(aid, pname, fname, entry.get("path", ""))

                    for smatch in stage_pattern.finditer(clean_body):
                        target_node_str = smatch.group(1).strip().lower()
                        raw_list = smatch.group(2).lower()
                        matched_aid, matched_pane = None, None
                        for k_name, (cand_id, cand_p) in name_to_pane.items():
                            if target_node_str in k_name or k_name in target_node_str:
                                matched_aid, matched_pane = cand_id, cand_p
                                break
                        if matched_aid and matched_pane:
                            for entry in files:
                                fname = entry.get("name", "")
                                if fname and fname.lower() in raw_list:
                                    req_by = entry.setdefault("requested_by_nodes", [])
                                    if matched_pane.account_name not in req_by:
                                        req_by.append(matched_pane.account_name)
                                        req_ids = entry.setdefault("requested_by_ids", [])
                                        if matched_aid not in req_ids:
                                            req_ids.append(matched_aid)
                                        entry["planned_usage"] = f"Requested by: {', '.join(req_by)}"
                                        changed = True
                                        self.explicit_file_request_detected.emit(
                                            matched_aid, matched_pane.account_name, fname, entry.get("path", "")
                                        )

                    if changed:
                        self._mark_dirty()
                        self._render_table()
                        self._emit_recommendations()
                return _on_text

            DOMScraper.scrape_page_text(pane.get_page(), _make_cb())

    def _emit_recommendations(self):
        vault = self._get_vault_data()
        recs = [f for f in vault.get("files", []) if f.get("requested_by_ids")]
        self.recommendations_updated.emit(recs)

    def upload_all_recommended_to_requesting_chats(self):
        vault = self._get_vault_data()
        panes = self.get_panes() or {}
        if not panes:
            return

        node_to_files: Dict[str, List[Dict]] = {}
        for entry in vault.get("files", []):
            req_ids = entry.get("requested_by_ids", [])
            for aid in req_ids:
                if aid in panes:
                    node_to_files.setdefault(aid, []).append(entry)

        if not node_to_files:
            QMessageBox.information(
                self,
                "No Explicit File Requests Yet",
                "No active Claude or Gemini node has requested files (REQUEST_FILES: [...]) yet.\n\n"
                "Tip: To manually send checked files to a specific chat, use 'Paste Checked -> Selected Target(s)' "
                "or approve a file link directly on the Live Graph Relay!"
            )
            return

        stamp = datetime.now().strftime("%H:%M:%S")
        prompt_note = self.input_note.text().strip() or "Here are the requested project files from the Nexus Vault."

        for aid, entries in node_to_files.items():
            pane = panes[aid]
            paths = [e["path"] for e in entries if os.path.exists(e["path"])]
            if not paths:
                continue
            self.injector.send_multi_files(
                page=pane.get_page(),
                platform=pane.platform,
                prompt_text=prompt_note,
                file_paths=paths,
                view=pane.web_view
            )
            for e in entries:
                e.setdefault("used_history", []).append(f"{pane.account_name} ({stamp})")

        self._mark_dirty()
        self._render_table()

    def _on_attach_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Attach Multiple Files to Project Vault", "", "All Files (*.*)")
        if not files:
            return
        vault = self._get_vault_data()
        existing_paths = {f["path"] for f in vault["files"]}

        for fpath in files:
            norm = os.path.abspath(fpath)
            if norm not in existing_paths and os.path.isfile(norm):
                vault["files"].append({
                    "name": os.path.basename(norm),
                    "path": norm,
                    "folder": os.path.dirname(norm),
                    "used_history": [],
                    "requested_by_nodes": [],
                    "requested_by_ids": [],
                    "planned_usage": "Ready in Vault"
                })
                existing_paths.add(norm)

        self._mark_dirty()
        self._render_table()
        self._emit_recommendations()

    def _on_attach_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Attach Project Folder from Computer")
        if not folder:
            return
        norm_folder = os.path.abspath(folder)
        vault = self._get_vault_data()
        if norm_folder not in vault["folders"]:
            vault["folders"].append(norm_folder)

        existing_paths = {f["path"] for f in vault["files"]}
        added = 0
        for root, dirs, files in os.walk(norm_folder):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext in CODE_EXTS:
                    full_p = os.path.abspath(os.path.join(root, fn))
                    if full_p not in existing_paths:
                        vault["files"].append({
                            "name": fn,
                            "path": full_p,
                            "folder": norm_folder,
                            "used_history": [],
                            "requested_by_nodes": [],
                            "requested_by_ids": [],
                            "planned_usage": "Indexed from Folder (Idle)"
                        })
                        existing_paths.add(full_p)
                        added += 1
                        if added >= 60:
                            break
            if added >= 60:
                break

        self._mark_dirty()
        self._render_table()
        self._emit_recommendations()

    def _toggle_all_checks(self):
        any_unchecked = any(
            self.table.item(r, 0) and self.table.item(r, 0).checkState() != Qt.CheckState.Checked
            for r in range(self.table.rowCount())
        )
        state = Qt.CheckState.Checked if any_unchecked else Qt.CheckState.Unchecked
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it:
                it.setCheckState(state)

    def _remove_selected_files(self):
        vault = self._get_vault_data()
        keep = []
        for r, fentry in enumerate(vault["files"]):
            it = self.table.item(r, 0)
            if not it or it.checkState() != Qt.CheckState.Checked:
                keep.append(fentry)
        vault["files"] = keep
        self._mark_dirty()
        self._render_table()
        self._emit_recommendations()

    def _get_checked_file_entries(self) -> List[Dict]:
        vault = self._get_vault_data()
        checked = []
        for r, fentry in enumerate(vault["files"]):
            it = self.table.item(r, 0)
            if it and it.checkState() == Qt.CheckState.Checked:
                checked.append(fentry)
        return checked

    def _paste_to_master(self):
        proj = self.get_project() or {}
        master_id = proj.get("master_node_id")
        panes = self.get_panes() or {}
        if not master_id or master_id not in panes:
            if panes:
                master_id = next(iter(panes.keys()))
            else:
                return
        self._dispatch_files_to_panes([panes[master_id]])

    def _paste_to_selected_target(self):
        target_key = self.combo_target.currentData()
        panes = self.get_panes() or {}
        if not panes:
            return

        if target_key == "all":
            target_panes = list(panes.values())
        elif target_key == "all_claude":
            target_panes = [p for p in panes.values() if p.platform == "claude"]
        elif target_key == "all_gemini":
            target_panes = [p for p in panes.values() if p.platform == "gemini"]
        elif target_key in panes:
            target_panes = [panes[target_key]]
        else:
            target_panes = []

        self._dispatch_files_to_panes(target_panes)

    def _dispatch_files_to_panes(self, target_panes: List):
        checked_entries = self._get_checked_file_entries()
        if not checked_entries:
            QMessageBox.information(self, "No Files Checked", "Please check [\u2713] one or more files in the table first.")
            return
        if not target_panes:
            return

        paths = [e["path"] for e in checked_entries if os.path.exists(e["path"])]
        prompt_text = self.input_note.text().strip()
        stamp = datetime.now().strftime("%H:%M:%S")

        for pane in target_panes:
            self.injector.send_multi_files(
                page=pane.get_page(),
                platform=pane.platform,
                prompt_text=prompt_text,
                file_paths=paths,
                view=pane.web_view
            )
            for entry in checked_entries:
                hist = entry.setdefault("used_history", [])
                hist.append(f"{pane.account_name} ({stamp})")

        self._mark_dirty()
        self._render_table()

    def _render_table(self):
        vault = self._get_vault_data()
        folders = vault.get("folders", [])
        if folders:
            short_folders = [os.path.basename(f) or f for f in folders]
            self.lbl_folders.setText("Attached Folders: " + " | ".join(short_folders))
        else:
            self.lbl_folders.setText("Attached Folders: None")

        files = vault.get("files", [])
        self.table.setRowCount(len(files))

        white_brush = QBrush(QColor("#f4f4f5"))

        for r, fentry in enumerate(files):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            is_req = bool(fentry.get("requested_by_ids"))
            chk.setCheckState(Qt.CheckState.Checked if is_req else Qt.CheckState.Unchecked)

            name_it = QTableWidgetItem(fentry.get("name", ""))
            name_it.setForeground(white_brush)

            path_it = QTableWidgetItem(fentry.get("path", ""))
            path_it.setForeground(white_brush)

            folder_str = fentry.get("folder", "")
            if not folder_str.startswith("Harvested"):
                folder_str = os.path.basename(folder_str) or folder_str
            folder_it = QTableWidgetItem(folder_str)
            folder_it.setForeground(QBrush(QColor("#10b981") if fentry.get("is_harvested") else QColor("#f4f4f5")))

            hist_list = fentry.get("used_history", [])
            hist_str = ", ".join(hist_list[-4:]) if hist_list else "Never used yet"
            hist_it = QTableWidgetItem(hist_str)
            hist_it.setForeground(QBrush(QColor("#10b981" if hist_list else "#a1a1aa")))

            plan_str = fentry.get("planned_usage", "Ready in Vault")
            plan_it = QTableWidgetItem(plan_str)
            if is_req:
                plan_it.setForeground(QBrush(QColor("#f97316")))
            elif fentry.get("is_harvested"):
                plan_it.setForeground(QBrush(QColor("#10b981")))
            else:
                plan_it.setForeground(white_brush)

            self.table.setItem(r, 0, chk)
            self.table.setItem(r, 1, name_it)
            self.table.setItem(r, 2, path_it)
            self.table.setItem(r, 3, folder_it)
            self.table.setItem(r, 4, hist_it)
            self.table.setItem(r, 5, plan_it)