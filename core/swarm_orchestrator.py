import re
from PyQt6.QtCore import QObject, pyqtSignal, QTime

class SwarmOrchestrator(QObject):
    orchestration_complete = pyqtSignal(int)
    orchestration_error = pyqtSignal(str)

    def __init__(self, scheduler):
        super().__init__()
        self.scheduler = scheduler

    def build_master_directive(self, user_prompt: str, worker_accounts: list) -> str:
        workers_info = "\n".join([f"ID: {acc['id']} | Name: {acc['account_name']}" for acc in worker_accounts])
        directive = f"""You are the Master Architect Orchestrator. 
Break down the user's request into a modular directory structure and write specific sub-prompts for your subordinate AI accounts.

USER REQUEST:
"{user_prompt}"

YOUR SUBORDINATES:
{workers_info}

STRICT OUTPUT RULES:
1. Assign each subordinate exact relative file paths from the project root (e.g., src/background.js).
2. Instruct every subordinate: "DO NOT use interactive Artifacts or previews. Output all code inline in the chat. Before EVERY code block, write the exact file path tag like this:
===FILE: relative/path/to/filename.ext===
```language
(full file code here)
```"
3. You MUST wrap each subordinate's prompt EXACTLY like this:

===[ID]===
(detailed prompt for this subordinate including their assigned file paths and the ===FILE: path=== rule)

Do not add conversational filler. Use the exact IDs provided.
"""
        return directive

    def process_master_response(self, raw_text: str, worker_accounts: list):
        tasks_queued = 0
        for acc in worker_accounts:
            target_id = acc['id']
            pattern = rf"===\s*\[?\s*{re.escape(target_id)}\s*\]?\s*===\s*(.*?)(?:\n===|$)"
            match = re.search(pattern, raw_text, re.DOTALL | re.IGNORECASE)

            if match:
                sub_prompt = match.group(1).strip()
                if sub_prompt:
                    target_time = QTime.currentTime().addSecs(tasks_queued * 2)
                    self.scheduler.add_task(
                        account_id=target_id, platform=acc.get('platform', 'claude'),
                        prompt_text=sub_prompt, target_time=target_time, file_path=None
                    )
                    tasks_queued += 1
        if tasks_queued > 0: self.orchestration_complete.emit(tasks_queued)
        else: self.orchestration_error.emit("Failed to parse Master response. Delimiters were missing.")