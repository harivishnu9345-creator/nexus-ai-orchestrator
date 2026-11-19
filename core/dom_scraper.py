import re
from typing import Callable
from PyQt6.QtWebEngineCore import QWebEnginePage


class DOMScraper:
    @staticmethod
    def normalize_delimiters(text: str) -> str:
        if not text:
            return ""

        # 1. Strip leading markdown bullets, numbers, or blockquotes before delimiter tags
        #    e.g. "- =TASK_END=" or "* =MAP_END=" or "4. =FILE: name.js="
        text = re.sub(
            r"(?m)^[\s>*\-\u2022\d.]*={1,3}[ \t]*(MAP_START|MAP_END|SUMMARY|END_SUMMARY|TASK_END)[ \t]*={1,3}",
            r"===\1===",
            text
        )
        text = re.sub(
            r"(?m)^[\s>*\-\u2022\d.]*={1,3}[ \t]*(TASK_START|FILE)[ \t]*:[ \t]*([^=\r\n]+?)[ \t]*={1,3}",
            lambda m: f"==={m.group(1).upper()}: {m.group(2).strip()}===",
            text
        )

        # 2. Catch inline single/double/triple equals delimiters anywhere in the text
        text = re.sub(r"={1,3}[ \t]*MAP_START[ \t]*={1,3}", "===MAP_START===", text, flags=re.IGNORECASE)
        text = re.sub(r"={1,3}[ \t]*MAP_END[ \t]*={1,3}", "===MAP_END===", text, flags=re.IGNORECASE)
        text = re.sub(r"={1,3}[ \t]*SUMMARY[ \t]*={1,3}", "===SUMMARY===", text, flags=re.IGNORECASE)
        text = re.sub(r"={1,3}[ \t]*END_SUMMARY[ \t]*={1,3}", "===END_SUMMARY===", text, flags=re.IGNORECASE)
        text = re.sub(r"={1,3}[ \t]*TASK_END[ \t]*={1,3}", "===TASK_END===", text, flags=re.IGNORECASE)
        text = re.sub(
            r"={1,3}[ \t]*TASK_START[ \t]*:[ \t]*([^=\r\n]+?)[ \t]*={1,3}",
            lambda m: f"===TASK_START: {m.group(1).strip()}===",
            text,
            flags=re.IGNORECASE
        )
        text = re.sub(
            r"={1,3}[ \t]*FILE[ \t]*:[ \t]*([^=\r\n]+?)[ \t]*={1,3}",
            lambda m: f"===FILE: {m.group(1).strip()}===",
            text,
            flags=re.IGNORECASE
        )

        # 3. Clean Gemini Markdown URL auto-linking inside specs:
        #    "[https://dld.srmist.edu.in/](https://dld.srmist.edu.in/)*" -> "https://dld.srmist.edu.in/*"
        text = re.sub(r"\[(https?://[^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\[([a-zA-Z0-9_.-]+\.[a-zA-Z]{2,}/?[^\]]*)\]\([^)]+\)", r"\1", text)

        # 4. Strip Gemini UI "Code snippet" header line injected above code blocks
        text = re.sub(r"(?m)^[ \t]*Code snippet[ \t]*\r?\n", "", text)

        # 5. If the Master output has ===TASK_START: ...=== blocks but omitted the final ===TASK_END===, append it
        starts = [m.start() for m in re.finditer(r"===TASK_START:", text)]
        ends = [m.start() for m in re.finditer(r"===TASK_END===", text)]
        if starts and (not ends or starts[-1] > ends[-1]):
            text = text.rstrip() + "\n===TASK_END===\n"

        return text

    @staticmethod
    def scrape_page_text(page: QWebEnginePage, callback: Callable[[str], None]):
        js = """
        (function() {
            try {
                const bodyText = document.body ? (document.body.innerText || "") : "";
                const isGemini = location.hostname.includes("gemini.google.com");
                if (isGemini) {
                    const responses = Array.from(document.querySelectorAll(
                        "message-content, model-response, .model-response-text, .response-container-content"
                    ));
                    if (responses.length > 0) {
                        const joined = responses.map(r => r.innerText || r.textContent || "").join("\\n\\n");
                        if (joined.trim().length > 20) {
                            return joined + "\\n\\n" + bodyText;
                        }
                    }
                }
                return bodyText;
            } catch (e) {
                return document.body ? (document.body.innerText || "") : "";
            }
        })();
        """

        def _on_scraped(raw_text):
            cleaned = DOMScraper.normalize_delimiters(raw_text or "")
            callback(cleaned)

        page.runJavaScript(js, _on_scraped)
# NEXUS_ASSISTANT_ONLY_SCRAPER_V22
_ASSISTANT_ONLY_SCRAPE_JS = r"""
(() => {
    const selectors = [
        '[data-testid="assistant-message"]',
        '.font-claude-message',
        '.font-claude-response',
        '[data-is-streaming]',
        'model-response',
        '.model-response-text',
        '.response-container-content',
        '[data-message-author-role="assistant"]'
    ];
    let nodes = [];
    for (const sel of selectors) {
        const found = Array.from(document.querySelectorAll(sel));
        if (found.length > 0) {
            nodes = found;
            break;
        }
    }
    if (nodes.length > 0) {
        return nodes.map(n => n.innerText || n.textContent || "").join("\n\n");
    }
    // Fallback: clone body and remove obvious user prompt bubbles
    const clone = document.body ? document.body.cloneNode(true) : null;
    if (!clone) return "";
    const userSelectors = [
        '[data-testid="user-message"]',
        '.font-user-message',
        'user-query',
        '[data-message-author-role="user"]'
    ];
    for (const us of userSelectors) {
        clone.querySelectorAll(us).forEach(el => el.remove());
    }
    return clone.innerText || "";
})();
"""


def _nexus_v22_scrape_page_text(page, callback):
    if page is None:
        callback("")
        return
    try:
        page.runJavaScript(_ASSISTANT_ONLY_SCRAPE_JS, lambda res: callback(res or ""))
    except Exception:
        callback("")


if hasattr(DOMScraper, "scrape_page_text"):
    DOMScraper._orig_scrape_page_text = staticmethod(DOMScraper.scrape_page_text)
    DOMScraper.scrape_page_text = staticmethod(_nexus_v22_scrape_page_text)
