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

    def create_project(self, name: str, accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
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
                    if "login" in acc.get("current_url", "") or "google" in acc.get("current_url", ""):
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

