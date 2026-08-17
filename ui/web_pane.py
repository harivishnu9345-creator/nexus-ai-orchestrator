"""
Web Pane UI Module
Defines individual AI account pane with God-Mode File Interceptor subclass.
"""
import os
from PyQt6.QtCore import QUrl, Qt, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

class AutoUploadPage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.auto_file_path = None

    def chooseFiles(self, mode, oldFiles, acceptedMimeTypes):
        if self.auto_file_path and os.path.exists(self.auto_file_path):
            file_to_upload = self.auto_file_path
            self.auto_file_path = None
            return [file_to_upload]
        return super().chooseFiles(mode, oldFiles, acceptedMimeTypes)

class AIPane(QWidget):
    url_changed = pyqtSignal(str, str) 

    def __init__(self, account_id: str, account_name: str, provider: str, profile: QWebEngineProfile, start_url: str, default_zoom: float = 0.75, parent=None):
        super().__init__(parent)
        self.account_id = account_id
        self.account_name = account_name
        self.provider = provider.capitalize()
        self.current_zoom = default_zoom

        self._setup_ui()
        
        self.page = AutoUploadPage(profile, self.web_view)
        self.web_view.setPage(self.page)
        self.web_view.setZoomFactor(self.current_zoom)
        self.web_view.load(QUrl(start_url))
        self.web_view.urlChanged.connect(self._on_url_changed)

    def _setup_ui(self):
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(400, 400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = QFrame()
        self.header.setStyleSheet("""
            QFrame { background-color: #18181b; border-bottom: 1px solid #27272a; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QLabel { color: #e4e4e7; font-family: 'Segoe UI', sans-serif; }
            QPushButton { background: transparent; color: #a1a1aa; border: none; font-weight: bold; padding: 4px 8px; border-radius: 4px; }
            QPushButton:hover { background-color: #27272a; color: #f4f4f5; }
        """)
        
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #22c55e; font-size: 14px;")
        
        self.title_label = QLabel(f"{self.account_name}  ·  {self.provider}")
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        
        self.url_label = QLabel("")
        self.url_label.setStyleSheet("color: #71717a; font-size: 11px;")

        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_in = QPushButton("+")
        self.btn_reload = QPushButton("↻")
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_reload.clicked.connect(self.reload_page)

        header_layout.addWidget(self.status_dot)
        header_layout.addWidget(self.title_label)
        header_layout.addSpacing(10)
        header_layout.addWidget(self.url_label)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_zoom_out)
        header_layout.addWidget(self.btn_zoom_in)
        header_layout.addWidget(self.btn_reload)

        self.web_view = QWebEngineView()
        layout.addWidget(self.header)
        layout.addWidget(self.web_view, stretch=1)

    def _on_url_changed(self, url: QUrl):
        url_str = url.toString()
        display_url = url_str.replace("https://", "").replace("www.", "")
        if len(display_url) > 35: display_url = display_url[:32] + "..."
        self.url_label.setText(display_url)
        self.url_changed.emit(self.account_id, url_str)

    def set_status(self, state: str):
        colors = {"ready": "#22c55e", "running": "#eab308", "rate_limited": "#ef4444"}
        color = colors.get(state, "#a1a1aa")
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")

    def zoom_in(self):
        self.current_zoom += 0.1
        self.web_view.setZoomFactor(self.current_zoom)

    def zoom_out(self):
        self.current_zoom = max(0.25, self.current_zoom - 0.1)
        self.web_view.setZoomFactor(self.current_zoom)

    def reload_page(self):
        self.web_view.reload()

    def get_page(self) -> AutoUploadPage:
        return self.page
