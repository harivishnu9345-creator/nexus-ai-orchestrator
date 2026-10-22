import os
from PyQt6.QtCore import QUrl, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
)
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

    def __init__(
        self, account_id: str, account_name: str, provider: str,
        profile: QWebEngineProfile, start_url: str, default_zoom: float = 0.80, parent=None
    ):
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
        self.setMinimumSize(460, 420)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.container = QFrame()
        self.container.setObjectName("PaneFrame")
        self.container.setStyleSheet("""
            QFrame#PaneFrame {
                background-color: #ffffff;
                border: 1px solid #9a9790;
                border-radius: 2px;
            }
        """)
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        # Classic Dark GTK Window Header Bar
        self.header = QFrame()
        self.header.setFixedHeight(34)
        self.header.setStyleSheet("""
            QFrame {
                background-color: #35393c;
                border-bottom: 1px solid #1c1f21;
            }
            QLabel {
                color: #eeeeec;
                font-family: 'Ubuntu', 'DejaVu Sans', sans-serif;
                border: none;
            }
            QPushButton {
                background-color: #454a4d;
                color: #eeeeec;
                border: 1px solid #232629;
                font-weight: bold;
                padding: 2px 7px;
                border-radius: 2px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #565c60;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #2b2e30;
            }
        """)

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(6)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #73d216; font-size: 13px;")

        self.title_label = QLabel(f"{self.account_name} [{self.provider}]")
        self.title_label.setStyleSheet("font-size: 12px; font-weight: bold;")

        self.url_label = QLabel("")
        self.url_label.setStyleSheet("""
            background-color: #232629;
            color: #babdb6;
            font-family: 'DejaVu Sans Mono', 'Consolas', monospace;
            font-size: 10px;
            padding: 2px 6px;
            border: 1px solid #181a1c;
            border-radius: 2px;
        """)

        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_in = QPushButton("+")
        self.btn_reload = QPushButton("↻")
        self.btn_zoom_out.setToolTip("Zoom Out")
        self.btn_zoom_in.setToolTip("Zoom In")
        self.btn_reload.setToolTip("Reload Node")

        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_reload.clicked.connect(self.reload_page)

        header_layout.addWidget(self.status_dot)
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.url_label, stretch=1)
        header_layout.addWidget(self.btn_zoom_out)
        header_layout.addWidget(self.btn_zoom_in)
        header_layout.addWidget(self.btn_reload)

        self.web_view = QWebEngineView()
        layout.addWidget(self.header)
        layout.addWidget(self.web_view, stretch=1)
        outer_layout.addWidget(self.container)

    def _on_url_changed(self, url: QUrl):
        url_str = url.toString()
        display_url = url_str.replace("https://", "").replace("www.", "")
        if len(display_url) > 34:
            display_url = display_url[:31] + "..."
        self.url_label.setText(display_url)
        self.url_changed.emit(self.account_id, url_str)

    def set_status(self, state: str):
        colors = {"ready": "#73d216", "running": "#f57900", "rate_limited": "#cc0000"}
        color = colors.get(state, "#888a85")
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 13px;")

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

    def cleanup(self):
        self.web_view.setPage(None)
        if self.page:
            self.page.deleteLater()
            self.page = None