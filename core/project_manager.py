"""
Project Manager Module
Handles saving and loading of project workspaces, URL states, and user notes using JSON.
Acts as the local database for the orchestrator.
"""

import json
import os
import time
import uuid
import shutil
from typing import Dict, Any, List, Optional

class ProjectManager:
    def __init__(self, workspace_dir: Optional[str] = None):
        if workspace_dir is None:
            self.workspace_dir = os.path.join(
                os.path.expanduser("~"), ".nexus_orchestrator", "projects"
            )
        else:
            self.workspace_dir = os.path.expanduser(workspace_dir)
            
        os.makedirs(self.workspace_dir, exist_ok=True)

    def _get_project_path(self, project_id: str) -> str:
        return os.path.join(self.workspace_dir, f"{project_id}.json")

    def create_project(self, name: str, accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Creates a new project structure and saves it to disk."""
        project_id = str(uuid.uuid4())
        
        project_data = {
            "id": project_id,
            "name": name,
            "created_at": time.time(),
            "updated_at": time.time(),
            "notes": f"# {name}\n\nAdd your project notes here...",
            "accounts": accounts
        }
        
        self.save_project(project_data)
        return project_data

    def save_project(self, project_data: Dict[str, Any]) -> bool:
        """Saves the project dictionary to a human-readable JSON file with backup protection."""
        project_data["updated_at"] = time.time()
        filepath = self._get_project_path(project_data["id"])
        
        # Backup existing file before overwrite to prevent data corruption
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
        """Loads a project dictionary from a JSON file."""
        filepath = self._get_project_path(project_id)
        if not os.path.exists(filepath):
            return None
            
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Error] Failed to load project {project_id}: {e}")
            return None

    def list_projects(self) -> List[Dict[str, Any]]:
        """Iterates over the workspace directory and returns metadata for all saved projects."""
        projects = []
        for filename in os.listdir(self.workspace_dir):
            if filename.endswith(".json"):
                project_id = filename.replace(".json", "")
                project_data = self.load_project(project_id)
                if project_data:
                    projects.append(project_data)
                    
        # Sort so newest edited projects appear first
        projects.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return projects

    def update_account_url(self, project_id: str, account_id: str, new_url: str) -> bool:
        """Updates the active chat URL for a specific account so the user can resume later."""
        project = self.load_project(project_id)
        if not project:
            return False
            
        for account in project.get("accounts", []):
            if account.get("id") == account_id or account.get("profile_id") == account_id:
                account["current_url"] = new_url
                return self.save_project(project)
                
        return False
        
    def update_notes(self, project_id: str, notes: str) -> bool:
        """Saves the latest scratchpad notes to the project."""
        project = self.load_project(project_id)
        if not project:
            return False
            
        project["notes"] = notes
        return self.save_project(project)
