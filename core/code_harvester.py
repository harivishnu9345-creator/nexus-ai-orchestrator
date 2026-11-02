import os
import re
import zipfile
import subprocess
from typing import Dict, List, Tuple
from PyQt6.QtCore import QObject, pyqtSignal


class CodeHarvester(QObject):
    harvest_finished = pyqtSignal(str, list)

    def __init__(self, base_output_dir: str = None):
        super().__init__()
        if base_output_dir is None:
            self.base_output_dir = os.path.join(os.path.expanduser("~"), "Nexus_Compiled_Workspaces")
        else:
            self.base_output_dir = base_output_dir
        os.makedirs(self.base_output_dir, exist_ok=True)

        self.project_map: Dict[str, Dict[str, str]] = {}

        # Tier 1: Explicit ===FILE: filename.ext=== followed by ``` block (allows optional language/header lines)
        self.file_block_pattern = re.compile(
            r"===\s*FILE\s*:\s*([^\n=]+?)\s*===\s*(?:[^\n`]*\n)*?```[^\n]*\n(.*?)```",
            re.DOTALL | re.IGNORECASE
        )

        # Tier 2: Markdown heading or bold filename (e.g. ### popup.html or **manifest.json**) before ``` block
        self.named_header_pattern = re.compile(
            r"(?:^|\n)[#*`\s]*([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]{1,8})[*`:\s]*\n+(?:[^\n`]*\n){0,2}?```[^\n]*\n(.*?)```",
            re.DOTALL
        )

        # Tier 3: Any raw ``` code block (used to map in-order or by content against worker's assigned files)
        self.any_code_block_pattern = re.compile(
            r"```[^\n]*\n(.*?)```",
            re.DOTALL
        )

        self.summary_pattern = re.compile(
            r"===\s*SUMMARY\s*===\s*(.*?)===\s*END_SUMMARY\s*===",
            re.DOTALL | re.IGNORECASE
        )

    def set_project_map(self, routing_map: Dict[str, Dict[str, str]]):
        self.project_map = routing_map or {}

    def get_project_build_dir(self, project_name: str) -> str:
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", (project_name or "Default_Build").strip())
        target_dir = os.path.join(self.base_output_dir, safe_name)
        os.makedirs(target_dir, exist_ok=True)
        return target_dir

    def _extract_file_pairs(self, raw_text: str, worker_map: Dict[str, str]) -> List[Tuple[str, str]]:
        # Pass 1: Strict ===FILE: name=== blocks
        matches = self.file_block_pattern.findall(raw_text)
        if matches:
            return matches

        # Pass 2: Header/Bold filename immediately preceding code block
        header_matches = self.named_header_pattern.findall(raw_text)
        if header_matches:
            return header_matches

        # Pass 3: Fallback matching against the worker's assigned files from Master [MAP]
        code_blocks = [b.strip() for b in self.any_code_block_pattern.findall(raw_text) if b.strip()]
        if not code_blocks or not worker_map:
            return []

        assigned_raw_names = list(worker_map.keys())
        paired: List[Tuple[str, str]] = []

        # If number of code blocks equals number of assigned files for this worker, pair them 1-to-1
        if len(code_blocks) == len(assigned_raw_names):
            return list(zip(assigned_raw_names, code_blocks))

        # Otherwise match by searching for the filename before each code block or by index
        for idx, block in enumerate(code_blocks):
            if idx < len(assigned_raw_names):
                paired.append((assigned_raw_names[idx], block))

        return paired

    def parse_and_write_files(self, raw_text: str, project_name: str, account_id: str = None) -> List[str]:
        build_dir = self.get_project_build_dir(project_name)
        created_files = []
        if not raw_text:
            return created_files

        worker_map = self.project_map.get(account_id, {}) if account_id else {}
        # Also build a global lookup across all workers in case account_id wasn't matched
        global_map = {}
        for w_dict in self.project_map.values():
            if isinstance(w_dict, dict):
                global_map.update(w_dict)

        active_map = worker_map if worker_map else global_map
        matches = self._extract_file_pairs(raw_text, active_map)

        for raw_path, code_content in matches:
            clean_name = raw_path.strip().strip("`'\"/\\*")
            mapped_rel = (
                active_map.get(clean_name)
                or active_map.get(os.path.basename(clean_name))
                or global_map.get(clean_name)
                or global_map.get(os.path.basename(clean_name))
                or clean_name
            )
            clean_rel = os.path.normpath(mapped_rel.strip().strip("`'\"/\\"))

            if clean_rel.startswith("..") or os.path.isabs(clean_rel):
                clean_rel = os.path.basename(clean_rel)

            full_path = os.path.join(build_dir, clean_rel)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(code_content.strip() + "\n")
            created_files.append(full_path)
            print(f"[HARVESTER] Materialized file: {full_path}")

        self.harvest_finished.emit(project_name, created_files)
        return created_files

    def extract_summary(self, raw_text: str) -> str:
        if not raw_text:
            return ""
        matches = self.summary_pattern.findall(raw_text)
        if matches:
            return matches[-1].strip()
        return ""

    def create_project_zip(self, project_name: str) -> str:
        build_dir = self.get_project_build_dir(project_name)
        zip_path = f"{build_dir}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(build_dir):
                for file in files:
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, build_dir)
                    zf.write(abs_path, rel_path)
        print(f"[HARVESTER] Built project archive: {zip_path}")
        return zip_path

    def open_in_vscode(self, project_name: str):
        build_dir = self.get_project_build_dir(project_name)
        try:
            subprocess.Popen(["code", build_dir], shell=True)
        except Exception:
            os.startfile(build_dir)
