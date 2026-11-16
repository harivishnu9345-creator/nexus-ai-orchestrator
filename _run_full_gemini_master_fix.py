import os
import re
import py_compile

# ==============================================================================
# 1. COMPLETE core/dom_scraper.py
#    - Normalizes Gemini single/double equals (=MAP_START=, =TASK_START: ...=,
#      - =TASK_END=, =FILE: ...=, =SUMMARY=, =END_SUMMARY=) into === tags
#    - Strips Gemini "Code snippet" artifacts and "[url](url)" link corruption
#    - Combines assistant response containers with full-body fallback
# ==============================================================================
dom_scraper_code = """import re
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
            r"(?m)^[\\s>*\\-\\u2022\\d.]*={1,3}[ \\t]*(MAP_START|MAP_END|SUMMARY|END_SUMMARY|TASK_END)[ \\t]*={1,3}",
            r"===\\1===",
            text
        )
        text = re.sub(
            r"(?m)^[\\s>*\\-\\u2022\\d.]*={1,3}[ \\t]*(TASK_START|FILE)[ \\t]*:[ \\t]*([^=\\r\\n]+?)[ \\t]*={1,3}",
            lambda m: f"==={m.group(1).upper()}: {m.group(2).strip()}===",
            text
        )

        # 2. Catch inline single/double/triple equals delimiters anywhere in the text
        text = re.sub(r"={1,3}[ \\t]*MAP_START[ \\t]*={1,3}", "===MAP_START===", text)
        text = re.sub(r"={1,3}[ \\t]*MAP_END[ \\t]*={1,3}", "===MAP_END===", text)
        text = re.sub(r"={1,3}[ \\t]*SUMMARY[ \\t]*={1,3}", "===SUMMARY===", text)
        text = re.sub(r"={1,3}[ \\t]*END_SUMMARY[ \\t]*={1,3}", "===END_SUMMARY===", text)
        text = re.sub(r"={1,3}[ \\t]*TASK_END[ \\t]*={1,3}", "===TASK_END===", text)
        text = re.sub(
            r"={1,3}[ \\t]*TASK_START[ \\t]*:[ \\t]*([^=\\r\\n]+?)[ \\t]*={1,3}",
            lambda m: f"===TASK_START: {m.group(1).strip()}===",
            text
        )
        text = re.sub(
            r"={1,3}[ \\t]*FILE[ \\t]*:[ \\t]*([^=\\r\\n]+?)[ \\t]*={1,3}",
            lambda m: f"===FILE: {m.group(1).strip()}===",
            text
        )

        # 3. Clean Gemini Markdown URL auto-linking inside specs:
        #    "[https://dld.srmist.edu.in/](https://dld.srmist.edu.in/)*" -> "https://dld.srmist.edu.in/*"
        #    "*://[gemini.google.com/](https://gemini.google.com/)*" -> "*://gemini.google.com/*"
        text = re.sub(r"\\[(https?://[^\\]]+)\\]\\([^)]+\\)", r"\\1", text)
        text = re.sub(r"\\[([a-zA-Z0-9_.-]+\\.[a-zA-Z]{2,}/?[^\\]]*)\\]\\([^)]+\\)", r"\\1", text)

        # 4. Strip Gemini UI "Code snippet" header line injected above code blocks
        text = re.sub(r"(?m)^[ \\t]*Code snippet[ \\t]*\\r?\\n", "", text)

        return text

    @staticmethod
    def scrape_page_text(page: QWebEnginePage, callback: Callable[[str], None]):
        js = (
            "(function() {"
            "  try {"
            "    const bodyText = document.body ? (document.body.innerText || \\"\\") : \\"\\";"
            "    const isGemini = location.hostname.includes(\\"gemini.google.com\\");"
            "    if (isGemini) {"
            "      const responses = Array.from(document.querySelectorAll("
            "        \\"message-content, model-response, .model-response-text, .response-container-content\\""
            "      ));"
            "      if (responses.length > 0) {"
            "        const joined = responses.map(r => r.innerText || r.textContent || \\"\\").join(\\"\\\\n\\\\n\\");"
            "        if (joined.trim().length > 20) return joined + \\"\\\\n\\\\n\\" + bodyText;"
            "      }"
            "    }"
            "    return bodyText;"
            "  } catch (e) {"
            "    return document.body ? (document.body.innerText || \\"\\") : \\"\\";"
            "  }"
            "})();"
        )
        def _on_scraped(raw_text):
            cleaned = DOMScraper.normalize_delimiters(raw_text or "")
            callback(cleaned)

        page.runJavaScript(js, _on_scraped)
"""

with open("core/dom_scraper.py", "w", encoding="utf-8") as f:
    f.write(dom_scraper_code)
py_compile.compile("core/dom_scraper.py", doraise=True)
import core.dom_scraper
print("[1/4] Wrote & verified complete core/dom_scraper.py")


# ==============================================================================
# 2. COMPLETE core/orchestrator.py UPGRADE
#    - Normalizes all text inputs via DOMScraper.normalize_delimiters
#    - Replaces strict ===TASK_START / ===MAP_START regexes with forgiving ones
# ==============================================================================
if os.path.exists("core/orchestrator.py"):
    with open("core/orchestrator.py", "r", encoding="utf-8") as f:
        ocode = f.read()

    if "from core.dom_scraper import DOMScraper" not in ocode:
        ocode = "from core.dom_scraper import DOMScraper\n" + ocode

    # Forgiving regex replacements inside core/orchestrator.py
    ocode = ocode.replace(
        r"===MAP_START===(.*?)===MAP_END===",
        r"={1,3}\s*MAP_START\s*={1,3}(.*?)={1,3}\s*MAP_END\s*={1,3}"
    )
    ocode = ocode.replace(
        r"===TASK_START:\s*(.+?)===(.*?)===TASK_END===",
        r"={1,3}\s*TASK_START\s*:\s*([^=\n]+?)\s*={1,3}(.*?)={1,3}\s*TASK_END\s*={1,3}"
    )
    ocode = ocode.replace(
        r"===TASK_START:\s*([^=]+)===(.*?)===TASK_END===",
        r"={1,3}\s*TASK_START\s*:\s*([^=\n]+?)\s*={1,3}(.*?)={1,3}\s*TASK_END\s*={1,3}"
    )

    with open("core/orchestrator.py", "w", encoding="utf-8") as f:
        f.write(ocode)
    py_compile.compile("core/orchestrator.py", doraise=True)
    import core.orchestrator
    print("[2/4] Upgraded & verified core/orchestrator.py with forgiving regexes")


# ==============================================================================
# 3. COMPLETE core/injector.py UPGRADE
#    - Automatically appends Gemini-specific Master Architect anti-mangling rules
#      ONLY when platform == "gemini" and sending a Master Directive
# ==============================================================================
with open("core/injector.py", "r", encoding="utf-8") as f:
    inj = f.read()

gemini_master_rule = """
        # Append Gemini-specific raw block rules ONLY when sending a Master Architect Directive to Gemini
        if (platform or "").lower() == "gemini" and ("MAP_START" in (prompt_text or "") and "TASK_START" in (prompt_text or "")):
            gemini_suffix = (
                "\\n\\n[CRITICAL GEMINI MASTER ARCHITECT FORMATTING OVERRIDE]:\\n"
                "Because Gemini Markdown strips triple-equals (===) into single-equals (=), "
                "auto-links URLs into [url](url), and adds bullet points (- ) before closing tags:\\n"
                "1. You MUST wrap your ENTIRE blueprint output (from ===MAP_START=== through the final ===TASK_END===) "
                "inside ONE single outer ```text ... ``` fenced code block so Markdown formatting never alters your tags or URLs.\\n"
                "2. Inside that outer block, use exact triple-equals: ===MAP_START===, ===MAP_END===, ===TASK_START: account_id===, and ===TASK_END===.\\n"
                "3. NEVER place a bullet point (- or *) on the same line as ===MAP_START===, ===MAP_END===, ===TASK_START===, or ===TASK_END===.\\n"
                "4. Output plain raw URLs (e.g. https://dld.srmist.edu.in/*) without Markdown link brackets."
            )
            if "[CRITICAL GEMINI MASTER ARCHITECT FORMATTING OVERRIDE]" not in prompt_text:
                prompt_text = prompt_text + gemini_suffix
"""

if "[CRITICAL GEMINI MASTER ARCHITECT FORMATTING OVERRIDE]" not in inj:
    # Remove shorter rule if present from earlier run
    if "[CRITICAL GEMINI MASTER FORMATTING OVERRIDE]" in inj:
        inj = inj.split("# Append Gemini-specific raw block rules")[0] + "        input_selector, send_selector = self._get_selectors(platform)" + inj.split("input_selector, send_selector = self._get_selectors(platform)", 1)[1]
    inj = inj.replace(
        "        input_selector, send_selector = self._get_selectors(platform)",
        gemini_master_rule + "\n        input_selector, send_selector = self._get_selectors(platform)",
        1
    )

with open("core/injector.py", "w", encoding="utf-8") as f:
    f.write(inj)
py_compile.compile("core/injector.py", doraise=True)
import core.injector
print("[3/4] Upgraded & verified core/injector.py with full Gemini Master Override")


# ==============================================================================
# 4. COMPLETE ui/main_window.py UPGRADE (All ~150 Lines Restored)
#    - Fixes _enhance_mind_map_zoom_and_fit AND _setup_url_tracing_and_mindmap_panel
#      so URL Trace Drawer NEVER attaches to Execution Flow & File Relay
#    - Reparents url_trace_drawer to Task Assignment Mind-Map if already mounted
#    - Fixes combo_master userData & syncs Master Architect changes live to
#      BinaryTreeRelayGraphWidget, Mind-Map, and SwarmOrchestrator
#    - Normalizes Master text in all Extract & Delegate callbacks AND adds a
#      multi-pane blueprint finder fallback so "No Tasks Found" never triggers
#      when =TASK_START= or ===TASK_START=== exists in the Gemini/Claude pane!
# ==============================================================================
with open("ui/main_window.py", "r", encoding="utf-8") as f:
    mw = f.read()

# 4A. Fix _enhance_mind_map_zoom_and_fit so self._mind_map_gv points strictly to the Mind-Map tab QGraphicsView
old_gv_finder = """        views = self.findChildren(QGraphicsView)
        if not views:
            return
        gv = views[0]"""

new_gv_finder = """        from PyQt6.QtWidgets import QTabWidget
        gv = None
        for tw in self.findChildren(QTabWidget):
            for i in range(tw.count()):
                if "Mind-Map" in tw.tabText(i):
                    tab_w = tw.widget(i)
                    found_gvs = tab_w.findChildren(QGraphicsView) if tab_w else []
                    if found_gvs:
                        gv = found_gvs[0]
                        break
        if gv is None:
            views = self.findChildren(QGraphicsView)
            if not views:
                return
            gv = views[0]"""

if old_gv_finder in mw:
    mw = mw.replace(old_gv_finder, new_gv_finder, 1)

# 4B. Make any inline TASK_START / MAP_START regex in ui/main_window.py forgiving and normalize text before checking "No Tasks Found"
if "from core.dom_scraper import DOMScraper" not in mw:
    mw = "from core.dom_scraper import DOMScraper\n" + mw

mw = mw.replace(
    r"===MAP_START===(.*?)===MAP_END===",
    r"={1,3}\s*MAP_START\s*={1,3}(.*?)={1,3}\s*MAP_END\s*={1,3}"
)
mw = mw.replace(
    r"===TASK_START:\s*(.+?)===(.*?)===TASK_END===",
    r"={1,3}\s*TASK_START\s*:\s*([^=\n]+?)\s*={1,3}(.*?)={1,3}\s*TASK_END\s*={1,3}"
)
mw = mw.replace(
    r"===TASK_START:\s*([^=]+)===(.*?)===TASK_END===",
    r"={1,3}\s*TASK_START\s*:\s*([^=\n]+?)\s*={1,3}(.*?)={1,3}\s*TASK_END\s*={1,3}"
)

# 4C. Replace _setup_master_architect_sync_and_gemini_adapter with the full, complete implementation
if "    def _setup_master_architect_sync_and_gemini_adapter(self):" in mw:
    before_sync = mw.split("    def _setup_master_architect_sync_and_gemini_adapter(self):", 1)[0]
    after_sync = mw.split("    def _ensure_v19_tabs_and_signals(self):", 1)[1]
    mw = before_sync + "    def _ensure_v19_tabs_and_signals(self):" + after_sync

full_master_and_layout_block = """    def _setup_master_architect_sync_and_gemini_adapter(self):
        \"\"\"
        1. Moves url_trace_drawer strictly into Task Assignment Mind-Map (restoring 100% height to Execution Flow & File Relay).
        2. Repairs combo_master userData and live-syncs Master Architect selection to L0: ROOT ARCHITECT, Mind-Map, and Orchestrator.
        3. Wraps Extract & Delegate Pipeline with DOMScraper.normalize_delimiters + multi-pane blueprint auto-detection.
        \"\"\"
        from PyQt6.QtWidgets import QTabWidget, QVBoxLayout
        from core.dom_scraper import DOMScraper

        # 1. Ensure url_trace_drawer is strictly inside "Task Assignment Mind-Map", NEVER inside "Execution Flow & File Relay"
        if hasattr(self, "url_trace_drawer") and self.url_trace_drawer is not None:
            mm_tab = None
            for tw in self.findChildren(QTabWidget):
                for i in range(tw.count()):
                    if "Mind-Map" in tw.tabText(i):
                        mm_tab = tw.widget(i)
                        break
                if mm_tab is not None:
                    break
            if mm_tab is not None and self.url_trace_drawer.parentWidget() != mm_tab:
                old_parent = self.url_trace_drawer.parentWidget()
                if old_parent and old_parent.layout():
                    old_parent.layout().removeWidget(self.url_trace_drawer)
                self.url_trace_drawer.setParent(mm_tab)
                if mm_tab.layout():
                    mm_tab.layout().addWidget(self.url_trace_drawer)

        # 2. Repair combo_master item data so currentData() always returns a valid account_id, and connect live signal
        if hasattr(self, "combo_master"):
            panes = getattr(self, "panes", {})
            for idx in range(self.combo_master.count()):
                if not self.combo_master.itemData(idx):
                    item_txt = (self.combo_master.itemText(idx) or "").strip()
                    for aid, pane in panes.items():
                        if pane.account_name in item_txt or aid in item_txt:
                            self.combo_master.setItemData(idx, aid)
                            break
            if not getattr(self, "_master_combo_synced", False):
                self.combo_master.currentIndexChanged.connect(self._on_master_architect_changed_live)
                self.combo_master.currentTextChanged.connect(self._on_master_architect_changed_live)
                self._master_combo_synced = True
            self._on_master_architect_changed_live()

        # 3. Wrap all Extract & Delegate methods so Gemini =TASK_START= / - =TASK_END= blocks are normalized and extracted
        extract_candidates = [
            name for name in dir(self)
            if any(k in name.lower() for k in ("extract", "delegate", "blueprint", "master_response"))
            and not name.startswith("__")
        ]
        for ext_name in extract_candidates:
            fn_obj = getattr(self, ext_name, None)
            if callable(fn_obj) and not getattr(self, f"_wrapped_norm_{ext_name}", False):
                def _make_ext_wrapper(orig_fn):
                    def _wrapped(*args, **kwargs):
                        new_args = list(args)
                        for i_arg, val in enumerate(new_args):
                            if isinstance(val, str) and ("TASK_START" in val or "MAP_START" in val or "FILE:" in val):
                                new_args[i_arg] = DOMScraper.normalize_delimiters(val)
                        return orig_fn(*tuple(new_args), **kwargs)
                    return _wrapped
                try:
                    setattr(self, ext_name, _make_ext_wrapper(fn_obj))
                    setattr(self, f"_wrapped_norm_{ext_name}", True)
                except Exception:
                    pass

        # 4. Also hook QMessageBox.warning so if "Could not find ===TASK_START===" is about to show,
        #    we automatically scan the selected Master pane (and all panes) with normalize_delimiters and delegate!
        from PyQt6.QtWidgets import QMessageBox
        if not getattr(QMessageBox, "_nexus_task_fallback_hooked", False):
            orig_warn = QMessageBox.warning
            main_win_ref = self
            def _smart_warning(parent, title, text, *rest):
                if "TASK_START" in str(text) or "No Tasks Found" in str(title):
                    main_win_ref._fallback_extract_and_delegate_from_any_master()
                    return QMessageBox.StandardButton.Ok
                return orig_warn(parent, title, text, *rest)
            QMessageBox.warning = staticmethod(_smart_warning)
            QMessageBox._nexus_task_fallback_hooked = True

    def _on_master_architect_changed_live(self, *_args):
        \"\"\"Updates master_node_id across Project, MainWindow, Orchestrator, Binary Tree, and Mind-Map when combo_master changes.\"\"\"
        if not hasattr(self, "combo_master"):
            return
        panes = getattr(self, "panes", {})
        master_id = self.combo_master.currentData()
        if not master_id or master_id not in panes:
            curr_txt = (self.combo_master.currentText() or "").strip()
            for aid, pane in panes.items():
                if pane.account_name in curr_txt or aid in curr_txt:
                    master_id = aid
                    break
        if not master_id or master_id not in panes:
            return

        proj = self._get_active_project_dict()
        proj["master_node_id"] = master_id

        for attr_name in ("master_id", "master_node_id", "active_master_id", "selected_master_id"):
            if hasattr(self, attr_name):
                setattr(self, attr_name, master_id)

        orch = getattr(self, "orchestrator", None)
        if orch is not None:
            for o_attr in ("master_id", "master_node_id"):
                if hasattr(orch, o_attr):
                    setattr(orch, o_attr, master_id)

        if hasattr(self, "binary_tree_graph") and self.binary_tree_graph is not None:
            self.binary_tree_graph.rebuild_and_layout_graph()

        for mm_attr in ("mind_map", "mind_map_widget", "architecture_map", "swarm_mind_map"):
            mm = getattr(self, mm_attr, None)
            if mm is not None:
                for fn_name in ("set_master_node", "rebuild_graph", "refresh_graph", "update_topology"):
                    if hasattr(mm, fn_name):
                        try:
                            getattr(mm, fn_name)(master_id)
                        except TypeError:
                            try:
                                getattr(mm, fn_name)()
                            except Exception:
                                pass

    def _fallback_extract_and_delegate_from_any_master(self):
        \"\"\"
        Scrapes and normalizes =MAP_START= / =TASK_START: acc_id= ... =TASK_END= from the active Master pane
        (or any pane containing a blueprint), updates the Mind-Map & Binary Tree, and delegates each task!
        \"\"\"
        import re
        from PyQt6.QtWidgets import QMessageBox
        from core.dom_scraper import DOMScraper

        panes = getattr(self, "panes", {})
        if not panes:
            return

        # Check selected Master pane first, then remaining panes
        self._on_master_architect_changed_live()
        proj = self._get_active_project_dict()
        master_id = proj.get("master_node_id")
        ordered_check = []
        if master_id and master_id in panes:
            ordered_check.append(master_id)
        for aid in panes.keys():
            if aid not in ordered_check:
                ordered_check.append(aid)

        results = {}
        pending = len(ordered_check)

        def _process_collected():
            chosen_aid = None
            chosen_text = ""
            for aid in ordered_check:
                t = results.get(aid, "")
                if "===TASK_START:" in t:
                    chosen_aid = aid
                    chosen_text = t
                    break

            if not chosen_aid or not chosen_text:
                QMessageBox.information(
                    self,
                    "Blueprint Still Generating",
                    "No ===TASK_START: account_id=== (or =TASK_START: account_id=) blocks were found in any open pane yet.\\n\\n"
                    "Wait for the Master Architect to finish generating the blueprint, then click Extract & Delegate Pipeline again."
                )
                return

            # Parse ===MAP_START=== ... ===MAP_END===
            map_rx = re.compile(r"===MAP_START===(.*?)===MAP_END===", re.DOTALL)
            node_files_map = {}
            for mm in map_rx.finditer(chosen_text):
                for ln in mm.group(1).splitlines():
                    parts = [p.strip() for p in ln.split("|")]
                    if len(parts) >= 2:
                        target_key, raw_file = parts[0], parts[1]
                        node_files_map.setdefault(target_key, []).append(raw_file)

            # Parse all ===TASK_START: <target>=== ... ===TASK_END=== blocks
            task_rx = re.compile(
                r"===TASK_START:\s*([^=\r\n]+?)\s*===(.*?)(?:===TASK_END===|(?====TASK_START:)|\Z)",
                re.DOTALL
            )
            tasks_to_send = []
            for tm in task_rx.finditer(chosen_text):
                raw_target = tm.group(1).strip()
                task_body = tm.group(2).strip()
                if not raw_target or len(task_body) < 15:
                    continue
                # Match raw_target (e.g. "acc_0_Default" or "Harivishnu9345") to actual pane account_id
                matched_id = None
                if raw_target in panes:
                    matched_id = raw_target
                else:
                    low_t = raw_target.lower()
                    for cand_id, cand_pane in panes.items():
                        if (
                            low_t in cand_id.lower() or
                            cand_id.lower() in low_t or
                            low_t in cand_pane.account_name.lower() or
                            cand_pane.account_name.lower() in low_t
                        ):
                            matched_id = cand_id
                            break
                if matched_id:
                    tasks_to_send.append((matched_id, raw_target, task_body))

            if not tasks_to_send:
                return

            # Update BinaryTreeRelayGraphWidget assigned files & status
            if hasattr(self, "binary_tree_graph") and self.binary_tree_graph is not None:
                for matched_id, raw_target, _body in tasks_to_send:
                    if matched_id in self.binary_tree_graph.node_items:
                        n_item = self.binary_tree_graph.node_items[matched_id]
                        assigned = node_files_map.get(raw_target) or node_files_map.get(matched_id) or []
                        if assigned:
                            n_item.assigned_files = assigned
                        n_item.status = "GENERATING"
                        n_item.update()
                self.binary_tree_graph._update_primary_edge_flow_states()
                self.binary_tree_graph.scene.update()

            # Dispatch each task prompt to its assigned worker pane!
            inj = getattr(self, "injector", None) or getattr(self, "dom_injector", None)
            if inj is not None:
                for matched_id, _raw_target, task_body in tasks_to_send:
                    target_pane = panes[matched_id]
                    inj.send_prompt(
                        page=target_pane.get_page(),
                        platform=target_pane.platform,
                        prompt_text=task_body,
                        file_path=None,
                        view=target_pane.web_view
                    )

        for aid in ordered_check:
            def _make_cb(acc_id=aid):
                def _on_txt(norm_txt: str):
                    nonlocal pending
                    results[acc_id] = norm_txt or ""
                    pending -= 1
                    if pending == 0:
                        _process_collected()
                return _on_txt

            DOMScraper.scrape_page_text(panes[aid].get_page(), _make_cb())
"""

marker_ensure = "    def _ensure_v19_tabs_and_signals(self):"
mw = mw.replace(
    marker_ensure,
    full_master_and_layout_block + "\n" + marker_ensure,
    1
)
if "self._setup_master_architect_sync_and_gemini_adapter()" not in mw:
    mw = mw.replace(
        "self._setup_url_tracing_and_mindmap_panel()",
        "self._setup_url_tracing_and_mindmap_panel()\n        self._setup_master_architect_sync_and_gemini_adapter()"
    )

with open("ui/main_window.py", "w", encoding="utf-8") as f:
    f.write(mw)
py_compile.compile("ui/main_window.py", doraise=True)
import ui.main_window
print("[4/4] Wrote & verified complete ui/main_window.py (all 4 sections active)")
