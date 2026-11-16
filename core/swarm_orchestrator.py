import re
from typing import Dict, List, Tuple, Any
from core.dom_scraper import DOMScraper


class SwarmOrchestrator:
    """
    Constructs Master Architect Directives with strict triple-equals (===)
    delimiter enforcement, topology-aware dependency rules, and parses:
      - Project Routing Map (===MAP_START=== ... ===MAP_END===)
      - Per-worker recommended upstream files & summaries
      - Worker Task Delegation prompts (===TASK_START: <worker_id>=== ... ===TASK_END===)
    """

    def __init__(self):
        self.task_pattern = re.compile(
            r"={1,3}\s*TASK_START\s*:\s*([^\r\n=]+?)\s*={1,3}\s*\r?\n(.*?)(?:^|\r?\n)[\s>*\-\u2022\d.]*={1,3}\s*TASK_END\s*={1,3}",
            re.DOTALL | re.IGNORECASE | re.MULTILINE
        )
        self.map_block_pattern = re.compile(
            r"={1,3}\s*MAP_START\s*={1,3}\s*(.*?)={1,3}\s*MAP_END\s*={1,3}",
            re.DOTALL | re.IGNORECASE
        )
        self.last_worker_dependencies: Dict[str, Dict[str, Any]] = {}

    def build_master_directive(
        self,
        user_goal: str,
        project_name: str,
        worker_accounts: List[dict],
        strategy_mode: str = "binary_tree"
    ) -> str:
        worker_roster = "\n".join(
            [
                f"- Stage {idx + 1} Worker ID: `{acc['id']}` (Name: {acc['account_name']}, Platform: {acc.get('platform', 'claude').capitalize()})"
                for idx, acc in enumerate(worker_accounts)
            ]
        )
        w0 = worker_accounts[0]["id"] if worker_accounts else "worker_1"
        w1 = worker_accounts[1]["id"] if len(worker_accounts) > 1 else w0

        mode_norm = (strategy_mode or "binary_tree").lower()
        if "dag" in mode_norm or "seq" in mode_norm:
            topology_instruction = (
                "You are orchestrating in **SEQUENTIAL DAG MODE**: Workers execute in strict stage order "
                "(Stage 1 -> Stage 2 -> Stage 3...). Explicitly specify which exact files and summaries from "
                "earlier stages each subsequent stage requires."
            )
        elif "parallel" in mode_norm:
            topology_instruction = (
                "You are orchestrating in **INSTANT PARALLEL MODE**: All workers execute simultaneously. "
                "Design completely self-contained Interface Contracts so no worker sleeps waiting on another worker's file."
            )
        else:
            topology_instruction = (
                "You are orchestrating in **BINARY TREE MODE (L0 Master -> L1 Left/Right Branch Leads -> L2 Leaf Workers)**:\n"
                "   - L1 Left Branch (Stage 1) and L1 Right Branch (Stage 2) can execute SIMULTANEOUSLY if they do not depend on each other.\n"
                "   - A branch or leaf node will ONLY sleep/wait if you list an upstream file in its `required_upstream_files` column (Column 5 of ===MAP_START===).\n"
                "   - Order tasks and file dependencies so independent branches run concurrently while dependent children wait ONLY for their required parent/upstream files."
            )

        directive = (
            f"You are the **Master Software Architect & Dependency Manager** for project `{project_name}`.\n"
            f"Your job is to break down the following software engineering goal into modular tasks for your Subordinate AI Worker Nodes.\n\n"
            f"### ACTIVE TOPOLOGY STRATEGY:\n{topology_instruction}\n\n"
            f"### USER PROJECT GOAL:\n{user_goal}\n\n"
            f"### AVAILABLE SUBORDINATE WORKER NODES (IN EXECUTION ORDER):\n{worker_roster}\n\n"
            "---\n\n"
            "### STRICT DELIMITER & BLOCK NAME RULES (CRITICAL - ZERO TOLERANCE):\n"
            "1. **EXACT NUMBER OF EQUALS SIGNS (`===`):**\n"
            "   - Every single control tag MUST use **EXACTLY THREE equals signs (`===`)** at the start and **EXACTLY THREE equals signs (`===`)** at the end.\n"
            "   - **NEVER** output single equals (`=MAP_START=`) or double equals (`==MAP_START==`).\n"
            "   - **NEVER** place markdown bullet points (`- `, `* `), numbered list prefixes (`1. `), or headings (`#`) on the same line as any `===...===` tag.\n"
            "   - Every `===...===` tag MUST sit completely alone on its own line.\n"
            "2. **EXACT ALLOWED BLOCK NAMES:**\n"
            "   - `===MAP_START===` and `===MAP_END===`\n"
            "   - `===TASK_START: <exact_worker_id>===` and `===TASK_END===`\n"
            "   - Inside worker prompts: `===FILE: <raw_filename.ext>===`, `===SUMMARY===`, and `===END_SUMMARY===`\n\n"
            "---\n\n"
            "### ARCHITECTURAL & FILE DEPENDENCY RULES:\n"
            "1. **6-COLUMN PROJECT ROUTING & DEPENDENCY MAP (`===MAP_START===`):**\n"
            "   - Output one line per file using this exact 6-column pipe-separated format:\n"
            "     `worker_id | raw_filename | relative/path/to/file | stage_order_int | required_upstream_files | required_upstream_summaries`\n"
            "   - `required_upstream_files`: Comma-separated list of exact `raw_filename`s from earlier stages that MUST be uploaded/approved into this worker before it runs (or write `NONE` if this worker does not need any upstream file to start).\n"
            "   - `required_upstream_summaries`: Comma-separated list of upstream `worker_id`s whose `===SUMMARY===` block should be checked/injected into this worker (or write `NONE`).\n"
            "2. **CONTRACT-DRIVEN DEVELOPMENT:**\n"
            "   - Define exact Interface Contracts inside each worker's prompt (exact function signatures, message actions, DOM IDs, exports/imports).\n"
            "3. **STRICT WORKER PROMPT INSTRUCTIONS:**\n"
            "   - Inside EVERY worker prompt you generate, you MUST include the exact `CRITICAL OUTPUT RULES` section instructing that worker to use exact `===FILE: raw_filename.ext===`, `===SUMMARY===`, and `===END_SUMMARY===` tags with **3 equals signs (`===`)** on their own lines.\n\n"
            "---\n\n"
            "### REQUIRED OUTPUT FORMAT FROM YOU (MASTER NODE):\n\n"
            "===MAP_START===\n"
            f"{w0} | contracts.js | src/common/contracts.js | 1 | NONE | NONE\n"
            f"{w1} | background.js | src/background/background.js | 2 | contracts.js | {w0}\n"
            "===MAP_END===\n\n"
            f"===TASK_START: {w0}===\n"
            f"You are building Stage 1 for `{project_name}`.\n"
            "Your assigned raw files to create: contracts.js.\n"
            "Upstream files attached for your reference: NONE.\n\n"
            "[Insert complete Interface Contract: exact message names, payload structures, DOM IDs, and logic specifications]\n\n"
            "CRITICAL OUTPUT RULES (FOLLOW EXACTLY):\n"
            "1. Do NOT use the Artifact viewer. Output all code directly in chat inside standard markdown code blocks.\n"
            "2. Use EXACTLY THREE equals signs (===) for all block tags. NEVER put bullet points (- or *) or numbers before a tag.\n"
            "3. Immediately before each code block, write the exact tag on its own line:\n"
            "===FILE: contracts.js===\n"
            "```javascript\n"
            "// full code here\n"
            "```\n"
            "4. Finish your response with these exact summary tags on their own lines:\n"
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
        cleaned_text = DOMScraper.normalize_delimiters(raw_text or "")

        tasks_by_worker: Dict[str, str] = {}
        routing_map: Dict[str, Dict[str, str]] = {wid: {} for wid in valid_worker_ids}
        assigned_files_display: Dict[str, List[str]] = {wid: [] for wid in valid_worker_ids}
        worker_deps: Dict[str, Dict[str, Any]] = {
            wid: {
                "stage_order": idx + 1,
                "required_files": [],
                "required_summaries": []
            }
            for idx, wid in enumerate(valid_worker_ids)
        }

        raw_id_to_matched: Dict[str, str] = {}
        file_producer_map: Dict[str, str] = {}

        map_blocks = self.map_block_pattern.findall(cleaned_text)
        if map_blocks:
            latest_map = map_blocks[-1]
            for line in latest_map.strip().splitlines():
                line = line.strip()
                if not line or "|" not in line:
                    continue
                parts = [p.strip().strip("`'\"") for p in line.split("|")]
                if len(parts) >= 2:
                    w_id = parts[0]
                    raw_fname = parts[1]
                    rel_path = parts[2] if len(parts) >= 3 else raw_fname
                    matched_id = self._match_worker_id(w_id, valid_worker_ids)
                    if matched_id:
                        raw_id_to_matched[w_id.lower()] = matched_id
                        routing_map[matched_id][raw_fname] = rel_path
                        file_producer_map[raw_fname.lower()] = matched_id
                        if raw_fname not in assigned_files_display[matched_id]:
                            assigned_files_display[matched_id].append(raw_fname)

                        # Parse optional columns 4, 5, 6 (stage_order | required_files | required_summaries)
                        if len(parts) >= 4:
                            try:
                                worker_deps[matched_id]["stage_order"] = int(re.sub(r"[^\d]", "", parts[3]) or worker_deps[matched_id]["stage_order"])
                            except Exception:
                                pass
                        if len(parts) >= 5 and parts[4].upper() != "NONE":
                            for rf in re.split(r"[,;]+", parts[4]):
                                clean_rf = rf.strip().strip("`'\"")
                                if clean_rf and clean_rf.upper() != "NONE" and clean_rf not in worker_deps[matched_id]["required_files"]:
                                    worker_deps[matched_id]["required_files"].append(clean_rf)
                        if len(parts) >= 6 and parts[5].upper() != "NONE":
                            for rs in re.split(r"[,;]+", parts[5]):
                                clean_rs = rs.strip().strip("`'\"")
                                if clean_rs and clean_rs.upper() != "NONE":
                                    matched_sum_id = self._match_worker_id(clean_rs, valid_worker_ids)
                                    if matched_sum_id and matched_sum_id != matched_id and matched_sum_id not in worker_deps[matched_id]["required_summaries"]:
                                        worker_deps[matched_id]["required_summaries"].append(matched_sum_id)

        task_matches = self.task_pattern.findall(cleaned_text)
        for raw_wid, prompt_body in task_matches:
            clean_wid = raw_wid.strip().strip("`'\"<>")
            if clean_wid.lower() == "worker_id" or "[insert complete interface contract" in prompt_body.lower():
                continue
            matched_id = self._match_worker_id(clean_wid, valid_worker_ids)
            if matched_id:
                tasks_by_worker[matched_id] = prompt_body.strip()

        # Sequential fallback if external worker names (e.g. acc_0_Default) didn't match directly
        if not tasks_by_worker and task_matches:
            for idx, (raw_wid, prompt_body) in enumerate(task_matches):
                if idx < len(valid_worker_ids):
                    fallback_id = valid_worker_ids[idx]
                    tasks_by_worker[fallback_id] = prompt_body.strip()

        # Auto-infer required_files & required_summaries when a worker's prompt explicitly mentions an upstream file
        for wid, prompt_body in tasks_by_worker.items():
            prompt_low = prompt_body.lower()
            own_files_low = {f.lower() for f in assigned_files_display.get(wid, [])}
            for fname_low, producer_id in file_producer_map.items():
                if producer_id != wid and fname_low not in own_files_low and fname_low in prompt_low:
                    # Find canonical filename casing
                    orig_fname = next(
                        (f for f in assigned_files_display.get(producer_id, []) if f.lower() == fname_low),
                        fname_low
                    )
                    if orig_fname not in worker_deps[wid]["required_files"]:
                        worker_deps[wid]["required_files"].append(orig_fname)
                    if producer_id not in worker_deps[wid]["required_summaries"]:
                        worker_deps[wid]["required_summaries"].append(producer_id)

        self.last_worker_dependencies = worker_deps
        return tasks_by_worker, routing_map, assigned_files_display

    def get_worker_dependencies(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.last_worker_dependencies)

    def _match_worker_id(self, candidate: str, valid_ids: List[str]) -> str:
        cand_low = candidate.lower().strip()
        for vid in valid_ids:
            if vid.lower() == cand_low:
                return vid
        for vid in valid_ids:
            if vid.lower() in cand_low or cand_low in vid.lower():
                return vid
        match_num = re.search(r"\d+", cand_low)
        if match_num:
            num_val = int(match_num.group())
            if 0 <= num_val < len(valid_ids):
                return valid_ids[num_val]
        return ""