"""
Nexus AI Orchestrator - Application Entry Point
Restores previous workspaces or launches Setup Wizard for new projects.
"""
import sys
import os
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.session_manager import SessionManager
from core.project_manager import ProjectManager
from core.injector import DOMInjector
from core.scheduler import TaskScheduler
from ui.onboarding_dialog import OnboardingDialog
from ui.project_hub import ProjectHubDialog
from ui.main_window import MainWindow

def global_exception_handler(exc_type, exc_value, exc_traceback):
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"CRITICAL ERROR:\n{error_msg}")
    if QApplication.instance():
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Fatal Application Error")
        msg_box.setText("An unexpected error occurred.")
        msg_box.setDetailedText(error_msg)
        msg_box.exec()
    sys.exit(1)

sys.excepthook = global_exception_handler

def main():
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    session_manager = SessionManager()
    project_manager = ProjectManager()
    injector = DOMInjector()
    scheduler = TaskScheduler()
    
    main_window = None

    def start_workspace(project_data):
        nonlocal main_window
        main_window = MainWindow(project_data, session_manager, project_manager, injector, scheduler)
        main_window.show()

    def launch_wizard():
        wizard = OnboardingDialog()
        def on_configured(config):
            proj_data = project_manager.create_project(config["name"], config["accounts"])
            start_workspace(proj_data)
        wizard.project_configured.connect(on_configured)
        wizard.exec()

    saved_projects = project_manager.list_projects()
    if saved_projects:
        hub = ProjectHubDialog(saved_projects)
        hub.open_project.connect(start_workspace)
        hub.create_new_clicked.connect(launch_wizard)
        if not hub.exec(): sys.exit(0)
    else:
        launch_wizard()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
