from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSizePolicy
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from core.session_manager import SessionManager

GEMINI_APP_URL = "https://" + "gemini.google.com/app"


class AIPane(QFrame):
    url_changed_trace = pyqtSignal(str, str)  # (account_id, full_url)
    url_changed = pyqtSignal(str, str)
    move_requested = pyqtSignal(str, int)  # (account_id, direction: -1 for left, +1 for right)

    def __init__(
        self,
        account_id: str,
        account_name: str,
        platform: str,
        profile: QWebEngineProfile,
        start_url: str,
        default_zoom: float = 0.75,
        parent=None
    ):
        super().__init__(parent)
        self.account_id = account_id
        self.account_name = account_name
        self.platform = (platform or "claude").lower()
        self.profile = profile
        self.start_url = GEMINI_APP_URL if (self.platform == "gemini" and "claude.ai" in (start_url or "")) else start_url
        self.zoom_factor = default_zoom
        self._session_mgr = SessionManager()

        # Brand Theme Colors: Claude = Orange (#f97316), Gemini = Blue (#38bdf8)
        self.brand_color = "#38bdf8" if self.platform == "gemini" else "#f97316"

        self._setup_ui()
        self._init_browser()

    def _setup_ui(self):
        self.setObjectName("AIPaneFrame")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(480)
        self.setMinimumHeight(400)
        self.setStyleSheet("""
            QFrame#AIPaneFrame {
                background-color: #09090b;
                border: 1px solid #27272a;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        self.header = QFrame()
        self.header.setFixedHeight(34)
        self.header.setStyleSheet("""
            QFrame { background-color: #18181b; border-bottom: 1px solid #27272a; }
            QLineEdit { background-color: #09090b; color: #a1a1aa; border: 1px solid #27272a; border-radius: 2px; padding: 2px 6px; font-size: 11px; }
            QPushButton { background-color: #27272a; color: #e4e4e7; border: 1px solid #3f3f46; border-radius: 2px; padding: 2px 6px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background-color: #3f3f46; color: #ffffff; }
        """)
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(6, 4, 6, 4)
        hl.setSpacing(4)

        # Far-left corner: Move Left button (◀)
        self.btn_move_left = QPushButton("\u25c0")
        self.btn_move_left.setFixedWidth(22)
        self.btn_move_left.setToolTip("Move Pane Left by 1 Position")
        self.btn_move_left.clicked.connect(lambda: self.move_requested.emit(self.account_id, -1))

        # Status dot + Name colored in platform theme (Claude Orange #f97316 / Gemini Blue #38bdf8)
        self.status_dot = QLabel("\u25cf")
        self.status_dot.setStyleSheet(f"color: {self.brand_color}; font-size: 13px; border: none;")

        self.title_lbl = QLabel(f"{self.account_name} [{self.platform.capitalize()}]")
        self.title_lbl.setStyleSheet(f"color: {self.brand_color}; font-size: 12px; font-weight: bold; border: none;")

        self.url_bar = QLineEdit()
        self.url_bar.setReadOnly(True)
        self.url_bar.setFixedWidth(120)

        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.setFixedWidth(20)
        self.btn_zoom_out.clicked.connect(lambda: self._adjust_zoom(-0.1))

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedWidth(20)
        self.btn_zoom_in.clicked.connect(lambda: self._adjust_zoom(0.1))

        self.btn_reload = QPushButton("\u21bb")
        self.btn_reload.setFixedWidth(22)
        self.btn_reload.setToolTip("Reload Pane")
        self.btn_reload.clicked.connect(self.reload_page)

        # Right corner next to Refresh button: Move Right button (▶)
        self.btn_move_right = QPushButton("\u25b6")
        self.btn_move_right.setFixedWidth(22)
        self.btn_move_right.setToolTip("Move Pane Right by 1 Position")
        self.btn_move_right.clicked.connect(lambda: self.move_requested.emit(self.account_id, 1))

        hl.addWidget(self.btn_move_left)
        hl.addWidget(self.status_dot)
        hl.addWidget(self.title_lbl)
        hl.addWidget(self.url_bar, stretch=1)
        hl.addWidget(self.btn_zoom_out)
        hl.addWidget(self.btn_zoom_in)
        hl.addWidget(self.btn_reload)
        hl.addWidget(self.btn_move_right)

        self.web_view = QWebEngineView(self)
        layout.addWidget(self.header)
        layout.addWidget(self.web_view, stretch=1)

    def _init_browser(self):
        self.page = QWebEnginePage(self.profile, self.web_view)
        self.web_view.setPage(self.page)
        self.web_view.setZoomFactor(self.zoom_factor)
        self._setup_editable_url_bar_and_trace()

        self.web_view.urlChanged.connect(self._on_url_changed)
        self.web_view.loadFinished.connect(self._on_load_finished)

        if self.platform == "gemini":
            self._session_mgr.inject_default_gemini_cookies(self.profile)
            QTimer.singleShot(800, lambda: self.web_view.load(QUrl(self.start_url)))
        else:
            self.web_view.load(QUrl(self.start_url))

    def _on_url_changed(self, qurl: QUrl):
        url_str = qurl.toString()
        short_url = url_str.replace("https://", "").replace("http://", "")
        self.url_bar.setText(short_url)
        self.url_changed.emit(self.account_id, url_str)

    def _on_load_finished(self, ok: bool):
        self.web_view.setZoomFactor(self.zoom_factor)

    def reload_page(self):
        self.web_view.reload()

    def get_page(self) -> QWebEnginePage:
        return self.page

    def set_status(self, status: str):
        color_map = {
            "ready": self.brand_color,
            "running": "#eab308",
            "rate_limited": "#ef4444"
        }
        color = color_map.get(status, self.brand_color)
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 13px; border: none;")

    def cleanup(self):
        try:
            self.web_view.stop()
            self.web_view.setPage(None)
            self.page.deleteLater()
        except Exception:
            pass


    def _setup_editable_url_bar_and_trace(self):
        """Unlocks the URL bar for manual chat import and tracks all live URL changes."""
        from PyQt6.QtWidgets import QLineEdit
        from PyQt6.QtCore import QUrl

        # Find the URL QLineEdit in the header
        url_edit = getattr(self, "url_bar", None) or getattr(self, "url_input", None) or getattr(self, "lbl_url", None)
        if url_edit is None:
            for le in self.findChildren(QLineEdit):
                url_edit = le
                break

        if isinstance(url_edit, QLineEdit):
            self._editable_url_bar = url_edit
            url_edit.setReadOnly(False)
            url_edit.setPlaceholderText("Paste chat URL & press Enter...")
            url_edit.setToolTip("Paste or type an existing Claude/Gemini chat URL and press Enter to import")
            url_edit.setMinimumWidth(135)
            url_edit.setStyleSheet("""
                QLineEdit {
                    background-color: #09090b; color: #e4e4e7; border: 1px solid #3f3f46;
                    border-radius: 3px; padding: 2px 6px; font-size: 10px; font-family: Consolas, monospace;
                }
                QLineEdit:focus {
                    border: 1px solid #38bdf8; background-color: #141417; color: #ffffff;
                }
            """)
            try:
                url_edit.returnPressed.disconnect()
            except Exception:
                pass
            url_edit.returnPressed.connect(self._on_manual_url_entered)

        if hasattr(self, "web_view") and self.web_view is not None:
            try:
                self.web_view.urlChanged.connect(self._on_webview_url_changed)
            except Exception:
                pass

    def _on_manual_url_entered(self):
        from PyQt6.QtCore import QUrl
        bar = getattr(self, "_editable_url_bar", None)
        if bar is None:
            return
        raw = (bar.text() or "").strip()
        if not raw:
            return
        if not raw.startswith("http://") and not raw.startswith("https://"):
            raw = "https://" + raw
        self.navigate_to_url(raw)

    def navigate_to_url(self, target_url: str):
        from PyQt6.QtCore import QUrl
        if not target_url:
            return
        if not target_url.startswith("http://") and not target_url.startswith("https://"):
            target_url = "https://" + target_url
        if hasattr(self, "web_view") and self.web_view is not None:
            self.web_view.setUrl(QUrl(target_url))

    def _on_webview_url_changed(self, qurl):
        full_url = qurl.toString() if hasattr(qurl, "toString") else str(qurl)
        if not full_url:
            return
        bar = getattr(self, "_editable_url_bar", None)
        if bar is not None and not bar.hasFocus():
            # Show clean domain + path without cutting off the chat ID
            clean_disp = full_url.replace("https://", "").replace("http://", "")
            bar.setText(clean_disp)
            bar.setCursorPosition(0)
        try:
            self.url_changed_trace.emit(self.account_id, full_url)
        except Exception:
            pass
