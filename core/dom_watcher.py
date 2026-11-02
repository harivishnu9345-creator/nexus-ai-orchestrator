from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWebEngineCore import QWebEnginePage

class DOMWatcher(QObject):
    """Watches the DOM to detect when an AI node finishes streaming its response."""
    generation_complete = pyqtSignal(str)  # Emits account_id when done
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_watches = {}  # Store timers and state for each account

    def start_watching(self, account_id: str, page: QWebEnginePage, platform: str, config: dict):
        """Starts a 2-second polling timer for the given node."""
        if account_id in self.active_watches:
            self.stop_watching(account_id)
            
        # Extract selectors from config (fallback to Claude defaults)
        platform_config = config.get("platforms", {}).get(platform.lower(), {})
        selectors = platform_config.get("selectors", {})
        stop_selector = selectors.get("stop_button", "button[aria-label='Stop response']")
        
        timer = QTimer(self)
        self.active_watches[account_id] = {
            "timer": timer,
            "page": page,
            "last_length": 0,
            "stable_count": 0,
            "stop_selector": stop_selector
        }
        
        # Poll every 2000ms (2 seconds)
        timer.timeout.connect(lambda: self._poll_dom(account_id))
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
        stop_sel = watch_data["stop_selector"]
        
        # JS to check for the stop button and get current text length
        script = f"""
        (() => {{
            const stopBtn = document.querySelector("{stop_sel}");
            const isGenerating = stopBtn !== null;
            const textLen = document.body.innerText.length;
            return {{ isGenerating: isGenerating, length: textLen }};
        }})();
        """
        page.runJavaScript(script, lambda res: self._evaluate_state(account_id, res))

    def _evaluate_state(self, account_id: str, result: dict):
        if not result or account_id not in self.active_watches:
            return
            
        watch_data = self.active_watches[account_id]
        is_generating = result.get("isGenerating", False)
        current_length = result.get("length", 0)
        
        if is_generating:
            # Still generating, reset stability counter
            watch_data["stable_count"] = 0
            watch_data["last_length"] = current_length
        else:
            # Stop button is gone. Let's ensure text length hasn't changed for 4 seconds (2 ticks)
            if current_length == watch_data["last_length"] and current_length > 0:
                watch_data["stable_count"] += 1
            else:
                watch_data["stable_count"] = 0
                watch_data["last_length"] = current_length
                
            # If stable for 2 consecutive ticks (4 seconds), generation is truly complete
            if watch_data["stable_count"] >= 2:
                self.stop_watching(account_id)
                self.generation_complete.emit(account_id)