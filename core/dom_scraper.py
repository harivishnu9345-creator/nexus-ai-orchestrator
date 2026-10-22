import json
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEnginePage

class DOMScraper(QObject):
    scrape_complete = pyqtSignal(str, str, dict)

    def __init__(self):
        super().__init__()

    def extract_latest_response(self, page: QWebEnginePage, account_id: str, task_id: str):
        print(f"\n[SCRAPER] 🚀 Initializing DOM extraction for Master Account: {account_id}")
        
        # Bug Fix 2: Prevent fatal crashes if the pane was closed or page is invalid
        if not page:
            print(f"[SCRAPER] ❌ Extraction Failed: Target page object is None.")
            self.scrape_complete.emit(account_id, task_id, {"success": False, "error": "Target page is invalid or closed."})
            return
        
        # Bug Fix 1 & 3: Broadened selectors and safer DOM stripping
        js_code = """
        (function() {
            try {
                // Catch Claude's modern DOM updates using attribute roles and fallback classes
                const responses = document.querySelectorAll(
                    '[data-message-author-role="assistant"], .font-claude-response, .font-claude-message, .font-claude-response-body, .prose'
                );
                
                if (responses.length === 0) {
                    return { success: false, error: "No responses found on page. Claude UI may have updated." };
                }
                
                const lastResponse = responses[responses.length - 1];
                const clone = lastResponse.cloneNode(true);
                
                // Safely strip UI bloat like copy buttons and SVG icons
                // Removed [aria-hidden] to prevent accidental code-block stripping
                clone.querySelectorAll('button, svg').forEach(n => n.remove());
                
                return { success: true, text: clone.innerText.trim() };
            } catch (e) {
                return { success: false, error: e.toString() };
            }
        })();
        """

        def _callback(result):
            # Bug Fix 4: Safely handle null or unexpected data types from the JS engine
            if result is None or not isinstance(result, dict):
                print(f"[SCRAPER] ❌ JS Execution Failed: Returned None or invalid type.")
                self.scrape_complete.emit(account_id, task_id, {"success": False, "error": "JS returned None or invalid payload."})
                return
                
            if not result.get("success"):
                print(f"[SCRAPER] ❌ Extraction Failed: {result.get('error')}")
                self.scrape_complete.emit(account_id, task_id, result)
            else:
                text_len = len(result.get("text", ""))
                print(f"[SCRAPER] ✅ Extraction Success! Retrieved {text_len} characters from the DOM.")
                self.scrape_complete.emit(account_id, task_id, result)

        print("[SCRAPER] Executing JavaScript payload in embedded browser...")
        page.runJavaScript(js_code, _callback)