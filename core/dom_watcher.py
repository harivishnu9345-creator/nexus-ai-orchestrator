import json
import time
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWebEngineCore import QWebEnginePage


class DOMWatcher(QObject):
    """Watches the DOM to detect when an AI node finishes streaming its response."""
    generation_complete = pyqtSignal(str)  # Emits account_id when done

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_watches = {}

    def start_watching(self, account_id: str, page: QWebEnginePage, platform: str, config: dict):
        """Starts a 2-second polling timer for the given node with startup grace period."""
        if account_id in self.active_watches:
            self.stop_watching(account_id)

        platform_config = (config or {}).get("platforms", {}).get((platform or "").lower(), {})
        selectors = platform_config.get("selectors", {})
        stop_selector = selectors.get("stop_button", "button[aria-label*='Stop' i]")

        timer = QTimer(self)
        self.active_watches[account_id] = {
            "timer": timer,
            "page": page,
            "initial_length": None,
            "last_length": 0,
            "stable_count": 0,
            "saw_generating": False,
            "started_at": time.time(),
            "stop_selector": stop_selector
        }

        timer.timeout.connect(lambda aid=account_id: self._poll_dom(aid))
        timer.start(2000)

    def stop_watching(self, account_id: str):
        if account_id in self.active_watches:
            self.active_watches[account_id]["timer"].stop()
            del self.active_watches[account_id]

    def _poll_dom(self, account_id: str):
        watch_data = self.active_watches.get(account_id)
        if not watch_data:
            return

        page = watch_data["page"]
        stop_sel_json = json.dumps(watch_data["stop_selector"])

        script = f"""
        (() => {{
            const customSel = {stop_sel_json};
            let isGenerating = false;
            try {{
                if (customSel) {{
                    const customBtn = document.querySelector(customSel);
                    if (customBtn && customBtn.getBoundingClientRect().width > 0) {{
                        isGenerating = true;
                    }}
                }}
            }} catch (e) {{}}

            if (!isGenerating) {{
                const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
                isGenerating = btns.some(b => {{
                    const r = b.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) return false;
                    const aria = (
                        (b.getAttribute("aria-label") || "") + " " +
                        (b.getAttribute("mattooltip") || "") + " " +
                        (b.innerText || "")
                    ).toLowerCase().trim();
                    return (
                        aria.includes("stop response") ||
                        aria.includes("stop generating") ||
                        aria === "stop"
                    );
                }});
            }}

            const textLen = document.body ? (document.body.innerText || "").length : 0;
            return {{ isGenerating: isGenerating, length: textLen }};
        }})();
        """
        page.runJavaScript(script, lambda res, aid=account_id: self._evaluate_state(aid, res))

    def _evaluate_state(self, account_id: str, result: dict):
        if not isinstance(result, dict) or account_id not in self.active_watches:
            return

        watch_data = self.active_watches[account_id]
        is_generating = bool(result.get("isGenerating", False))
        current_length = int(result.get("length", 0))
        elapsed = time.time() - watch_data["started_at"]

        if watch_data["initial_length"] is None:
            watch_data["initial_length"] = current_length
            watch_data["last_length"] = current_length
            return

        if is_generating:
            watch_data["saw_generating"] = True
            watch_data["stable_count"] = 0
            watch_data["last_length"] = current_length
            return

        has_grown = (current_length - watch_data["initial_length"]) >= 40
        if current_length != watch_data["last_length"]:
            watch_data["stable_count"] = 0
            watch_data["last_length"] = current_length
            return

        # Only count stability once streaming was seen OR text grew significantly (after 8s startup grace)
        if watch_data["saw_generating"] or (has_grown and elapsed >= 8.0):
            watch_data["stable_count"] += 1
            required_ticks = 2 if watch_data["saw_generating"] else 3
            if watch_data["stable_count"] >= required_ticks:
                self.stop_watching(account_id)
                self.generation_complete.emit(account_id)