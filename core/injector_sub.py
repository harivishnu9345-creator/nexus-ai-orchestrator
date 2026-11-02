import json
import os
from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal, QUrl, QMimeData, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWebEngineCore import QWebEnginePage


class SubInjector(QObject):
    """Dedicated injector for handling multi-file OS clipboard relays."""
    progress_update = pyqtSignal(str)
    injection_complete = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_active = False

    def inject_multiple_files(
        self,
        page: QWebEnginePage,
        prompt_text: str,
        file_paths: list,
        selectors: dict,
        view: Any = None
    ):
        if self._is_active:
            self.injection_complete.emit({"success": False, "error": "Sub-injector is currently locked."})
            return

        self._is_active = True
        input_selector = selectors.get("input_box", "div[contenteditable='true'], textarea")
        valid_paths = [f for f in (file_paths or []) if f and os.path.exists(f)]

        if valid_paths:
            self.progress_update.emit(f"Locking OS clipboard for {len(valid_paths)} file(s)...")
            mime_data = QMimeData()
            urls = [QUrl.fromLocalFile(f) for f in valid_paths]
            mime_data.setUrls(urls)
            QGuiApplication.clipboard().setMimeData(mime_data)

        if view is not None:
            view.setFocus()

        js_click_bar = f"""
        (function() {{
            const el = document.querySelector({json.dumps(input_selector)});
            if (!el) return false;
            el.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true, cancelable: true }}));
            el.focus();
            el.dispatchEvent(new MouseEvent('mouseup', {{ bubbles: true, cancelable: true }}));
            el.click();
            if (el.classList.contains("ql-blank")) el.classList.remove("ql-blank");
            document.execCommand("selectAll", false, null);
            document.execCommand("delete", false, null);
            return true;
        }})();
        """

        def _on_bar_focused(found):
            if not found:
                self._is_active = False
                self.progress_update.emit("Error: Chat input bar not found.")
                self.injection_complete.emit({"success": False, "error": "Chat input bar not found."})
                return

            if view is not None:
                view.setFocus()

            if valid_paths:
                self.progress_update.emit(f"Pasting {len(valid_paths)} physical file(s) into node...")
                page.triggerAction(QWebEnginePage.WebAction.Paste)
                self.progress_update.emit("Waiting 5s for UI to render file attachments...")
                QTimer.singleShot(5000, lambda: self._send_text_and_submit(page, prompt_text, input_selector))
            else:
                QTimer.singleShot(250, lambda: self._send_text_and_submit(page, prompt_text, input_selector))

        page.runJavaScript(js_click_bar, lambda res: QTimer.singleShot(250, lambda: _on_bar_focused(res)))

    def _send_text_and_submit(self, page: QWebEnginePage, prompt_text: str, input_selector: str):
        self.progress_update.emit("Dispatching contract prompt & clicking Send...")
        js_finish = f"""
        (function() {{
            try {{
                const el = document.querySelector({json.dumps(input_selector)});
                if (!el) return {{ success: false, error: "Input lost focus" }};
                el.focus();
                if (el.classList.contains("ql-blank")) el.classList.remove("ql-blank");
                document.execCommand("insertText", false, {json.dumps(prompt_text)});
                el.dispatchEvent(new Event('input', {{ bubbles: true, cancelable: true }}));
                setTimeout(() => {{
                    const btn = document.querySelector(
                        'button[aria-label*="Send" i]:not([disabled]), button[data-testid="send-button"]:not([disabled])'
                    );
                    if (btn) {{
                        btn.click();
                    }} else {{
                        el.dispatchEvent(new KeyboardEvent('keydown', {{
                            key: 'Enter', code: 'Enter', keyCode: 13,
                            bubbles: true, cancelable: true, composed: true
                        }}));
                    }}
                }}, 600);
                return {{ success: true }};
            }} catch (e) {{
                return {{ success: false, error: e.toString() }};
            }}
        }})();
        """
        page.runJavaScript(js_finish, lambda res: QTimer.singleShot(800, lambda: self._finalize_injection(res)))

    def _finalize_injection(self, result):
        self._is_active = False
        if isinstance(result, dict) and result.get("success"):
            self.progress_update.emit("Relay stage successfully fired.")
            self.injection_complete.emit({"success": True})
        else:
            err_msg = result.get("error", "DOM Interaction Failed") if isinstance(result, dict) else "DOM Interaction Failed"
            self.progress_update.emit(f"Error: {err_msg}")
            self.injection_complete.emit({"success": False, "error": err_msg})
