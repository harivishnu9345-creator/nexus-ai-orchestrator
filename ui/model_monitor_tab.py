import json
import time
from typing import Callable, Dict
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QFrame, QAbstractItemView
)

CLAUDE_FREE_MODELS = [
    "Sonnet 5.5",
    "Haiku 5.5"
]

CLAUDE_PAID_MODELS = [
    "Sonnet 5.5",
    "Haiku 5.5",
    "Opus 5.5",
    "Fable 5.1",
    "Fable 5",
    "Opus 5"
]

CLAUDE_EFFORTS = [
    "Low",
    "Medium",
    "High",
    "Extra",
    "Max"
]

GEMINI_MODELS = [
    "4 Argon (Code & analysis)",
    "3.1 Pro (Detailed research)",
    "3.8 Flash (All-around help)",
    "3.5 Flash-Lite (Quick answers)"
]

GEMINI_THINKING = [
    "Low",
    "Medium",
    "High"
]


class ModelEfficiencyMonitorTab(QWidget):
    """Live Model Mode Controller powered by exact <gem-menu-item> & Claude DOM selectors."""

    def __init__(self, get_panes_fn: Callable, parent=None):
        super().__init__(parent)
        self.get_panes = get_panes_fn
        self._updating_programmatically = False
        self._pending_switch_until: Dict[str, float] = {}
        self._last_known_state: Dict[str, Dict[str, str]] = {}
        self._setup_ui()

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.scan_all_panes_telemetry)
        self.poll_timer.start(3500)

    def _setup_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #09090b; color: #f4f4f5; }
            QLabel { color: #e4e4e7; font-size: 11px; font-weight: bold; }
            QPushButton {
                background-color: #1f1f23; color: #e4e4e7; border: 1px solid #3f3f46;
                border-radius: 3px; padding: 5px 10px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #27272a; color: #ffffff; }
            QComboBox {
                background-color: #141417; color: #f4f4f5; border: 1px solid #3f3f46;
                border-radius: 3px; padding: 3px 6px; font-size: 11px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        bar = QFrame()
        bar.setStyleSheet("background-color: #141417; border: 1px solid #27272a; border-radius: 4px;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 6, 8, 6)

        title = QLabel("\u26a1 Live Model Mode Controller, Plan Tier & Usage / Rate-Limit Telemetry")
        title.setStyleSheet("color: #f4f4f5; font-size: 12px; font-weight: bold; border: none;")

        self.lbl_summary = QLabel("Ready")
        self.lbl_summary.setStyleSheet("color: #10b981; font-size: 11px; border: none;")

        btn_scan = QPushButton("\u21bb Sync Models & Quota Now")
        btn_scan.clicked.connect(lambda: self.scan_all_panes_telemetry(force_manual=True))

        bl.addWidget(title)
        bl.addStretch()
        bl.addWidget(self.lbl_summary)
        bl.addSpacing(10)
        bl.addWidget(btn_scan)
        layout.addWidget(bar)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Node Name", "AI Engine", "Detected Plan Tier", "Live Active Model & Effort",
            "Available Models (Unlocked Only)", "Effort / Thinking Level", "Live Quota & Usage Status"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #09090b; alternate-background-color: #121215;
                color: #f4f4f5; gridline-color: #27272a; border: 1px solid #27272a; font-size: 11px;
            }
            QHeaderView::section {
                background-color: #18181b; color: #a1a1aa; padding: 5px;
                border: none; border-right: 1px solid #27272a; border-bottom: 1px solid #27272a;
                font-weight: bold; font-size: 11px;
            }
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 145)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(3, 195)
        self.table.setColumnWidth(4, 225)
        self.table.setColumnWidth(5, 165)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, stretch=1)

    def rebuild_node_rows(self):
        panes = self.get_panes() or {}
        self._updating_programmatically = True
        self.table.setRowCount(len(panes))

        for row, (acc_id, pane) in enumerate(panes.items()):
            is_gemini = pane.platform == "gemini"
            theme_col = QColor("#38bdf8") if is_gemini else QColor("#f97316")

            saved = self._last_known_state.get(acc_id, {})
            default_model = saved.get("model", "4 Argon" if is_gemini else "Sonnet 5.5")
            default_eff = saved.get("effort", "Medium")

            name_it = QTableWidgetItem(pane.account_name)
            name_it.setForeground(QBrush(theme_col))

            plat_it = QTableWidgetItem(pane.platform.capitalize())
            plat_it.setForeground(QBrush(theme_col))

            default_plan = "Google AI Pro / Active" if is_gemini else "Free Plan (Sonnet / Haiku)"
            plan_it = QTableWidgetItem(default_plan)
            plan_it.setForeground(QBrush(QColor("#10b981" if is_gemini else "#e4e4e7")))

            det_it = QTableWidgetItem(f"{default_model} | {default_eff}")
            det_it.setForeground(QBrush(QColor("#f4f4f5")))

            combo_model = QComboBox()
            if is_gemini:
                combo_model.addItems(GEMINI_MODELS)
            else:
                combo_model.addItems(CLAUDE_FREE_MODELS)
            idx_m = combo_model.findText(default_model, Qt.MatchFlag.MatchContains)
            if idx_m >= 0:
                combo_model.setCurrentIndex(idx_m)
            combo_model.currentTextChanged.connect(
                lambda val, pid=acc_id, r=row: self._on_user_changed_model(pid, val, r)
            )

            combo_eff = QComboBox()
            if is_gemini:
                combo_eff.addItems(GEMINI_THINKING)
            else:
                combo_eff.addItems(CLAUDE_EFFORTS)
            combo_eff.setCurrentText(default_eff)
            combo_eff.setEnabled(True)
            combo_eff.currentTextChanged.connect(
                lambda val, pid=acc_id, r=row: self._on_user_changed_effort(pid, val, r)
            )

            quota_it = QTableWidgetItem("\U0001f7e2 FREE / READY - Available for tasks")
            quota_it.setForeground(QBrush(QColor("#10b981")))

            self.table.setItem(row, 0, name_it)
            self.table.setItem(row, 1, plat_it)
            self.table.setItem(row, 2, plan_it)
            self.table.setItem(row, 3, det_it)
            self.table.setCellWidget(row, 4, combo_model)
            self.table.setCellWidget(row, 5, combo_eff)
            self.table.setItem(row, 6, quota_it)

        self._updating_programmatically = False
        self._update_summary_badge()
        QTimer.singleShot(400, self.scan_all_panes_telemetry)

    def _on_user_changed_model(self, acc_id: str, model_label: str, row: int):
        if self._updating_programmatically or not model_label:
            return
        panes = self.get_panes() or {}
        if acc_id not in panes:
            return
        pane = panes[acc_id]
        self._execute_two_step_dom_switch(pane, model_label, is_effort=False, row=row)

    def _on_user_changed_effort(self, acc_id: str, eff_label: str, row: int):
        if self._updating_programmatically or not eff_label:
            return
        panes = self.get_panes() or {}
        if acc_id not in panes:
            return
        pane = panes[acc_id]
        clean_eff = eff_label.split("(")[0].strip()
        self._execute_two_step_dom_switch(pane, clean_eff, is_effort=True, row=row)

    def _execute_two_step_dom_switch(self, pane, target_text: str, is_effort: bool, row: int):
        acc_id = pane.account_id
        self._pending_switch_until[acc_id] = time.time() + 4.0

        page = pane.get_page()
        is_gemini = pane.platform == "gemini"

        combo_m = self.table.cellWidget(row, 4)
        combo_e = self.table.cellWidget(row, 5)
        m_txt = combo_m.currentText().split("(")[0].strip() if combo_m else ""
        e_txt = combo_e.currentText().split("(")[0].strip() if combo_e else ""

        self._last_known_state[acc_id] = {"model": m_txt, "effort": e_txt}

        det_it = self.table.item(row, 3)
        if det_it:
            det_it.setText(f"{m_txt} | {e_txt}")

        low_t = target_text.lower()
        if is_effort:
            synonyms = [low_t.split("(")[0].strip()]
        else:
            if "argon" in low_t:
                synonyms = ["code & analysis", "4 argon"]
            elif "3.1 pro" in low_t or "detailed research" in low_t:
                synonyms = ["detailed research", "3.1 pro"]
            elif "3.8 flash" in low_t or "all-around help" in low_t:
                synonyms = ["all-around help", "3.8 flash"]
            elif "3.5 flash-lite" in low_t or "quick answers" in low_t:
                synonyms = ["quick answers", "3.5 flash-lite"]
            else:
                synonyms = [low_t.split("(")[0].strip()]

        js_switch = f"""
        (function() {{
            const targetList = {json.dumps(synonyms)};
            const isGemini = {json.dumps(is_gemini)};
            const isEffort = {json.dumps(is_effort)};
            const NL = String.fromCharCode(10);

            function dispatchClickSequence(el) {{
                if (!el) return;
                const r = el.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) return;
                const cx = r.left + r.width / 2;
                const cy = r.top + r.height / 2;
                const opts = {{ bubbles: true, cancelable: true, composed: true, view: window, clientX: cx, clientY: cy, button: 0, buttons: 1 }};
                el.dispatchEvent(new PointerEvent('pointerdown', opts));
                el.dispatchEvent(new MouseEvent('mousedown', opts));
                el.dispatchEvent(new PointerEvent('pointerup', opts));
                el.dispatchEvent(new MouseEvent('mouseup', opts));
                el.click();
            }}

            function clickGemMenuItemOrButton(el) {{
                if (!el) return;
                // In Gemini DevTools (image_d1593c.png), items are <gem-menu-item role="menuitemradio"> containing <gem-menu-item-content> and <div class="label-container">
                const gemItem = el.closest('gem-menu-item, [role="menuitemradio"], [role="menuitem"], [role="option"], button, .mat-mdc-menu-item');
                if (gemItem) {{
                    dispatchClickSequence(gemItem);
                    const gemContent = gemItem.querySelector('gem-menu-item-content, .label-container');
                    if (gemContent) dispatchClickSequence(gemContent);
                }} else {{
                    dispatchClickSequence(el);
                }}
            }}

            function findGeminiModelPickerButton() {{
                const selectors = [
                    '[data-test-id*="mode-menu" i]',
                    '[data-test-id*="model" i]',
                    'bard-mode-switcher button',
                    'button.mat-mdc-menu-trigger'
                ];
                for (const sel of selectors) {{
                    const found = document.querySelector(sel);
                    if (found && found.getBoundingClientRect().width > 0) return found;
                }}
                const allBtns = Array.from(document.querySelectorAll('button, [role="button"]'));
                for (const b of allBtns) {{
                    const r = b.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0 || r.top > 180) continue;
                    const t = (b.innerText || "").split(NL).join(" ").trim();
                    if (!t || t.length > 42) continue;
                    const low = t.toLowerCase();
                    if (
                        low.includes("argon") ||
                        low.includes("flash") ||
                        low.includes("gemini ") ||
                        low.startsWith("pro ") ||
                        low === "pro" ||
                        low.includes("3.1") ||
                        low.includes("3.8") ||
                        low.includes("3.5")
                    ) {{
                        return b;
                    }}
                }}
                return null;
            }}

            function findClaudeModelPickerButton() {{
                const allBtns = Array.from(document.querySelectorAll('button, [role="button"]'));
                for (const b of allBtns) {{
                    const r = b.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) continue;
                    const t = (b.innerText || "").split(NL).join(" ").trim();
                    if (!t || t.length > 42) continue;
                    const low = t.toLowerCase();
                    if (low.includes("sonnet") || low.includes("haiku") || low.includes("opus") || low.includes("fable")) {{
                        if (!low.includes("upgrade")) return b;
                    }}
                }}
                return null;
            }}

            function findMatchingMenuItem() {{
                // 1. First check Gemini's <gem-menu-item> and .label-container elements directly (from DevTools image_d1593c.png)
                if (isGemini) {{
                    const gemItems = Array.from(document.querySelectorAll('gem-menu-item, [role="menuitemradio"], [role="menuitem"], .mat-mdc-menu-item'));
                    for (const item of gemItems) {{
                        const r = item.getBoundingClientRect();
                        if (r.width === 0 || r.height === 0) continue;
                        const raw = (item.innerText || "").trim();
                        if (!raw) continue;
                        const lowFull = raw.toLowerCase();
                        // Never click locked 4 Carbon
                        if (lowFull.includes("4 carbon") || lowFull.includes("most complex work")) continue;

                        const lines = raw.split(NL).map(s => s.replace("\u2713", "").replace("check", "").trim().toLowerCase()).filter(Boolean);
                        for (const cand of targetList) {{
                            if (lines.some(line => line === cand || line.startsWith(cand + " ") || line.endsWith(" " + cand))) {{
                                if (cand === "3.8 flash" && lowFull.includes("flash-lite")) continue;
                                return item;
                            }}
                        }}
                    }}
                }}

                // 2. General fallback for Claude and any other menu structure
                const allItems = Array.from(document.querySelectorAll(
                    '[role="menuitem"], [role="option"], [role="menuitemradio"], .mat-mdc-menu-item, button, div.label-container, div'
                ));
                for (const el of allItems) {{
                    const r = el.getBoundingClientRect();
                    if (r.width < 30 || r.height < 14 || r.height > 90) continue;
                    if (isGemini && r.top < 68 && r.left < 260) continue;
                    if (!isGemini && r.top > window.innerHeight - 90) continue;

                    const raw = (el.innerText || "").trim();
                    if (!raw) continue;
                    const lowFull = raw.toLowerCase();
                    if (!isGemini && lowFull.includes("upgrade")) continue;
                    if (isGemini && (lowFull.includes("4 carbon") || lowFull.includes("most complex work"))) continue;

                    const lines = raw.split(NL).map(s => s.replace("\u2713", "").replace("check", "").trim().toLowerCase()).filter(Boolean);
                    if (lines.length === 0 || lines.length > 3) continue;

                    for (const cand of targetList) {{
                        if (lines.some(line => line === cand || line.startsWith(cand + " ") || line.endsWith(" " + cand))) {{
                            if (cand === "3.8 flash" && lowFull.includes("flash-lite")) continue;
                            return el;
                        }}
                    }}
                }}
                return null;
            }}

            function areGeminiThinkingOptionsVisible() {{
                const gemItems = Array.from(document.querySelectorAll('gem-menu-item, [role="menuitemradio"], div.label-container'));
                let hasLow = false;
                let hasHigh = false;
                for (const el of gemItems) {{
                    const r = el.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) continue;
                    const fl = ((el.innerText || "").split(NL)[0] || "").trim().toLowerCase();
                    if (fl === "low") hasLow = true;
                    if (fl === "high") hasHigh = true;
                }}
                return hasLow && hasHigh;
            }}

            function expandGeminiThinkingLevel() {{
                // Find every element in the open menu that says "Thinking level" (without Low/Medium/High inside its text)
                const allEls = Array.from(document.querySelectorAll(
                    '.cdk-overlay-container gem-menu-item, .cdk-overlay-container button, .cdk-overlay-container [role="button"], ' +
                    '.cdk-overlay-container .label-container, .cdk-overlay-container div, .cdk-overlay-container span'
                ));
                const matchedEls = [];
                for (const el of allEls) {{
                    const r = el.getBoundingClientRect();
                    if (r.width < 30 || r.height < 12 || r.height > 75) continue;
                    const t = (el.innerText || "").trim().toLowerCase();
                    if (t === "thinking level" || (t.startsWith("thinking level") && t.length < 25)) {{
                        matchedEls.push(el);
                    }}
                }}

                if (matchedEls.length === 0) return false;

                // Click from the outer row container AND the inner label/button so Angular's (click) listener is guaranteed to fire!
                const seen = new Set();
                for (const el of matchedEls) {{
                    const row = el.closest('gem-menu-item, button, [role="button"], [role="menuitem"]') || el.parentElement || el;
                    if (row && !seen.has(row)) {{
                        seen.add(row);
                        dispatchClickSequence(row);
                    }}
                    if (!seen.has(el)) {{
                        seen.add(el);
                        dispatchClickSequence(el);
                    }}
                }}
                return true;
            }}

            function clickOptionInsideOverlay() {{
                if (isGemini && isEffort) {{
                    if (areGeminiThinkingOptionsVisible()) {{
                        const match = findMatchingMenuItem();
                        if (match) clickGemMenuItemOrButton(match);
                        return;
                    }}

                    // Expand "Thinking level v"
                    expandGeminiThinkingLevel();

                    setTimeout(() => {{
                        if (!areGeminiThinkingOptionsVisible()) {{
                            expandGeminiThinkingLevel();
                        }}
                        setTimeout(() => {{
                            const match = findMatchingMenuItem();
                            if (match) {{
                                clickGemMenuItemOrButton(match);
                            }}
                        }}, 240);
                    }}, 280);
                    return;
                }}

                let match = findMatchingMenuItem();
                if (match) {{
                    clickGemMenuItemOrButton(match);
                    if (!isGemini && isEffort) {{
                        setTimeout(() => {{
                            document.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true }}));
                        }}, 260);
                    }}
                    return;
                }}

                if (!isGemini && !isEffort) {{
                    const moreEl = Array.from(document.querySelectorAll('button, div, span')).find(e => {{
                        return (e.innerText || "").trim().toLowerCase() === "more models";
                    }});
                    if (moreEl) dispatchClickSequence(moreEl);
                    setTimeout(() => {{
                        const secondMatch = findMatchingMenuItem();
                        if (secondMatch) clickGemMenuItemOrButton(secondMatch);
                    }}, 250);
                }}
            }}

            // Step 1: Open the menu if not already open
            const isMenuOpen = document.querySelector('gem-menu-item, .cdk-overlay-pane [role="menu"], .cdk-overlay-pane .mat-mdc-menu-panel, [role="menu"], [role="listbox"]');
            if (isMenuOpen && isMenuOpen.getBoundingClientRect().height > 0) {{
                clickOptionInsideOverlay();
            }} else {{
                let triggerBtn = isGemini ? findGeminiModelPickerButton() : findClaudeModelPickerButton();
                if (isGemini && !triggerBtn) {{
                    const gInput = document.querySelector("rich-textarea div.ql-editor, rich-textarea [contenteditable='true'], div[contenteditable='true']");
                    if (gInput) {{
                        gInput.focus();
                        gInput.click();
                    }}
                    setTimeout(() => {{
                        triggerBtn = findGeminiModelPickerButton();
                        if (triggerBtn) dispatchClickSequence(triggerBtn);
                        setTimeout(clickOptionInsideOverlay, 360);
                    }}, 220);
                }} else {{
                    if (triggerBtn) dispatchClickSequence(triggerBtn);
                    setTimeout(clickOptionInsideOverlay, 360);
                }}
            }}
            return true;
        }})();
        """
        page.runJavaScript(js_switch)
        QTimer.singleShot(2000, self.scan_all_panes_telemetry)

    def scan_all_panes_telemetry(self, force_manual: bool = False):
        if force_manual:
            self._pending_switch_until.clear()
        panes = self.get_panes() or {}
        if self.table.rowCount() != len(panes):
            self.rebuild_node_rows()
            return

        js_probe = """
        (function() {
            try {
                const body = document.body ? document.body.innerText : "";
                const lowBody = body.toLowerCase();
                const isGemini = location.hostname.includes("gemini.google.com");
                const NL = String.fromCharCode(10);

                let isFreeClaude = false;
                let planTier = isGemini ? "Google AI Pro / Active" : "Claude Plan";

                if (!isGemini) {
                    const hasUpgradeBadge = Array.from(document.querySelectorAll('a, button, span')).some(el => {
                        const t = (el.innerText || "").trim().toLowerCase();
                        return t === "upgrade" || t.includes("free plan");
                    });
                    if (lowBody.includes("free plan") || hasUpgradeBadge) {
                        isFreeClaude = true;
                        planTier = "Free Plan (Sonnet / Haiku)";
                    } else if (lowBody.includes("max plan") || lowBody.includes("claude max")) {
                        planTier = "Claude Max (All Models)";
                    } else if (lowBody.includes("pro plan") || lowBody.includes("claude pro")) {
                        planTier = "Claude Pro (All Models)";
                    } else {
                        isFreeClaude = true;
                        planTier = "Free Plan (Sonnet / Haiku)";
                    }
                }

                let rawButtonLabel = "";
                const allBtns = Array.from(document.querySelectorAll('button, [role="button"]'));
                for (const b of allBtns) {
                    const r = b.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) continue;
                    const raw = (b.innerText || "").split(NL).join(" ").trim();
                    if (!raw || raw.length > 42) continue;
                    const low = raw.toLowerCase();

                    if (isGemini) {
                        if (r.top > 180) continue;
                        if (
                            low.includes("argon") ||
                            low.includes("flash") ||
                            low.includes("gemini ") ||
                            low.startsWith("pro ") ||
                            low === "pro" ||
                            low.includes("3.1") ||
                            low.includes("3.8") ||
                            low.includes("3.5")
                        ) {
                            rawButtonLabel = raw;
                            break;
                        }
                    } else {
                        if (low.includes("sonnet") || low.includes("haiku") || low.includes("opus") || low.includes("fable")) {
                            if (!low.includes("upgrade")) {
                                rawButtonLabel = raw;
                                break;
                            }
                        }
                    }
                }

                let foundButton = Boolean(rawButtonLabel);
                let canonicalModel = "";
                let canonicalEffort = "";
                const lowBtn = (rawButtonLabel || "").toLowerCase();

                if (foundButton) {
                    if (isGemini) {
                        if (lowBtn.includes("flash-lite")) canonicalModel = "3.5 Flash-Lite";
                        else if (lowBtn.includes("flash")) canonicalModel = "3.8 Flash";
                        else if (lowBtn.includes("pro")) canonicalModel = "3.1 Pro";
                        else if (lowBtn.includes("argon")) canonicalModel = "4 Argon";

                        if (lowBtn.includes(" low")) canonicalEffort = "Low";
                        else if (lowBtn.includes(" high")) canonicalEffort = "High";
                        else if (lowBtn.includes(" medium")) canonicalEffort = "Medium";
                    } else {
                        if (lowBtn.includes("haiku")) canonicalModel = "Haiku 5.5";
                        else if (lowBtn.includes("opus 5.5")) canonicalModel = "Opus 5.5";
                        else if (lowBtn.includes("fable 5.1")) canonicalModel = "Fable 5.1";
                        else if (lowBtn.includes("fable")) canonicalModel = "Fable 5";
                        else if (lowBtn.includes("opus")) canonicalModel = "Opus 5";
                        else if (lowBtn.includes("sonnet")) canonicalModel = "Sonnet 5.5";

                        for (const eff of ["Low", "Medium", "High", "Extra", "Max"]) {
                            if (lowBtn.includes(eff.toLowerCase())) {
                                canonicalEffort = eff;
                                break;
                            }
                        }
                    }
                }

                let usageHit = false;
                let usageMsg = "FREE / READY - Available for tasks";
                const lines = body.split(NL);
                for (const line of lines) {
                    const l = line.trim();
                    const lowL = l.toLowerCase();
                    if (!l || l.length > 140) continue;
                    if (
                        lowL.includes("limit reached") ||
                        lowL.includes("resets on ") ||
                        lowL.includes("your limit resets") ||
                        lowL.includes("usage limit") ||
                        lowL.includes("reached your limit") ||
                        lowL.includes("out of free messages") ||
                        lowL.includes("out of messages")
                    ) {
                        usageHit = true;
                        usageMsg = "USAGE LIMIT HIT - " + l;
                        break;
                    }
                    if (lowL.includes("messages remaining")) {
                        usageMsg = "LOW QUOTA - " + l;
                        break;
                    }
                }

                return {
                    planTier: planTier,
                    isFreeClaude: isFreeClaude,
                    foundButton: foundButton,
                    canonicalModel: canonicalModel,
                    canonicalEffort: canonicalEffort,
                    usageHit: usageHit,
                    usageMsg: usageMsg
                };
            } catch (err) {
                return null;
            }
        })();
        """

        now = time.time()
        for row, (acc_id, pane) in enumerate(panes.items()):
            if now < self._pending_switch_until.get(acc_id, 0):
                continue

            def _make_cb(r=row, p=pane, aid=acc_id):
                def _cb(res):
                    if not isinstance(res, dict):
                        return
                    plan_item = self.table.item(r, 2)
                    det_item = self.table.item(r, 3)
                    quota_item = self.table.item(r, 6)

                    if plan_item:
                        plan_txt = res.get("planTier", "Standard")
                        plan_item.setText(plan_txt)
                        plan_item.setForeground(QBrush(QColor("#e4e4e7" if "Free" in plan_txt else "#10b981")))

                    if p.platform == "claude":
                        self._update_claude_available_models_dropdown(r, bool(res.get("isFreeClaude", True)))

                    if res.get("foundButton"):
                        c_model = res.get("canonicalModel", "")
                        c_eff = res.get("canonicalEffort", "")
                        prev = self._last_known_state.setdefault(aid, {})
                        if c_model:
                            prev["model"] = c_model
                        if c_eff:
                            prev["effort"] = c_eff

                        eff_display = prev.get("effort", "Medium")
                        mod_display = prev.get("model", c_model or "Active")
                        if det_item:
                            det_item.setText(f"{mod_display} | {eff_display}")

                        self._sync_row_dropdowns_exact(r, c_model, c_eff)

                    if quota_item:
                        raw_msg = res.get("usageMsg", "FREE / READY - Available for tasks")
                        if res.get("usageHit"):
                            quota_item.setText("\U0001f534 " + raw_msg)
                            quota_item.setForeground(QBrush(QColor("#ef4444")))
                            p.set_status("rate_limited")
                        elif "LOW QUOTA" in raw_msg:
                            quota_item.setText("\U0001f7e1 " + raw_msg)
                            quota_item.setForeground(QBrush(QColor("#eab308")))
                        else:
                            quota_item.setText("\U0001f7e2 " + raw_msg)
                            quota_item.setForeground(QBrush(QColor("#10b981")))
                            p.set_status("ready")
                    self._update_summary_badge()
                return _cb

            pane.get_page().runJavaScript(js_probe, _make_cb())

    def _update_claude_available_models_dropdown(self, row: int, is_free_claude: bool):
        combo_m = self.table.cellWidget(row, 4)
        if not combo_m or combo_m.view().isVisible():
            return
        target_list = CLAUDE_FREE_MODELS if is_free_claude else CLAUDE_PAID_MODELS
        current_items = [combo_m.itemText(i) for i in range(combo_m.count())]
        if current_items != target_list:
            self._updating_programmatically = True
            curr_val = combo_m.currentText()
            combo_m.clear()
            combo_m.addItems(target_list)
            if curr_val in target_list:
                combo_m.setCurrentText(curr_val)
            self._updating_programmatically = False

    def _sync_row_dropdowns_exact(self, row: int, canonical_model: str, canonical_effort: str):
        self._updating_programmatically = True
        try:
            combo_m = self.table.cellWidget(row, 4)
            combo_e = self.table.cellWidget(row, 5)
            if combo_m and canonical_model and not combo_m.view().isVisible():
                idx = combo_m.findText(canonical_model, Qt.MatchFlag.MatchContains)
                if idx >= 0 and combo_m.currentIndex() != idx:
                    combo_m.setCurrentIndex(idx)
            if combo_e is not None:
                combo_e.setEnabled(True)
                if canonical_effort and not combo_e.view().isVisible():
                    idx_e = combo_e.findText(canonical_effort, Qt.MatchFlag.MatchStartsWith)
                    if idx_e >= 0 and combo_e.currentIndex() != idx_e:
                        combo_e.setCurrentIndex(idx_e)
        finally:
            self._updating_programmatically = False

    def _update_summary_badge(self):
        total = self.table.rowCount()
        free_count = 0
        hit_count = 0
        for r in range(total):
            it = self.table.item(r, 6)
            txt = it.text() if it else ""
            if "USAGE LIMIT HIT" in txt:
                hit_count += 1
            else:
                free_count += 1
        from datetime import datetime
        self.lbl_summary.setText(f"Free/Ready Chats: {free_count}/{total}  |  Usage Hit: {hit_count}  (Synced {datetime.now().strftime('%H:%M:%S')})")
