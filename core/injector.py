import json
import os
from collections import deque
from typing import Optional, Callable, Any, List, Union
from PyQt6.QtCore import QMimeData, QUrl, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWebEngineCore import QWebEnginePage


class DOMInjector:
    _paste_queue = deque()
    _clipboard_busy = False

    def send_prompt(
        self,
        page: QWebEnginePage,
        platform: str,
        prompt_text: str,
        file_path: Optional[Union[str, List[str]]] = None,
        view: Any = None,
        callback: Optional[Callable[[dict], None]] = None
    ):
        files: List[str] = []
        if isinstance(file_path, str) and file_path.strip():
            if os.path.exists(file_path):
                files = [os.path.abspath(file_path)]
        elif isinstance(file_path, list):
            files = [os.path.abspath(p) for p in file_path if isinstance(p, str) and os.path.exists(p)]

        if files:
            self.send_multi_files(page, platform, prompt_text, files, view=view, callback=callback)
            return


        # Append Gemini-specific raw block rules ONLY when sending a Master Architect Directive to Gemini
        if (platform or "").lower() == "gemini" and ("MAP_START" in (prompt_text or "") and "TASK_START" in (prompt_text or "")):
            gemini_suffix = (
                "\n\n[CRITICAL GEMINI MASTER ARCHITECT FORMATTING OVERRIDE]:\n"
                "Because Gemini Markdown strips triple-equals (===) into single-equals (=), "
                "auto-links URLs into [url](url), and adds bullet points (- ) before closing tags:\n"
                "1. You MUST wrap your ENTIRE blueprint output (from ===MAP_START=== through the final ===TASK_END===) "
                "inside ONE single outer ```text ... ``` fenced code block so Markdown formatting never alters your tags or URLs.\n"
                "2. Inside that outer block, use exact triple-equals: ===MAP_START===, ===MAP_END===, ===TASK_START: account_id===, and ===TASK_END===.\n"
                "3. NEVER place a bullet point (- or *) on the same line as ===MAP_START===, ===MAP_END===, ===TASK_START===, or ===TASK_END===.\n"
                "4. Output plain raw URLs (e.g. https://dld.srmist.edu.in/*) without Markdown link brackets."
            )
            if "[CRITICAL GEMINI MASTER ARCHITECT FORMATTING OVERRIDE]" not in prompt_text:
                prompt_text = prompt_text + gemini_suffix

        input_selector, send_selector = self._get_selectors(platform)

        def _handle_result(result):
            if callback:
                if isinstance(result, dict) and result.get("success", False):
                    callback({
                        "success": True,
                        "ok": True,
                        "sent": True,
                        "status": "success"
                    })
                elif isinstance(result, dict):
                    callback(result)
                else:
                    callback({
                        "success": bool(result),
                        "ok": bool(result),
                        "sent": bool(result),
                        "status": "success" if result else "error"
                    })

        if view is not None:
            view.setFocus()

        js_code = self._build_single_insert_and_send_js(input_selector, send_selector, prompt_text)
        page.runJavaScript(js_code, _handle_result)

    @staticmethod
    def _build_single_insert_and_send_js(input_selector: str, send_selector: str, prompt_text: str) -> str:
        input_list_json = json.dumps([s.strip() for s in input_selector.split(",") if s.strip()])
        send_list_json = json.dumps([s.strip() for s in send_selector.split(",") if s.strip()])
        text_json = json.dumps(prompt_text or "")

        return f"""
        (function() {{
            try {{
                const inputSelectors = {input_list_json};
                const sendSelectors = {send_list_json};
                const rawText = {text_json};
                const CR = String.fromCharCode(13);
                const NL = String.fromCharCode(10);

                // 1. Locate the visible chat input editor
                let el = null;
                for (const sel of inputSelectors) {{
                    const cand = document.querySelector(sel);
                    if (cand && cand.getBoundingClientRect().width > 0) {{
                        el = cand;
                        break;
                    }}
                }}
                if (!el) {{
                    const fallbacks = Array.from(document.querySelectorAll(
                        'rich-textarea div.ql-editor, div.ProseMirror, div[contenteditable="true"], textarea'
                    ));
                    el = fallbacks.find(e => e.getBoundingClientRect().width > 0) || fallbacks[0] || null;
                }}
                if (!el) {{
                    return {{ success: false, status: "error", error: "Input box not found" }};
                }}

                // 2. Focus the editor cleanly
                el.focus();
                el.click();

                // 3. Clear any previous stuck text in the input box first
                document.execCommand("selectAll", false, null);
                document.execCommand("delete", false, null);

                // 4. Insert text EXACTLY ONCE (never run both Paste and insertText!)
                const lines = rawText.split(CR).join("").split(NL);
                let insertedOk = false;

                if (el.tagName && el.tagName.toLowerCase() === "textarea") {{
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value")?.set;
                    if (nativeSetter) {{
                        nativeSetter.call(el, rawText);
                    }} else {{
                        el.value = rawText;
                    }}
                    el.dispatchEvent(new Event("input", {{ bubbles: true }}));
                    insertedOk = true;
                }} else if (lines.length === 1) {{
                    // Single-line prompt: native execCommand('insertText') fires trusted input events in Quill & ProseMirror
                    insertedOk = document.execCommand("insertText", false, rawText);
                }} else {{
                    // Multi-line prompt: insert paragraph nodes cleanly so Enter doesn't submit on line 1
                    while (el.firstChild) {{
                        el.removeChild(el.firstChild);
                    }}
                    for (const line of lines) {{
                        const p = document.createElement("p");
                        if (line.length === 0) {{
                            p.appendChild(document.createElement("br"));
                        }} else {{
                            p.textContent = line;
                        }}
                        el.appendChild(p);
                    }}
                    if (el.classList && el.classList.contains("ql-blank")) {{
                        el.classList.remove("ql-blank");
                    }}
                    el.dispatchEvent(new InputEvent("input", {{ bubbles: true, cancelable: true, inputType: "insertText" }}));
                    insertedOk = true;
                }}

                if (!insertedOk && (el.innerText || "").trim().length === 0) {{
                    el.textContent = rawText;
                    el.dispatchEvent(new InputEvent("input", {{ bubbles: true, cancelable: true, inputType: "insertText" }}));
                }}

                // 5. Click the Send button (and verify submission with Enter fallback)
                function findSendButton() {{
                    for (const sel of sendSelectors) {{
                        const b = document.querySelector(sel);
                        if (b && !b.disabled && b.getAttribute("aria-disabled") !== "true" && b.getBoundingClientRect().width > 0) {{
                            return b;
                        }}
                    }}
                    // Fallback search for Gemini's blue [↑] button or Claude's send button near the input bar
                    const elRect = el.getBoundingClientRect();
                    const allBtns = Array.from(document.querySelectorAll('button, [role="button"]'));
                    for (const b of allBtns) {{
                        if (b.disabled || b.getAttribute("aria-disabled") === "true") continue;
                        const r = b.getBoundingClientRect();
                        if (r.width === 0 || r.height === 0) continue;
                        const label = (
                            (b.getAttribute("aria-label") || "") + " " +
                            (b.getAttribute("mattooltip") || "") + " " +
                            (b.getAttribute("data-testid") || "") + " " +
                            (b.className || "")
                        ).toLowerCase();
                        if (
                            label.includes("send message") ||
                            label.includes("send prompt") ||
                            label.includes("send-button") ||
                            label.includes("submit")
                        ) {{
                            return b;
                        }}
                    }}
                    return null;
                }}

                function triggerSendClick(btn) {{
                    const r = btn.getBoundingClientRect();
                    const cx = r.left + r.width / 2;
                    const cy = r.top + r.height / 2;
                    const opts = {{ bubbles: true, cancelable: true, composed: true, view: window, clientX: cx, clientY: cy, button: 0, buttons: 1 }};
                    const icon = btn.querySelector("mat-icon, svg, span") || btn;
                    for (const t of [icon, btn]) {{
                        t.dispatchEvent(new PointerEvent("pointerdown", opts));
                        t.dispatchEvent(new MouseEvent("mousedown", opts));
                        t.dispatchEvent(new PointerEvent("pointerup", opts));
                        t.dispatchEvent(new MouseEvent("mouseup", opts));
                        if (typeof t.click === "function") t.click();
                    }}
                }}

                function triggerEnterKey() {{
                    el.focus();
                    const kOpts = {{
                        key: "Enter", code: "Enter", keyCode: 13, which: 13, charCode: 13,
                        bubbles: true, cancelable: true, composed: true, view: window
                    }};
                    el.dispatchEvent(new KeyboardEvent("keydown", kOpts));
                    el.dispatchEvent(new KeyboardEvent("keypress", kOpts));
                    el.dispatchEvent(new KeyboardEvent("keyup", kOpts));
                }}

                // Attempt 1 at 180ms: Click Send button or press Enter
                setTimeout(() => {{
                    const btn = findSendButton();
                    if (btn) {{
                        triggerSendClick(btn);
                    }} else {{
                        triggerEnterKey();
                    }}

                    // Attempt 2 at 480ms: If text is STILL sitting in the input box, fire Enter + click Send again!
                    setTimeout(() => {{
                        const remaining = (el.innerText || el.value || "").trim();
                        if (remaining.length > 0) {{
                            const btnRetry = findSendButton();
                            if (btnRetry) {{
                                triggerSendClick(btnRetry);
                            }}
                            setTimeout(() => {{
                                const stillThere = (el.innerText || el.value || "").trim();
                                if (stillThere.length > 0) {{
                                    triggerEnterKey();
                                }}
                            }}, 120);
                        }}
                    }}, 300);
                }}, 180);

                return {{ success: true, ok: true, sent: true, status: "success" }};
            }} catch (err) {{
                return {{ success: false, status: "error", error: String(err) }};
            }}
        }})();
        """

    def send_multi_files(
        self,
        page: QWebEnginePage,
        platform: str,
        prompt_text: str,
        file_paths: List[str],
        view: Any = None,
        callback: Optional[Callable[[dict], None]] = None
    ):
        valid_files = [os.path.abspath(p) for p in (file_paths or []) if os.path.exists(p)]
        if not valid_files:
            self.send_prompt(page, platform, prompt_text, None, view=view, callback=callback)
            return

        DOMInjector._paste_queue.append({
            "page": page,
            "platform": platform,
            "prompt_text": prompt_text,
            "file_paths": valid_files,
            "view": view,
            "callback": callback
        })
        self._process_next_paste_job()

    @classmethod
    def _process_next_paste_job(cls):
        if cls._clipboard_busy or not cls._paste_queue:
            return

        cls._clipboard_busy = True
        job = cls._paste_queue.popleft()

        page: QWebEnginePage = job["page"]
        platform: str = job["platform"]
        prompt_text: str = job["prompt_text"]
        file_paths: List[str] = job["file_paths"]
        view = job["view"]
        callback = job["callback"]

        input_selector, send_selector = cls._get_selectors(platform)
        input_list_json = json.dumps([s.strip() for s in input_selector.split(",") if s.strip()])

        def _release_lock_and_continue():
            cls._clipboard_busy = False
            QTimer.singleShot(150, cls._process_next_paste_job)

        def _handle_result(result):
            if callback:
                callback({
                    "success": True,
                    "ok": True,
                    "sent": True,
                    "status": "success"
                })

        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(p) for p in file_paths])
        QGuiApplication.clipboard().setMimeData(mime)

        if view is not None:
            view.setFocus()

        js_focus_clear = f"""
        (function() {{
            const sels = {input_list_json};
            let el = null;
            for (const s of sels) {{
                const c = document.querySelector(s);
                if (c && c.getBoundingClientRect().width > 0) {{ el = c; break; }}
            }}
            if (!el) el = document.querySelector('rich-textarea div.ql-editor, div.ProseMirror, div[contenteditable="true"], textarea');
            if (!el) return false;
            el.focus();
            el.click();
            document.execCommand("selectAll", false, null);
            document.execCommand("delete", false, null);
            return true;
        }})();
        """

        def _on_focused(_ok):
            if view is not None:
                view.setFocus()

            page.triggerAction(QWebEnginePage.WebAction.Paste)
            QTimer.singleShot(1600, _release_lock_and_continue)

            def _finish_typing():
                if not prompt_text:
                    _handle_result({"success": True, "status": "success", "sent": True})
                    return
                js_finish = cls._build_single_insert_and_send_js(input_selector, send_selector, prompt_text)
                page.runJavaScript(js_finish, _handle_result)

            QTimer.singleShot(4200, _finish_typing)

        page.runJavaScript(js_focus_clear, lambda res: QTimer.singleShot(250, lambda: _on_focused(res)))

    @staticmethod
    def _get_selectors(platform: str):
        if (platform or "").lower() == "gemini":
            input_sel = "rich-textarea div.ql-editor, rich-textarea [contenteditable='true'], div.ql-editor[contenteditable='true'], div[contenteditable='true'][role='textbox'], div[contenteditable='true']"
            send_sel = "button.send-button, .send-button-container button, button[aria-label*='Send' i], button[mattooltip*='Send' i]"
        else:
            input_sel = "div.ProseMirror[contenteditable='true'], div[contenteditable='true'].ProseMirror, div[contenteditable='true'][role='textbox'], div[contenteditable='true'], textarea"
            send_sel = "button[aria-label*='Send' i], button[data-testid='send-button']"
        return input_sel, send_sel