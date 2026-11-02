import sys
import json
import os
from PyQt6.QtWidgets import QApplication, QDialog
from core.project_manager import ProjectManager
from ui.project_hub import ProjectHubDialog
from ui.onboarding_dialog import OnboardingDialog
from ui.main_window import MainWindow


def load_config(config_path="config.json"):
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config.json: {e}")

    return {
        "app": {
            "name": "Nexus AI Orchestrator",
            "version": "1.8.0",
            "default_zoom": 0.75,
            "storage_root": "~/.nexus_orchestrator"
        },
        "platforms": {
            "claude": {
                "name": "Claude",
                "home_url": "https://claude.ai/new",
                "selectors": {
                    "input_box": "div[contenteditable='true']",
                    "send_button": "button[aria-label='Send Message'], button[aria-label='Send message']",
                    "stop_button": "button[aria-label='Stop response']"
                }
            }
        }
    }


def get_saved_projects(project_mgr: ProjectManager) -> list:
    for method_name in ("load_projects", "get_projects", "list_projects"):
        if hasattr(project_mgr, method_name):
            res = getattr(project_mgr, method_name)()
            if isinstance(res, list):
                return res
    if hasattr(project_mgr, "projects") and isinstance(project_mgr.projects, list):
        return project_mgr.projects
    return []


def save_workspace_project(project_mgr: ProjectManager, proj_dict: dict):
    if hasattr(project_mgr, "save_project"):
        try:
            project_mgr.save_project(proj_dict)
        except TypeError:
            project_mgr.save_project(proj_dict.get("name", "Untitled"), proj_dict.get("accounts", []))


def select_workspace_before_boot(project_mgr: ProjectManager):
    """
    1. ALWAYS opens ProjectHubDialog (Saved Swarm Workspaces) first.
    2. Only opens OnboardingDialog if the user clicks '+ New Workspace'.
    """
    selected_workspace = {"data": None, "create_new": False}

    projects = get_saved_projects(project_mgr)

    # Always show ProjectHubDialog first
    hub = ProjectHubDialog(projects)
    hub.open_project.connect(lambda proj: selected_workspace.update({"data": proj}))
    hub.create_new_clicked.connect(lambda: selected_workspace.update({"create_new": True}))
    hub.exec()

    # Case A: User clicked "Load Workspace" on an existing project
    if selected_workspace["data"]:
        return selected_workspace["data"]

    # Case B: User closed the dialog without clicking "+ New Workspace"
    if not selected_workspace["create_new"]:
        return None

    # Case C: User explicitly clicked "+ New Workspace" -> Open OnboardingDialog
    onboard = OnboardingDialog()
    onboard.project_configured.connect(lambda proj: selected_workspace.update({"data": proj}))
    if onboard.exec() == QDialog.DialogCode.Accepted and selected_workspace["data"]:
        proj = selected_workspace["data"]
        save_workspace_project(project_mgr, proj)
        return proj

    return None


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    project_mgr = ProjectManager()
    workspace_data = select_workspace_before_boot(project_mgr)

    if not workspace_data:
        sys.exit(0)

    config = load_config()
    window = MainWindow(config, workspace_data=workspace_data)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
