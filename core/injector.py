"""
DOM Injector Module
Uses native system clipboard (MIME Data) and Paste actions to bypass React security,
allowing seamless file uploads before injecting text.
"""

import json
import os
from typing import Any, Callable, Dict, Optional
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QUrl, QMimeData, QTimer

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
                with open(path, "r", encoding="utf-8") as f: return json.load(f)
            except Exception: pass
        return {"platforms": {}}

    def get_platform_config(self, platform: str) -> Dict[str, Any]:
        return self.platforms.get(platform.lower(), {})

    def send_prompt(
        self, page: QWebEnginePage, platform: str, prompt_text: str,
        file_path: Optional[str] = None, callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        
        p_cfg = self.get_platform_config(platform)
        selectors = p_cfg.get("selectors", {})
        input_selector = selectors.get("input_box", "div[contenteditable='true'], textarea")
        send_selector = selectors.get("send_button", "button[type='submit']")

        def _handle_result(result):
            if callback:
                if isinstance(result, dict): callback(result)
                else: callback({"success": False, "raw": result})

        # Core JS to type text and hit send
        js_type_and_send = f"""
        (function() {{
            try {{
                const inputSel = {json.dumps(input_selector)};
                const sendSel = {json.dumps(send_selector)};
                const prompt = {json.dumps(prompt_text)};

                const el = document.querySelector(inputSel);
                if (!el) return {{ success: false, error: "Input not found" }};

                el.focus();
                if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {{
                    el.value = prompt;
                    el.dispatchEvent(new Event('input', {{ bubbles: true, cancelable: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true, cancelable: true }}));
                }} else {{
                    el.innerHTML = '<p>' + prompt.replace(/\\n/g, '<br>') + '</p>';
                    el.dispatchEvent(new Event('input', {{ bubbles: true, cancelable: true }}));
                }}

                setTimeout(() => {{
                    const btn = document.querySelector(sendSel);
                    if (btn && !btn.disabled) btn.click();
                    else el.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
                }}, 300);
                
                return {{ success: true }};
            }} catch (e) {{
                return {{ success: false, error: e.toString() }};
            }}
        }})();
        """

        if file_path and os.path.exists(file_path):
            # 1. Copy the file into the System Clipboard as MIME Data
            clipboard = QApplication.clipboard()
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(file_path)])
            clipboard.setMimeData(mime)

            # 2. Focus the input box via JS
            focus_js = f"document.querySelector({json.dumps(input_selector)}).focus();"

            def on_focused(res):
                # 3. Simulate Ctrl+V (Native Paste) directly into the focused element
                page.triggerAction(QWebEnginePage.WebAction.Paste)
                
                # 4. Wait 3.5 seconds for the platform to upload the file, then type prompt
                # QTimer prevents blocking the UI thread while we wait
                QTimer.singleShot(3500, lambda: page.runJavaScript(js_type_and_send, _handle_result))

            page.runJavaScript(focus_js, on_focused)
        else:
            # If no file, just run the prompt injection normally
            page.runJavaScript(js_type_and_send, _handle_result)
