import json
import os
import time
import uuid
import shutil
from typing import Dict, Any, List, Optional


class ProjectManager:
    def __init__(self, workspace_dir: Optional[str] = None):
        if workspace_dir is None:
            self.workspace_dir = os.path.join(os.path.expanduser("~"), ".nexus_orchestrator", "projects")
        else:
            self.workspace_dir = os.path.expanduser(workspace_dir)
        os.makedirs(self.workspace_dir, exist_ok=True)

    def _get_project_path(self, project_id: str) -> str:
        return os.path.join(self.workspace_dir, f"{project_id}.json")

    def find_project_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        clean = (name or "").strip().lower()
        if not clean:
            return None
        for proj in self.list_projects():
            if proj.get("name", "").strip().lower() == clean:
                return proj
        return None

    def create_project(self, name: str, accounts: List[Dict[str, Any]], auto_save: bool = False, **kwargs)-> Dict[str, Any]:
        project_id = str(uuid.uuid4())
        project_data = {
            "id": project_id,
            "name": name,
            "created_at": time.time(),
            "updated_at": time.time(),
            "notes": f"# {name}\n\nAdd your project notes here...",
            "accounts": accounts,
            "task_history": [],
            "pipeline_sessions": []
        }
        self.save_project(project_data)
        return project_data

    def save_project(self, project_data: Dict[str, Any], accounts: Optional[List[Dict[str, Any]]] = None) -> bool:
        if isinstance(project_data, str):
            project_data = {"name": project_data, "accounts": accounts or []}

        if "id" not in project_data or not project_data["id"]:
            existing = self.find_project_by_name(project_data.get("name", ""))
            project_data["id"] = existing["id"] if existing else str(uuid.uuid4())

        if "created_at" not in project_data:
            project_data["created_at"] = time.time()
        if "task_history" not in project_data:
            project_data["task_history"] = []
        if "pipeline_sessions" not in project_data:
            project_data["pipeline_sessions"] = []

        project_data["updated_at"] = time.time()
        filepath = self._get_project_path(project_data["id"])
        if os.path.exists(filepath):
            try:
                shutil.copy2(filepath, filepath + ".bak")
            except Exception:
                pass
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(project_data, f, indent=4)
            return True
        except Exception as e:
            print(f"[Error] Failed to save project: {e}")
            return False

    def load_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        filepath = self._get_project_path(project_id)
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                for acc in data.get("accounts", []):
                    if (acc.get("platform") != "gemini" and ("login" in acc.get("current_url", "") or "google" in acc.get("current_url", ""))):
                        acc["current_url"] = "https://claude.ai/new"
                if "task_history" not in data:
                    data["task_history"] = []
                if "pipeline_sessions" not in data:
                    data["pipeline_sessions"] = []
                return data
        except Exception as e:
            print(f"[Error] Failed to load project {project_id}: {e}")
            return None

    def list_projects(self) -> List[Dict[str, Any]]:
        projects = []
        for filename in os.listdir(self.workspace_dir):
            if filename.endswith(".json"):
                project_data = self.load_project(filename.replace(".json", ""))
                if project_data:
                    projects.append(project_data)
        projects.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return projects

    def load_projects(self) -> List[Dict[str, Any]]:
        return self.list_projects()

    def update_account_url(self, project_id: str, account_id: str, new_url: str) -> bool:
        if not new_url.strip() or "login" in new_url.lower() or "accounts.google.com" in new_url.lower():
            return False

        project = self.load_project(project_id)
        if not project:
            return False

        for account in project.get("accounts", []):
            if account.get("id") == account_id or account.get("profile_id") == account_id:
                account["current_url"] = new_url
                return self.save_project(project)
        return False

    def save_task_history(self, project_id: str, serialized_tasks: List[Dict[str, Any]]) -> bool:
        project = self.load_project(project_id)
        if not project:
            return False
        project["task_history"] = serialized_tasks
        return self.save_project(project)

    def save_pipeline_sessions(self, project_id: str, sessions: List[Dict[str, Any]]) -> bool:
        project = self.load_project(project_id)
        if not project:
            return False
        project["pipeline_sessions"] = sessions
        return self.save_project(project)

    def save_project(self, project_data: dict, force_disk: bool = True, custom_file_path: str = None) -> str:
        """Compatible wrapper that saves using the native v1.8 schema AND supports custom JSON export."""
        if not isinstance(project_data, dict):
            return ""
        # Ensure both "id" and "project_id" keys are synchronized
        proj_id = project_data.get("id") or project_data.get("project_id") or f"proj_{uuid.uuid4().hex[:8]}"
        project_data["id"] = proj_id
        project_data["project_id"] = proj_id

        serializable = {k: v for k, v in project_data.items() if not str(k).startswith("_")}

        # 1. Save into the software's internal project storage
        internal_dir = getattr(self, "projects_dir", None) or getattr(self, "storage_dir", None) or os.path.expanduser("~/.nexus_orchestrator/projects")
        os.makedirs(internal_dir, exist_ok=True)
        internal_path = os.path.join(internal_dir, f"{proj_id}.json")
        try:
            with open(internal_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2)
        except Exception as e:
            print(f"[INTERNAL SAVE ERROR] {e}")

        # Also call original v1.8 save method if present (e.g. _save_index or save_workspace)
        if hasattr(self, "save_workspace"):
            try:
                self.save_workspace(project_data)
            except Exception:
                pass
        elif hasattr(self, "_save_to_disk"):
            try:
                self._save_to_disk(proj_id, serializable)
            except Exception:
                pass

        # 2. If user clicked "Save Project As..." (custom_file_path), also write to that exact external JSON file
        if custom_file_path:
            with open(custom_file_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2)
            return custom_file_path

        return internal_path

    def load_project_from_file(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            proj_id = data.get("id") or data.get("project_id") or f"proj_{uuid.uuid4().hex[:8]}"
            data["id"] = proj_id
            data["project_id"] = proj_id
            if "name" not in data:
                data["name"] = os.path.splitext(os.path.basename(file_path))[0]
            data["_is_saved"] = True
            data["_is_dirty"] = False
            data["_file_path"] = os.path.abspath(file_path)
            # Sync into internal vault so Project Hub sees it too
            self.save_project(data, force_disk=True)
            return data
        except Exception as e:
            print(f"[LOAD JSON ERROR] {e}")
            return None

    def find_project_by_name(self, name: str):
        clean_target = (name or "").strip().lower()
        if hasattr(self, "list_projects"):
            for p in self.list_projects():
                if p.get("name", "").strip().lower() == clean_target:
                    return p
        elif hasattr(self, "get_all_projects"):
            for p in self.get_all_projects():
                if p.get("name", "").strip().lower() == clean_target:
                    return p
        return None


_orig_pm_create_project = ProjectManager.create_project
def _patched_pm_create_project(self, name, selected_accounts, auto_save: bool = False, **kwargs):
    import uuid
    from datetime import datetime
    if not auto_save:
        proj_id = f"proj_{uuid.uuid4().hex[:8]}"
        project_data = {
            "id": proj_id,
            "project_id": proj_id,
            "name": name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "master_node_id": selected_accounts[0]["id"] if selected_accounts else None,
            "accounts": selected_accounts,
            "task_history": [],
            "pipeline_sessions": [],
            "file_vault": {"files": [], "folders": []},
            "_is_saved": False,
            "_is_dirty": True
        }
        if not hasattr(self, "_memory_projects"):
            self._memory_projects = {}
        self._memory_projects[proj_id] = project_data
        return project_data

    res = _orig_pm_create_project(self, name, selected_accounts)
    if isinstance(res, dict):
        proj_id = res.get("id") or res.get("project_id") or f"proj_{uuid.uuid4().hex[:8]}"
        res["id"] = proj_id
        res["project_id"] = proj_id
        res["_is_saved"] = True
        res["_is_dirty"] = False
    return res

ProjectManager.create_project = _patched_pm_create_project

