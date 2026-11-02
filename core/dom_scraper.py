from typing import Callable
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEnginePage


class DOMScraper(QObject):
    scrape_complete = pyqtSignal(str, str, dict)

    def __init__(self):
        super().__init__()

    @staticmethod
    def scrape_page_text(page: QWebEnginePage, callback: Callable[[str], None]):
        if not page:
            callback("")
            return

        js_code = r"""
        (function() {
            try {
                // 1. Find the full assistant message container (avoiding partial child .prose fragments)
                const tierSelectors = [
                    '[data-message-author-role="assistant"]',
                    '.font-claude-response',
                    '.font-claude-message',
                    '[data-testid*="assistant"]',
                    '[data-is-streaming]'
                ];

                let targetContainer = null;
                for (const sel of tierSelectors) {
                    const matches = document.querySelectorAll(sel);
                    if (matches.length > 0) {
                        targetContainer = matches[matches.length - 1];
                        break;
                    }
                }

                // Fallback: if only .prose elements exist, climb up to their shared message wrapper
                if (!targetContainer) {
                    const proseList = document.querySelectorAll('.prose');
                    if (proseList.length > 0) {
                        const lastProse = proseList[proseList.length - 1];
                        targetContainer = lastProse.closest('[data-test-render-count]') || lastProse.parentElement || lastProse;
                    }
                }

                if (!targetContainer) {
                    targetContainer = document.body;
                }

                const clone = targetContainer.cloneNode(true);

                // 2. Strip UI buttons, copy toolbars, and SVGs before extracting code
                clone.querySelectorAll('button, svg, [role="toolbar"]').forEach(n => n.remove());

                // 3. Convert every <pre> block into explicit ``` fenced markdown so regex harvesters never miss code
                clone.querySelectorAll('pre').forEach(pre => {
                    const codeEl = pre.querySelector('code');
                    const rawCode = codeEl ? codeEl.innerText : pre.innerText;
                    const fencedText = "\n```\n" + rawCode.trim() + "\n```\n";
                    const replacement = document.createTextNode(fencedText);
                    pre.parentNode.replaceChild(replacement, pre);
                });

                return clone.innerText.trim();
            } catch (e) {
                return document.body ? document.body.innerText : "";
            }
        })();
        """
        page.runJavaScript(js_code, lambda res: callback(res if isinstance(res, str) else ""))

    def extract_latest_response(self, page: QWebEnginePage, account_id: str, task_id: str):
        if not page:
            self.scrape_complete.emit(account_id, task_id, {"success": False, "error": "Target page is invalid or closed."})
            return

        def _on_text(text: str):
            if text:
                self.scrape_complete.emit(account_id, task_id, {"success": True, "text": text})
            else:
                self.scrape_complete.emit(account_id, task_id, {"success": False, "error": "No response text found."})

        DOMScraper.scrape_page_text(page, _on_text)
