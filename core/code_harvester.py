import os
import re
import subprocess
from typing import List
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

        self.file_block_pattern = re.compile(
            r"===\s*FILE\s*:\s*([^\n=]+?)\s*===\s*\n+```[^\n]*\n(.*?)```",
            re.DOTALL | re.IGNORECASE
        )

    def get_project_build_dir(self, project_name: str) -> str:
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", project_name.strip())
        target_dir = os.path.join(self.base_output_dir, safe_name)
        os.makedirs(target_dir, exist_ok=True)
        return target_dir

    def parse_and_write_files(self, raw_text: str, project_name: str) -> List[str]:
        build_dir = self.get_project_build_dir(project_name)
        created_files = []
        matches = self.file_block_pattern.findall(raw_text)
        
        for rel_path, code_content in matches:
            clean_rel = os.path.normpath(rel_path.strip().strip("`'\"/\\"))
            if clean_rel.startswith("..") or os.path.isabs(clean_rel):
                continue
            full_path = os.path.join(build_dir, clean_rel)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(code_content.strip() + "\n")
            created_files.append(clean_rel)
            print(f"[HARVESTER] 💾 Materialized file: {full_path}")

        return created_files

    def open_in_vscode(self, project_name: str):
        build_dir = self.get_project_build_dir(project_name)
        try: subprocess.Popen(["code", build_dir], shell=True)
        except Exception: os.startfile(build_dir)