import re
from PyQt6.QtCore import QObject, pyqtSignal, QTime

class SwarmOrchestrator(QObject):
    orchestration_complete = pyqtSignal(int)
    orchestration_error = pyqtSignal(str)

    def __init__(self, scheduler):
        super().__init__()
        self.scheduler = scheduler

    def build_master_directive(self, user_prompt: str, worker_accounts: list) -> str:
        print(f"\n[ORCHESTRATOR] Building Master Directive for {len(worker_accounts)} subordinates...")
        workers_info = "\n".join([f"ID: {acc['id']} | Name: {acc['account_name']}" for acc in worker_accounts])

        directive = f"""You are the Master Architect Orchestrator. 
Your job is to break down the user's request and write highly specific, optimized sub-prompts for your subordinate AI accounts.

USER REQUEST:
"{user_prompt}"

YOUR SUBORDINATES:
{workers_info}

STRICT OUTPUT RULES:
You must generate a specific prompt for your subordinates to execute the plan.
You MUST wrap each subordinate's prompt EXACTLY like this:

===[ID]===
(detailed prompt text for this specific subordinate)

Do not add conversational filler. Use the exact IDs provided.
"""
        return directive

    def process_master_response(self, raw_text: str, worker_accounts: list):
        print("\n" + "=" * 50)
        print("[ORCHESTRATOR] PROCESSING MASTER RESPONSE")
        print("=" * 50)
        print(f"[DEBUG] Raw text received from scraper (length: {len(raw_text)} chars)")

        tasks_queued = 0
        for acc in worker_accounts:
            target_id = acc['id']
            print(f"\n[ORCHESTRATOR] Searching for Subordinate: {acc['account_name']} (ID: {target_id})")

            # Matches both ===acc_id=== and ===[acc_id]===
            pattern = rf"===\s*\[?\s*{re.escape(target_id)}\s*\]?\s*===\s*(.*?)(?:\n===|$)"
            match = re.search(pattern, raw_text, re.DOTALL | re.IGNORECASE)

            if match:
                sub_prompt = match.group(1).strip()
                if sub_prompt:
                    print(f"[ORCHESTRATOR] Match Found! Extracted {len(sub_prompt)} chars for {target_id}.")
                    target_time = QTime.currentTime().addSecs(tasks_queued * 2)
                    self.scheduler.add_task(
                        account_id=target_id,
                        platform=acc.get('platform', 'claude'),
                        prompt_text=sub_prompt,
                        target_time=target_time,
                        file_path=None
                    )
                    tasks_queued += 1
                else:
                    print(f"[ORCHESTRATOR] Match found for {target_id}, but the prompt was empty.")
            else:
                print(f"[ORCHESTRATOR] FAILED to find delimiter for {target_id}.")

        if tasks_queued > 0:
            self.orchestration_complete.emit(tasks_queued)
        else:
            self.orchestration_error.emit("Failed to parse Master response. Delimiters were missing or malformed.")