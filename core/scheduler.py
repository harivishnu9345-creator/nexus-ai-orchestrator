import uuid
from typing import List, Dict, Any
from PyQt6.QtCore import QObject, QTimer, QTime, QDateTime, pyqtSignal
from core.injector import DOMInjector
from core.injector_sub import SubInjector


class TaskScheduler(QObject):
    queue_updated = pyqtSignal(list)
    rate_limit_detected = pyqtSignal(str, str, str, str)
    task_status_changed = pyqtSignal(str, str)
    sub_injector_telemetry = pyqtSignal(str)
    stage_dispatched = pyqtSignal(str)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.tasks: List[Dict] = []
        self.panes: Dict = {}
        self.accounts_map: Dict = {}

        self.is_injecting = False
        self.active_injector_type = None

        self.primary_injector = DOMInjector()
        self.sub_injector = SubInjector(self)
        self.sub_injector.progress_update.connect(self.sub_injector_telemetry.emit)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_queue)
        self.timer.start(1000)

    def register_pane(self, account_id: str, pane, account_info: dict):
        self.panes[account_id] = pane
        self.accounts_map[account_id] = account_info

    def serialize_tasks(self) -> List[Dict[str, Any]]:
        serialized = []
        for t in self.tasks:
            dt = t.get("target_datetime")
            dt_str = dt.toString("yyyy-MM-dd hh:mm:ss AP") if isinstance(dt, QDateTime) else t.get("target_datetime_str", "")
            serialized.append({
                "task_id": t.get("task_id"),
                "account_id": t.get("account_id"),
                "account_name": t.get("account_name"),
                "platform": t.get("platform"),
                "prompt_text": t.get("prompt_text"),
                "file_path": t.get("file_path"),
                "file_paths": t.get("file_paths", []),
                "target_datetime_str": dt_str,
                "status": t.get("status"),
                "cooldown_time": t.get("cooldown_time"),
                "stage_index": t.get("stage_index", -1)
            })
        return serialized

    def load_serialized_tasks(self, saved_tasks: List[Dict[str, Any]]):
        self.tasks.clear()
        for st in (saved_tasks or []):
            dt_str = st.get("target_datetime_str", "")
            dt = QDateTime.fromString(dt_str, "yyyy-MM-dd hh:mm:ss AP")
            if not dt.isValid():
                dt = QDateTime.currentDateTime()
            # Historical running tasks that were interrupted on close become 'success' or remain visible
            status = st.get("status", "success")
            if status == "running":
                status = "success"
            self.tasks.append({
                "task_id": st.get("task_id", str(uuid.uuid4())),
                "account_id": st.get("account_id", ""),
                "account_name": st.get("account_name", "Unknown"),
                "platform": st.get("platform", "claude"),
                "prompt_text": st.get("prompt_text", ""),
                "file_path": st.get("file_path"),
                "file_paths": st.get("file_paths", []),
                "target_datetime": dt,
                "target_datetime_str": dt.toString("yyyy-MM-dd hh:mm:ss AP"),
                "target_time": dt.time(),
                "status": status,
                "cooldown_time": st.get("cooldown_time"),
                "stage_index": st.get("stage_index", -1)
            })
        self.queue_updated.emit(self.tasks)

    def add_task(
        self,
        target_id: str,
        prompt: str,
        target_time: Any = None,
        file_path: str = None,
        file_paths: List[str] = None,
        hold_for_gate: bool = False,
        stage_index: int = -1,
        target_datetime: QDateTime = None
    ):
        if isinstance(target_time, QDateTime):
            dt = target_time
        elif isinstance(target_datetime, QDateTime):
            dt = target_datetime
        elif isinstance(target_time, QTime):
            dt = QDateTime(QDateTime.currentDateTime().date(), target_time)
        else:
            dt = QDateTime.currentDateTime()

        initial_status = "held_for_gate" if hold_for_gate else "queued"
        targets = list(self.panes.keys()) if target_id == "all" else [target_id]

        for acc_id in targets:
            if acc_id not in self.accounts_map:
                continue
            acc = self.accounts_map[acc_id]
            task = {
                "task_id": str(uuid.uuid4()),
                "account_id": acc_id,
                "account_name": acc["account_name"],
                "platform": acc.get("platform", "claude"),
                "prompt_text": prompt,
                "file_path": file_path,
                "file_paths": file_paths or ([] if not file_path else [file_path]),
                "target_datetime": dt,
                "target_datetime_str": dt.toString("yyyy-MM-dd hh:mm:ss AP"),
                "target_time": dt.time(),
                "status": initial_status,
                "cooldown_time": None,
                "stage_index": stage_index
            }
            self.tasks.append(task)

        self.queue_updated.emit(self.tasks)

    def release_stage_task(
        self,
        account_id: str,
        appended_summary: str = "",
        relay_files: List[str] = None
    ):
        now_dt = QDateTime.currentDateTime()
        for task in self.tasks:
            if task["account_id"] == account_id and task["status"] == "held_for_gate":
                if appended_summary:
                    task["prompt_text"] = (
                        f"{task['prompt_text']}\n\n"
                        f"=== UPSTREAM STAGE INTERFACE SUMMARY ===\n"
                        f"{appended_summary}\n"
                        f"========================================"
                    )
                if relay_files:
                    task["file_paths"] = list(relay_files)
                task["target_datetime"] = now_dt
                task["target_datetime_str"] = now_dt.toString("yyyy-MM-dd hh:mm:ss AP")
                task["target_time"] = now_dt.time()
                task["status"] = "queued"
                break

        self.queue_updated.emit(self.tasks)
        self._check_queue()

    def release_all_held_tasks(self):
        now_dt = QDateTime.currentDateTime()
        for task in self.tasks:
            if task["status"] == "held_for_gate":
                task["target_datetime"] = now_dt
                task["target_datetime_str"] = now_dt.toString("yyyy-MM-dd hh:mm:ss AP")
                task["target_time"] = now_dt.time()
                task["status"] = "queued"
        self.queue_updated.emit(self.tasks)
        self._check_queue()

    def schedule_auto_resume(self, account_id: str):
        resume_dt = QDateTime.currentDateTime().addSecs(120)
        for task in self.tasks:
            if task["account_id"] == account_id and task["status"] in ("rate_limited", "failed"):
                task["target_datetime"] = resume_dt
                task["target_datetime_str"] = resume_dt.toString("yyyy-MM-dd hh:mm:ss AP")
                task["target_time"] = resume_dt.time()
                task["status"] = "queued"
        self.queue_updated.emit(self.tasks)

    def _check_queue(self):
        if self.is_injecting:
            return

        now_dt = QDateTime.currentDateTime()
        for task in self.tasks:
            if task["status"] == "queued":
                t_dt = task.get("target_datetime")
                if isinstance(t_dt, QDateTime):
                    ready = now_dt >= t_dt
                else:
                    ready = QTime.currentTime() >= task.get("target_time", QTime.currentTime())
                if ready:
                    self._execute_task(task)
                    break

    def _execute_task(self, task: dict):
        acc_id = task["account_id"]
        if acc_id not in self.panes:
            task["status"] = "failed"
            self.queue_updated.emit(self.tasks)
            return

        self.is_injecting = True
        task["status"] = "running"
        self.queue_updated.emit(self.tasks)
        self.task_status_changed.emit(acc_id, "running")

        pane = self.panes[acc_id]
        platform_key = task["platform"].lower()
        platform_cfg = self.config.get("platforms", {}).get(platform_key, {})
        selectors = platform_cfg.get("selectors", {})

        file_list = [f for f in (task.get("file_paths") or []) if f]

        if len(file_list) > 1 or (len(file_list) == 1 and task.get("stage_index", -1) > 0):
            self.active_injector_type = "sub"
            self.sub_injector_telemetry.emit(
                f"Sub-Injector Active -> {task['account_name']} ({len(file_list)} file(s))"
            )

            def _on_sub_done(res):
                try:
                    self.sub_injector.injection_complete.disconnect(_on_sub_done)
                except Exception:
                    pass
                self._on_execution_complete(task, res)

            self.sub_injector.injection_complete.connect(_on_sub_done)
            self.sub_injector.inject_multiple_files(
                page=pane.get_page(),
                prompt_text=task["prompt_text"],
                file_paths=file_list,
                selectors=selectors,
                view=pane.web_view if hasattr(pane, "web_view") else None
            )
        else:
            self.active_injector_type = "primary"
            single_file = file_list[0] if len(file_list) == 1 else task.get("file_path")
            self.sub_injector_telemetry.emit(f"Primary Injector Active -> {task['account_name']}")
            self.primary_injector.send_prompt(
                page=pane.get_page(),
                platform=platform_key,
                prompt_text=task["prompt_text"],
                file_path=single_file,
                view=pane.web_view if hasattr(pane, "web_view") else None,
                callback=lambda res: self._on_execution_complete(task, res)
            )

    def _on_execution_complete(self, task: dict, result: dict):
        self.is_injecting = False
        self.active_injector_type = None

        acc_id = task["account_id"]
        if not isinstance(result, dict):
            result = {"success": bool(result)}

        status = result.get("status", "success" if result.get("success") else "failed")

        if status == "success":
            task["status"] = "success"
            self.task_status_changed.emit(acc_id, "ready")
            self.stage_dispatched.emit(acc_id)
        elif status == "rate_limited":
            task["status"] = "rate_limited"
            resets_at = result.get("resets_at", "Unknown")
            task["cooldown_time"] = resets_at
            self.task_status_changed.emit(acc_id, "rate_limited")
            self.rate_limit_detected.emit(
                acc_id, task["account_name"], task["platform"], resets_at
            )
        else:
            task["status"] = "failed"
            self.task_status_changed.emit(acc_id, "rate_limited")

        self.queue_updated.emit(self.tasks)
        QTimer.singleShot(2000, self._check_queue)

    def clear_completed(self):
        self.tasks = [t for t in self.tasks if t["status"] not in ("success", "failed")]
        self.queue_updated.emit(self.tasks)
