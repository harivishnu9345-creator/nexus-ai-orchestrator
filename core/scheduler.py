"""
Task Scheduler Module
Manages a background queue of automated prompts based on target AM/PM times.
"""

import uuid
from typing import Dict, Any, List, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QTime, QDateTime

class TaskScheduler(QObject):
    task_due = pyqtSignal(dict)           
    queue_updated = pyqtSignal(list)      

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._queue: Dict[str, Dict[str, Any]] = {}
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_queue)
        self._timer.start(2000)

    def add_task(self, account_id: str, platform: str, prompt_text: str, target_time: QTime, file_path: Optional[str] = None) -> str:
        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "account_id": account_id,
            "platform": platform.capitalize(),
            "prompt_text": prompt_text,
            "file_path": file_path,
            "target_time": target_time,
            "status": "queued",
            "created_at": QDateTime.currentDateTime()
        }
        self._queue[task_id] = task
        self._emit_queue_update()
        return task_id

    def remove_task(self, task_id: str) -> bool:
        if task_id in self._queue:
            del self._queue[task_id]
            self._emit_queue_update()
            return True
        return False

    def update_task_status(self, task_id: str, status: str, cooldown_time: Optional[str] = None) -> None:
        if task_id in self._queue:
            self._queue[task_id]["status"] = status
            if cooldown_time: self._queue[task_id]["cooldown_time"] = cooldown_time
            self._emit_queue_update()

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        tasks = list(self._queue.values())
        tasks.sort(key=lambda t: t["target_time"])
        return tasks

    def _check_queue(self) -> None:
        current_time = QTime.currentTime()
        for task_id, task in self._queue.items():
            if task["status"] == "queued":
                if current_time >= task["target_time"]:
                    task["status"] = "running"
                    self.task_due.emit(task)
                    self._emit_queue_update()

    def _emit_queue_update(self) -> None:
        self.queue_updated.emit(self.get_all_tasks())
