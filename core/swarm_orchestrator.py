import re
from typing import Dict, List, Tuple


class SwarmOrchestrator:
    """
    Constructs Master Architect Directives and parses the returned
    Project Routing [MAP] and Worker Task Delegation blocks.
    """

    def __init__(self):
        self.task_pattern = re.compile(
            r"===\s*TASK_START\s*:\s*([^\n=]+?)\s*===\s*\n(.*?)===\s*TASK_END\s*===",
            re.DOTALL | re.IGNORECASE
        )
        self.map_block_pattern = re.compile(
            r"===\s*MAP_START\s*===\s*(.*?)===\s*MAP_END\s*===",
            re.DOTALL | re.IGNORECASE
        )

    def build_master_directive(self, user_goal: str, project_name: str, worker_accounts: List[dict]) -> str:
        worker_roster = "\n".join(
            [f"- Worker ID: `{acc['id']}` (Name: {acc['account_name']})" for acc in worker_accounts]
        )
        default_worker = worker_accounts[0]['id'] if worker_accounts else 'worker_1'

        directive = (
            f"You are the **Master Software Architect & Dependency Manager** for project `{project_name}`.\n"
            f"Your job is to break down the following software engineering goal into modular tasks for your Subordinate AI Worker Nodes.\n\n"
            f"### USER PROJECT GOAL:\n{user_goal}\n\n"
            f"### AVAILABLE SUBORDINATE WORKER NODES:\n{worker_roster}\n\n"
            "---\n\n"
            "### ARCHITECTURAL RULES (CRITICAL — FOLLOW EXACTLY):\n\n"
            "1. **ONLY YOU KNOW THE DIRECTORY TREE (THE PROJECT MAP):**\n"
            "   - Do NOT burden the subordinate workers with nested folder paths (like `src/ui/popup.html`).\n"
            "   - Instead, instruct each subordinate worker to create their assigned files using ONLY the **raw filename** (e.g., `popup.html`, `background.js`).\n"
            "   - You will output a `===MAP_START===` block so our Python Assembler knows where each worker's raw filename belongs in the final directory structure.\n\n"
            "2. **CONTRACT-DRIVEN DEVELOPMENT (INTERFACE CONTRACTS):**\n"
            "   - Because workers generate code in separate browser nodes, you MUST define exact **Interface Contracts** inside each worker's prompt (exact function names, message payloads, DOM element IDs, CSS class names) so all files snap together without errors.\n"
            "   - Order the workers in logical dependency order.\n\n"
            "3. **WORKER OUTPUT FORMAT REQUIREMENTS:**\n"
            "   - Inside every worker prompt you write, explicitly instruct the worker:\n"
            "     a) Output EVERY assigned file preceded by `===FILE: raw_filename.ext===` followed immediately by a standard markdown code block.\n"
            "     b) Do NOT use interactive Artifact side-panels; print all code inline in standard markdown code blocks.\n"
            "     c) At the very end of its response, the worker MUST output a short summary block formatted as:\n"
            "        `===SUMMARY===`\n"
            "        (2-4 bullet points listing the exact exported functions, message listeners, and IDs it implemented for the next stage)\n"
            "        `===END_SUMMARY===`\n\n"
            "---\n\n"
            "### REQUIRED OUTPUT FORMAT FROM YOU (MASTER NODE):\n\n"
            "First, output the **Project Routing Map** using this exact delimiter block (one file per line, formatted as `worker_id | raw_filename | full/relative/path/to/raw_filename`):\n\n"
            "===MAP_START===\n"
            f"{default_worker} | manifest.json | manifest.json\n"
            f"{default_worker} | background.js | src/background.js\n"
            "===MAP_END===\n\n"
            "Second, output the **Delegation Prompts** for each worker in sequential stage order using these exact delimiter blocks:\n\n"
            "===TASK_START: <worker_id>===\n"
            f"You are building the assigned module for `{project_name}`.\n"
            "Your assigned raw files to create: `filename1.ext`, `filename2.ext`.\n\n"
            "[Insert complete Interface Contract: exact message names, payload structures, DOM IDs, and logic specifications]\n\n"
            "CRITICAL OUTPUT RULES:\n"
            "1. Do NOT use the Artifact viewer. Output all code directly in chat inside markdown code blocks.\n"
            "2. Immediately before each code block, write the exact tag:\n"
            "===FILE: filename.ext===\n"
            "```language\n"
            "// full code here\n"
            "```\n"
            "3. Finish your response with:\n"
            "===SUMMARY===\n"
            "- Bullet summary of exact APIs/listeners/IDs created.\n"
            "===END_SUMMARY===\n"
            "===TASK_END===\n\n"
            f"Now generate the complete `===MAP_START===` block and all `===TASK_START: <worker_id>===` blocks for `{project_name}`."
        )
        return directive

    def parse_master_response(
        self, raw_text: str, valid_worker_ids: List[str]
    ) -> Tuple[Dict[str, str], Dict[str, Dict[str, str]], Dict[str, List[str]]]:
        tasks_by_worker: Dict[str, str] = {}
        routing_map: Dict[str, Dict[str, str]] = {wid: {} for wid in valid_worker_ids}
        assigned_files_display: Dict[str, List[str]] = {wid: [] for wid in valid_worker_ids}

        map_blocks = self.map_block_pattern.findall(raw_text)
        if map_blocks:
            latest_map = map_blocks[-1]
            for line in latest_map.strip().splitlines():
                line = line.strip()
                if not line or "|" not in line:
                    continue
                parts = [p.strip().strip("`'\"") for p in line.split("|")]
                if len(parts) >= 3:
                    w_id, raw_fname, rel_path = parts[0], parts[1], parts[2]
                    matched_id = self._match_worker_id(w_id, valid_worker_ids)
                    if matched_id:
                        routing_map[matched_id][raw_fname] = rel_path
                        if raw_fname not in assigned_files_display[matched_id]:
                            assigned_files_display[matched_id].append(raw_fname)

        task_matches = self.task_pattern.findall(raw_text)
        for raw_wid, prompt_body in task_matches:
            clean_wid = raw_wid.strip().strip("`'\"<>")
            if clean_wid.lower() == "worker_id" or "[insert complete interface contract" in prompt_body.lower():
                continue
            matched_id = self._match_worker_id(clean_wid, valid_worker_ids)
            if matched_id:
                tasks_by_worker[matched_id] = prompt_body.strip()

        return tasks_by_worker, routing_map, assigned_files_display

    def _match_worker_id(self, candidate: str, valid_ids: List[str]) -> str:
        cand_low = candidate.lower().strip()
        for vid in valid_ids:
            if vid.lower() == cand_low or vid.lower() in cand_low or cand_low in vid.lower():
                return vid
        return ""