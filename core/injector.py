import json
import os
from typing import Any, Callable, Dict, Optional
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtCore import QMimeData, QUrl, QTimer

class DOMInjector:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.json")
        self.config = self._load_config(config_path)
        self.platforms = self.config.get("platforms", {})

    def _load_config(self, path: str) -> Dict[str, Any]:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"platforms": {}}

    def get_platform_config(self, platform: str) -> Dict[str, Any]:
        return self.platforms.get(platform.lower(), {})

    def send_prompt(
        self, page: QWebEnginePage, platform: str, prompt_text: str,
        file_path: Optional[str] = None, main_hwnd: Optional[int] = None,
        view: Optional[Any] = None,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        p_cfg = self.get_platform_config(platform)
        selectors = p_cfg.get("selectors", {})
        input_selector = selectors.get("input_box", "div[contenteditable='true'], textarea")

        def _handle_result(result):
            if callback:
                if isinstance(result, dict):
                    callback(result)
                else:
                    callback({"success": False, "raw": result})

        if file_path and os.path.exists(file_path):
            print("[INJECTOR] File detected. Activating pane and targeting chat bar.")

            # STEP 1: Load file into Native OS Clipboard
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(file_path)])
            QGuiApplication.clipboard().setMimeData(mime)

            # STEP 2: Force Qt physical focus onto the target QWebEngineView pane
            if view is not None:
                view.setFocus()

            # STEP 3: Simulate a mouse click on the chat bar to wake React state
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

            def on_clicked(success):
                if not success:
                    print("[INJECTOR] Failed to find chat bar to click.")
                    return _handle_result({"success": False, "error": "Chat bar not found"})

                if view is not None:
                    view.setFocus()

                # STEP 4: Fire native paste now that both View and DOM are focused
                page.triggerAction(QWebEnginePage.WebAction.Paste)

                # STEP 5: Wait 5 seconds for React file pill render, then append prompt and send
                def finish_typing():
                    js_finish = f"""
                    (function() {{
                        const el = document.querySelector({json.dumps(input_selector)});
                        if (!el) return {{ success: false, error: "Input lost focus" }};
                        el.focus();
                        document.execCommand("insertText", false, {json.dumps(prompt_text)});
                        el.dispatchEvent(new Event('input', {{ bubbles: true, cancelable: true }}));
                        setTimeout(() => {{
                            const btn = document.querySelector('button[aria-label*="Send" i]:not([disabled]), button[data-testid="send-button"]:not([disabled])');
                            if (btn) btn.click();
                            else el.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true, cancelable: true, composed: true }}));
                        }}, 500);
                        return {{ success: true }};
                    }})();
                    """
                    page.runJavaScript(js_finish, _handle_result)

                QTimer.singleShot(5000, finish_typing)

            page.runJavaScript(js_click_bar, lambda res: QTimer.singleShot(250, lambda: on_clicked(res)))

        else:
            print("[INJECTOR] No file attached. Using fast JS injection.")
            js_type_and_send = f"""
            (function() {{
                try {{
                    const el = document.querySelector({json.dumps(input_selector)});
                    if (!el) return {{ success: false, error: "Input not found" }};
                    el.focus();
                    if (el.classList.contains("ql-blank")) el.classList.remove("ql-blank");
                    document.execCommand("selectAll", false, null);
                    document.execCommand("delete", false, null);
                    document.execCommand("insertText", false, {json.dumps(prompt_text)});
                    el.dispatchEvent(new Event('input', {{ bubbles: true, cancelable: true }}));
                    setTimeout(() => {{
                        const btn = document.querySelector('button[aria-label*="Send" i]:not([disabled]), button[data-testid="send-button"]:not([disabled])');
                        if (btn) btn.click();
                        else el.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true, cancelable: true, composed: true }}));
                    }}, 400);
                    return {{ success: true }};
                }} catch (e) {{ return {{ success: false, error: e.toString() }}; }}
            }})();
            """
            page.runJavaScript(js_type_and_send, _handle_result)