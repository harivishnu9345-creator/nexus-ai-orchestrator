import json
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEnginePage

class DOMScraper(QObject):
    scrape_complete = pyqtSignal(str, str, dict)

    def __init__(self):
        super().__init__()

    def extract_latest_response(self, page: QWebEnginePage, account_id: str, task_id: str):
        print(f"\n[SCRAPER] 🚀 Initializing DOM extraction for Master Account: {account_id}")
        
        js_code = """
        (function() {
            try {
                const responses = document.querySelectorAll('.font-claude-response');
                if (responses.length === 0) {
                    return { success: false, error: "No responses found on page." };
                }
                const lastResponse = responses[responses.length - 1];
                const clone = lastResponse.cloneNode(true);
                clone.querySelectorAll('button, svg, [aria-hidden]').forEach(n => n.remove());
                return { success: true, text: clone.innerText.trim() };
            } catch (e) {
                return { success: false, error: e.toString() };
            }
        })();
        """

        def _callback(result):
            if result is None:
                print(f"[SCRAPER] ❌ JS Execution Failed: Returned None")
                self.scrape_complete.emit(account_id, task_id, {"success": False, "error": "JS returned None"})
            elif not result.get("success"):
                print(f"[SCRAPER] ❌ Extraction Failed: {result.get('error')}")
                self.scrape_complete.emit(account_id, task_id, result)
            else:
                text_len = len(result.get("text", ""))
                print(f"[SCRAPER] ✅ Extraction Success! Retrieved {text_len} characters from the DOM.")
                self.scrape_complete.emit(account_id, task_id, result)

        print("[SCRAPER] Executing JavaScript payload in embedded browser...")
        page.runJavaScript(js_code, _callback)
