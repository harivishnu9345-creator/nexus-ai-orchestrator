
javascript
// src/background/swarm_coordinator.js
import '../common/contracts.js';
import { StorageManager } from './storage_manager.js';

const C = globalThis.ELAB_CONTRACTS;
const { MSG, LIMITS, AI_PROVIDERS, PROMPT_TEMPLATES } = C;

const ELAB_URL = 'https://dld.srmist.edu.in/fetelab/#/fetelab/student/home';
const ELAB_MATCH = ['*://dld.srmist.edu.in/*'];
const MAX_NEXT_CLICKS = 15;
const MAX_ATTEMPTS = LIMITS.MAX_DEBUG_ATTEMPTS; // 5
const MAX_AI_RETRIES = 2;
const RUNTIME_KEY = 'swarmRuntime';

const FALLBACK_CONFIG = Object.freeze({
  course: 'C PROGRAMMING', topic: 'INPUT & OUTPUT', level: '1',
  startQuestion: 1, totalQuestions: 10, tabCount: 1, language: 'c',
  aiProvider: 'gemini', aiModel: 'Argon', aiEfficiency: 'Medium', debugMode: false
});

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const providerEntry = (id) =>
  AI_PROVIDERS[String(id || 'gemini').toUpperCase()] || AI_PROVIDERS.GEMINI;
const pctOf = (p) => Number(String(p ?? '0').replace('%', '')) || 0;

export class SwarmCoordinator {
  constructor(options = {}) {
    this.isRunning = false;
    this.isPaused = false;
    // elabTabId -> { workerIndex, elabTabId, aiTabId, currentQuestionNumber, currentQuestionKey,
    //                status, attempts, lastQuestionData, sessionRecovering, ...internal fields }
    this.workers = new Map();

    this.inProgressQuestions = new Set();
    this.solvedQuestions = new Set();
    this.unsolvableQuestions = new Set();

    this.config = null;
    this.onStateChange = options.onStateChange || null;
    this.timers = new Map();      // elabTabId -> timeout id (AI / eval watchdogs)
    this._earlyReady = new Set(); // ELAB_TAB_READY received before the worker map existed
    this._persistTimer = null;
  }

  /* =================================================================== */
  /* Public lifecycle                                                     */
  /* =================================================================== */

  async startSwarm(config = {}) {
    if (this.isRunning) {
      await this._log('WARN', 'Swarm already running; start request ignored.');
      return this.getSwarmRuntimeSnapshot();
    }

    const stored = await StorageManager.getSwarmConfig();
    const cfg = await StorageManager.saveSwarmConfig({ ...stored, ...(config || {}) });
    cfg.tabCount = Math.min(LIMITS.MAX_SWARM_TABS, Math.max(LIMITS.MIN_SWARM_TABS, parseInt(cfg.tabCount, 10) || 1));
    this.config = cfg;

    // Reset runtime state.
    this._clearAllTimers();
    this.workers.clear();
    this.inProgressQuestions.clear();
    this.solvedQuestions.clear();
    this.unsolvableQuestions.clear();

    this._earlyReady.clear();
    this.isPaused = false;

    // Pre-load decisions from earlier runs for the same course/topic/level.
    const ledger = await StorageManager.getQuestionLedger();
    for (const [key, e] of Object.entries(ledger)) {
      if (e.course !== cfg.course || e.topic !== cfg.topic || String(e.level) !== String(cfg.level)) continue;
      if (e.status === 'SOLVED') this.solvedQuestions.add(e.questionNumber);
      else if (e.status === 'UNSOLVABLE') this.unsolvableQuestions.add(e.questionNumber);
      else if (e.status === 'IN_PROGRESS' || e.status === 'QUOTA_PAUSED') {
        await StorageManager.updateQuestionEntry(key, { status: 'PENDING', assignedTabId: null });
      }
    }

    this.isRunning = true;
    const provider = providerEntry(cfg.aiProvider);
    const usedElab = new Set();
    const usedAi = new Set();
    const existingElab = (await chrome.tabs.query({ url: ELAB_MATCH })).map((t) => t.id);

    for (let i = 0; i < cfg.tabCount; i++) {
      let elabTabId;
      let reused = false;
      const free = existingElab.find((id) => !usedElab.has(id));
      if (free !== undefined) {
        elabTabId = free;
        reused = true;
      } else {
        const t = await chrome.tabs.create({ url: ELAB_URL, active: i === 0 });
        elabTabId = t.id;
      }
      usedElab.add(elabTabId);


      const aiTab = await this._acquireAiTab(provider, usedAi);
      usedAi.add(aiTab.id);

      this.workers.set(elabTabId, this._newWorker(i, elabTabId, aiTab.id, cfg.aiProvider));

      if (reused) {
        try {
          await chrome.tabs.update(elabTabId, { url: ELAB_URL });
          await chrome.tabs.reload(elabTabId); // guarantees a fresh content-script run -> ELAB_TAB_READY
        } catch (_) { /* tab vanished; onRemoved handler will clean up */ }
      }
    }

    await this._log('INFO', `Swarm started: ${cfg.tabCount} tab(s), ${cfg.course} / ${cfg.topic} / L${cfg.level}, Q${cfg.startQuestion}-Q${cfg.startQuestion + cfg.totalQuestions - 1}, AI=${cfg.aiProvider}/${cfg.aiModel}.`);
    this._emit();

    // Tabs that reported ready while we were still building the map.
    for (const w of this.workers.values()) {
      if (this._earlyReady.has(w.elabTabId)) await this.handleTabReady(w.elabTabId, {});
    }
    this._earlyReady.clear();

    // Safety net: if a tab never reports ready, try to hand it work anyway.
    setTimeout(() => {
      if (!this.isRunning || this.isPaused) return;
      for (const w of this.workers.values()) {
        if (w.status === 'IDLE' && !this._hasActive(w)) this._assignAndNavigate(w).catch(() => {});
      }
    }, 25000);

    return this.getSwarmRuntimeSnapshot();

  }

  async stopSwarm() {
    this._clearAllTimers();
    for (const w of this.workers.values()) {
      if (this._hasActive(w)) {
        this.inProgressQuestions.delete(w.currentQuestionNumber);
        await StorageManager.updateQuestionEntry(w.currentQuestionKey, { status: 'PENDING', assignedTabId: null });
      }
    }
    const solved = this.solvedQuestions.size;
    this.workers.clear();
    this.isRunning = false;
    this.isPaused = false;
    await this._log('INFO', `Swarm stopped (${solved} solved this session).`);
    this._emit();
    return this.getSwarmRuntimeSnapshot();
  }

  async pauseSwarm(reason = 'User paused') {
    if (!this.isRunning) return this.getSwarmRuntimeSnapshot();
    this.isPaused = true;
    this._clearAllTimers();
    await this._log('WARN', `Swarm paused: ${reason}`);
    this._emit();
    return this.getSwarmRuntimeSnapshot();
  }

  async resumeSwarm() {
    if (!this.isRunning) return this.getSwarmRuntimeSnapshot();
    this.isPaused = false;
    await this._log('INFO', 'Swarm resumed.');

    for (const w of this.workers.values()) {
      if (w.status === 'QUOTA_PAUSED') continue; // needs switchAiModelAndResume
      if (w.status === 'STALLED' && w.lastRelay) {
        w.status = 'WAITING_AI';
        w.aiRetries = 0;
        w.pending = { target: 'ai', message: w.lastRelay };
      }
      if (!this._hasActive(w) && w.status !== 'DONE') await this._assignAndNavigate(w);
      else if (w.pending) await this._flush(w);
      else this._rearm(w);
    }
    this._emit();
    return this.getSwarmRuntimeSnapshot();
  }

  /** Debug-mode single step: release queued messages once, then stay paused. */
  async debugStep() {
    if (!this.isRunning) return;
    const wasPaused = this.isPaused;
    this.isPaused = false;
    await Promise.all([...this.workers.values()].map((w) => this._flush(w)));
    this.isPaused = wasPaused;
    this._emit();
  }

  /* =================================================================== */
  /* Question claiming                                                    */
  /* =================================================================== */

  claimNextQuestion(elabTabId, skippedGreenNumbers = []) {
    const worker = this.workers.get(elabTabId);
    if (!worker) return null;

    const cfg = this._cfg();
    const first = cfg.startQuestion;
    const last = first + cfg.totalQuestions - 1;

    // Slices that are already green on the Sunburst wheel -> SOLVED for everyone.
    for (const raw of skippedGreenNumbers || []) {
      const n = parseInt(raw, 10);
      if (!Number.isInteger(n) || n < first || n > last) continue;
      if (this.solvedQuestions.has(n) || this.inProgressQuestions.has(n)) continue;
      this.unsolvableQuestions.delete(n);
      this.solvedQuestions.add(n);
      StorageManager.updateQuestionEntry(this._key(n), {
        questionNumber: n, course: cfg.course, topic: cfg.topic, level: String(cfg.level),
        status: 'SOLVED', lastPercentage: 100, assignedTabId: null
      }).catch(() => {});
      this._log('INFO', `Q${n} already solved (green slice) - skipped.`, worker);
    }

    // A tab re-asking while it still owns an unfinished question resumes that question.
    const cur = worker.currentQuestionNumber;
    if (cur && this.inProgressQuestions.has(cur)) {
      return { questionNumber: cur, questionKey: worker.currentQuestionKey, useNextButton: false, nextClicksCount: 0 };
    }

    let next = null;
    for (let n = first; n <= last; n++) {
      if (!this.inProgressQuestions.has(n) && !this.solvedQuestions.has(n) && !this.unsolvableQuestions.has(n)) {
        next = n;
        break;
      }
    }
    if (next === null) return null;


    const deltaClicks = cur ? next - cur : 0;
    const key = this._key(next);

    this.inProgressQuestions.add(next);
    Object.assign(worker, {
      currentQuestionNumber: next,
      currentQuestionKey: key,
      status: 'NAVIGATING',
      attempts: 0,
      lastQuestionData: null,
      lastCode: '',
      lastEvalResult: null,
      lastRelay: null,
      lastInject: null,
      requiredComplexity: null,
      afterNav: null,
      aiRetries: 0
    });

    StorageManager.updateQuestionEntry(key, {
      questionNumber: next, course: cfg.course, topic: cfg.topic, level: String(cfg.level),
      status: 'IN_PROGRESS', attempts: 0, assignedTabId: elabTabId
    }).catch(() => {});
    this._log('INFO', `Claimed Q${next}.`, worker);
    this._emit();

    return {
      questionNumber: next,
      questionKey: key,
      useNextButton: !worker.sessionRecovering && deltaClicks > 0 && deltaClicks <= MAX_NEXT_CLICKS,
      nextClicksCount: Math.max(0, deltaClicks)

    };
  }

  /* =================================================================== */
  /* Pipeline handlers                                                    */
  /* =================================================================== */

  async handleQuestionScraped(elabTabId, questionData) {
    const worker = this.workers.get(elabTabId);
    if (!worker) return;
    const cfg = this._cfg();

    worker.lastQuestionData = questionData || null;
    const req = this._extractRequirements(questionData);
    worker.requiredComplexity = req.requiredComplexity;

    const afterNav = worker.afterNav;
    worker.afterNav = null;

    if (afterNav === 'IGNORE' || worker.status === 'QUOTA_PAUSED') {
      this._emit();
      return;
    }
    if (afterNav === 'INJECT') {
      worker.status = 'EVALUATING';
      if (worker.lastInject) await this._dispatch(worker, 'elab', worker.lastInject);
      return;
    }

    await StorageManager.updateQuestionEntry(worker.currentQuestionKey, {
      mandatoryKeywords: req.mandatoryKeywords,
      requiredComplexity: req.requiredComplexity,

      status: 'IN_PROGRESS',
      assignedTabId: elabTabId
    });

    await this._ensureWorkerAiTab(worker);
    const prompt = PROMPT_TEMPLATES.buildInitialPrompt(questionData, cfg.language);
    const message = {
      action: MSG.RELAY_PROMPT_TO_AI,
      prompt,
      aiModel: cfg.aiModel,
      aiEfficiency: cfg.aiEfficiency,
      isNewChat: true
    };
    worker.lastRelay = message;
    worker.status = 'WAITING_AI';
    worker.aiRetries = 0;
    await this._log('INFO', `Q${worker.currentQuestionNumber} scraped; prompt relayed to AI.`, worker);
    await this._dispatch(worker, 'ai', message);
  }

  async handleAiCodeResponse(aiTabId, code) {
    const worker = this._byAiTab(aiTabId);
    if (!worker) return;
    if (worker.status !== 'WAITING_AI') {
      await this._log('WARN', `Unexpected AI response ignored (worker status ${worker.status}).`, worker);
      return;
    }
    const text = String(code ?? '').trim();
    if (!text) {
      await this._log('WARN', 'AI returned empty code; waiting for retry/timeout.', worker);
      return;
    }

    const cfg = this._cfg();
    this._clearTimer(worker.elabTabId);
    worker.aiRetries = 0;
    worker.lastCode = text;
    worker.status = 'EVALUATING';
    const message = { action: MSG.INJECT_AND_EVALUATE, code: text, language: cfg.language };
    worker.lastInject = message;

    StorageManager.updateQuestionEntry(worker.currentQuestionKey, { lastCode: text }).catch(() => {});
    await this._log('INFO', 'AI code received; injecting into eLab for evaluation.', worker);

    if (worker.sessionRecovering || worker.afterNav === 'IGNORE') {
      // eLab page is mid-navigation/re-login: inject once the question has been re-scraped.
      worker.afterNav = 'INJECT';
      this._emit();
      return;
    }
    await this._dispatch(worker, 'elab', message);
  }

  async handleEvaluationResult(elabTabId, evalResult = {}) {
    const worker = this.workers.get(elabTabId);
    if (!worker || !worker.currentQuestionNumber) return;
    const r = evalResult || {};
    const status = String(r.status || '').toUpperCase();

    if (r.questionNumber != null && Number(r.questionNumber) !== worker.currentQuestionNumber) {
      await this._log('WARN', `Stale evaluation for Q${r.questionNumber} ignored.`, worker);
      return;
    }
    if (status !== 'SOLVED' && worker.status !== 'EVALUATING') return;


    this._clearTimer(elabTabId);
    worker.lastEvalResult = r;
    const qn = worker.currentQuestionNumber;
    const key = worker.currentQuestionKey;

    /* ------------------------------ SOLVED ------------------------------ */
    if (status === 'SOLVED') {
      await StorageManager.updateQuestionEntry(key, {
        status: 'SOLVED',
        attempts: worker.attempts + 1,
        lastPercentage: 100,
        failedBadges: [],
        compilerError: '',
        measuredComplexity: r.measuredComplexity || {},
        lastCode: r.code || worker.lastCode || '',
        assignedTabId: null
      });
      this.solvedQuestions.add(qn);
      this.inProgressQuestions.delete(qn);
      worker.status = 'IDLE';
      await this._log('SUCCESS', `Q${qn} SOLVED (100%).`, worker);
      this._debugGate();
      await this._assignAndNavigate(worker, r.skippedGreenNumbers || []);
      return;
    }

    /* -------------------- COMPILE_ERROR / PARTIAL_FAIL ------------------- */
    if (status !== 'COMPILE_ERROR' && status !== 'PARTIAL_FAIL') {
      await this._log('WARN', `Unrecognised evaluation status "${status}" treated as PARTIAL_FAIL.`, worker);
    }

    worker.attempts += 1;

    const code = r.code || worker.lastCode || '';
    await StorageManager.updateQuestionEntry(key, {
      status: 'IN_PROGRESS',
      attempts: worker.attempts,
      lastPercentage: pctOf(r.percentage),
      failedBadges: Array.isArray(r.failedBadges) ? r.failedBadges : [],
      compilerError: r.compilerError ? String(r.compilerError) : '',
      measuredComplexity: r.measuredComplexity || {},
      lastCode: code
    });

    if (worker.attempts >= MAX_ATTEMPTS) {
      await this._giveUp(worker, { ...r, lastCode: r.code });
      return;
    }

    const cfg = this._cfg();
    const debugPrompt = PROMPT_TEMPLATES.buildDebugPrompt(worker.lastQuestionData, r, worker.attempts, cfg.language);
    const message = { action: MSG.RELAY_PROMPT_TO_AI, prompt: debugPrompt, isNewChat: false };
    worker.lastRelay = message;
    worker.status = 'WAITING_AI';
    worker.aiRetries = 0;
    await this._log('WARN', `Q${qn} attempt ${worker.attempts}/${MAX_ATTEMPTS} failed (${pctOf(r.percentage)}%); requesting fix.`, worker);
    this._debugGate();
    await this._dispatch(worker, 'ai', message);
  }

  /** Externally flagged unsolvable (MSG.MARK_UNSOLVABLE). */
  async handleMarkUnsolvable(elabTabId, details = {}) {
    const worker = this.workers.get(elabTabId);
    if (!worker || !this._hasActive(worker)) return;
    await this._giveUp(worker, details || {});

  }

  async handleSessionExpired(elabTabId) {
    const worker = this.workers.get(elabTabId);
    if (!worker) return;
    worker.sessionRecovering = true; // currentQuestionNumber / attempts deliberately preserved
    this._clearTimer(elabTabId);
    if (this._hasActive(worker) && worker.afterNav !== 'INJECT') {
      worker.afterNav = this._afterNavFor(worker.status);
    }
    if (worker.pending && worker.pending.target === 'elab') worker.pending = null;
    await this._log('WARN', 'eLab session expired; waiting for re-login.', worker);
    this._emit();
  }

  async handleLoginSuccess(elabTabId) {
    const worker = this.workers.get(elabTabId);
    if (!worker) return;
    const wasRecovering = worker.sessionRecovering;
    worker.sessionRecovering = false;
    await this._log('INFO', 'eLab login successful.', worker);

    if (!this._hasActive(worker)) {
      if (worker.status !== 'QUOTA_PAUSED') await this._assignAndNavigate(worker);
      return;
    }
    if (wasRecovering || worker.status === 'NAVIGATING') {
      await this._dispatch(worker, 'elab', this._navMessage(this._claimOf(worker), { isRecovery: true }));
    } else {
      await this._flush(worker);
    }
  }


  async handleTabReady(tabId, payload = {}) {
    const worker = this.workers.get(tabId);
    if (!worker) {
      const aiWorker = this._byAiTab(tabId);
      if (aiWorker) await this._flush(aiWorker); // AI tab finished loading; resend anything queued
      else if (this.isRunning) this._earlyReady.add(tabId);
      return;
    }
    if (payload && payload.loggedIn === false) return;

    if (!this._hasActive(worker)) {
      if (worker.status !== 'QUOTA_PAUSED' && worker.status !== 'DONE') await this._assignAndNavigate(worker);
      return;
    }
    // Page was (re)loaded while we own a question -> re-navigate to it.
    if (worker.afterNav !== 'INJECT') worker.afterNav = this._afterNavFor(worker.status);
    await this._dispatch(worker, 'elab', this._navMessage(this._claimOf(worker), { isRecovery: true }));
  }

  async handleQuotaExceeded(aiTabId, provider, details) {
    const worker = this._byAiTab(aiTabId);
    if (!worker) {
      await this._log('WARN', `Quota signal from unpaired AI tab ${aiTabId} ignored.`);
      return;
    }
    this._clearTimer(worker.elabTabId);
    // attempts intentionally NOT incremented
    worker.status = 'QUOTA_PAUSED';
    worker.pending = worker.lastRelay ? { target: 'ai', message: worker.lastRelay } : null;

    if (worker.currentQuestionKey) {

      await StorageManager.updateQuestionEntry(worker.currentQuestionKey, { status: 'QUOTA_PAUSED' });
    }
    const pid = String(provider || worker.aiProvider || '').toLowerCase();
    await this._log('ERROR', `AI quota exceeded on ${pid}. Switch provider/model to continue.`, worker);
    StorageManager.notify(
      'AI quota exceeded',
      `${pid || 'AI provider'} hit its limit. Open the eLab Swarm panel and switch AI provider/model to resume.`,
      'elab-quota'
    );
    try {
      await chrome.runtime.sendMessage({
        action: MSG.AI_QUOTA_EXCEEDED,
        provider: pid,
        aiTabId,
        elabTabId: worker.elabTabId,
        workerIndex: worker.workerIndex,
        questionNumber: worker.currentQuestionNumber,
        details: details ?? null
      });
    } catch (_) { /* popup closed */ }
    this._emit();
  }

  async switchAiModelAndResume(newProvider, newModel, newEfficiency) {
    const before = this._cfg();
    const providerId = String(newProvider || before.aiProvider).toLowerCase();
    const saved = await StorageManager.saveSwarmConfig({
      aiProvider: providerId,
      aiModel: newModel ?? before.aiModel,
      aiEfficiency: newEfficiency ?? before.aiEfficiency
    });
    this.config = saved;

    const providerChanged = saved.aiProvider !== before.aiProvider;
    const settingsChanged = providerChanged || saved.aiModel !== before.aiModel || saved.aiEfficiency !== before.aiEfficiency;
    await this._log('INFO', `AI switched to ${saved.aiProvider}/${saved.aiModel}/${saved.aiEfficiency}.`);

    for (const worker of this.workers.values()) {
      if (worker.status !== 'QUOTA_PAUSED') continue;
      if (providerChanged || worker.aiProvider !== saved.aiProvider) await this._ensureWorkerAiTab(worker);

      worker.aiRetries = 0;
      if (!worker.lastQuestionData && !worker.lastRelay) {
        // Paused before the question was scraped: just re-navigate.
        worker.status = 'NAVIGATING';
        await StorageManager.updateQuestionEntry(worker.currentQuestionKey, { status: 'IN_PROGRESS' });
        await this._dispatch(worker, 'elab', this._navMessage(this._claimOf(worker), { isRecovery: true }));
        continue;
      }

      let message;
      if (worker.lastRelay && (worker.lastRelay.isNewChat !== false || !settingsChanged)) {
        message = { ...worker.lastRelay };
        if (message.isNewChat) { message.aiModel = saved.aiModel; message.aiEfficiency = saved.aiEfficiency; }
      } else {
        message = this._freshRelay(worker); // debug prompt on a new chat/model needs full context
      }
      worker.lastRelay = message;
      worker.status = 'WAITING_AI';
      await StorageManager.updateQuestionEntry(worker.currentQuestionKey, { status: 'IN_PROGRESS' });
      await this._log('INFO', `Resuming Q${worker.currentQuestionNumber} on ${saved.aiProvider}.`, worker);
      await this._dispatch(worker, 'ai', message);
    }
    this._emit();
    return this.getSwarmRuntimeSnapshot();

  }

  async handleTabClosed(tabId) {
    this._earlyReady.delete(tabId);
    const worker = this.workers.get(tabId);
    if (worker) {
      this._clearTimer(tabId);
      if (this._hasActive(worker)) {
        this.inProgressQuestions.delete(worker.currentQuestionNumber);
        await StorageManager.updateQuestionEntry(worker.currentQuestionKey, { status: 'PENDING', assignedTabId: null });
      }
      this.workers.delete(tabId);
      await this._log('WARN', `eLab worker tab ${tabId} closed; its question was released.`, worker);
      if (this.isRunning && this.workers.size === 0) {
        this.isRunning = false;
        await this._log('WARN', 'All worker tabs closed; swarm stopped.');
      }
      this._emit();
      return;
    }
    const aiWorker = this._byAiTab(tabId);
    if (aiWorker) {
      aiWorker.aiTabId = null;
      await this._log('WARN', `AI tab ${tabId} closed; reopening.`, aiWorker);
      if (this.isRunning) {
        await this._ensureWorkerAiTab(aiWorker);
        if (aiWorker.status === 'WAITING_AI' && aiWorker.lastQuestionData) {
          const msg = this._freshRelay(aiWorker);
          aiWorker.lastRelay = msg;
          await this._dispatch(aiWorker, 'ai', msg);
        }
      }

      this._emit();
    }
  }

  getSwarmRuntimeSnapshot() {
    return {
      isRunning: this.isRunning,
      isPaused: this.isPaused,
      workers: Array.from(this.workers.values()),
      solvedCount: this.solvedQuestions.size,
      unsolvableCount: this.unsolvableQuestions.size
    };
  }

  /* =================================================================== */
  /* Public utilities used by background.js                               */
  /* =================================================================== */

  async sendToTab(tabId, message, retries = 6, delayMs = 1500) {
    for (let i = 0; i <= retries; i++) {
      try {
        await chrome.tabs.sendMessage(tabId, message);
        return true;
      } catch (err) {
        const msg = String(err && err.message || err);
        if (/No tab with id/i.test(msg) || i === retries) {
          await this._log('ERROR', `Could not deliver ${message.action} to tab ${tabId}: ${msg}`);
          return false;
        }
        await sleep(delayMs);
      }
    }

    return false;
  }

  /** Finds (or opens) an AI tab not paired with any worker - used for model scanning. */
  async getOrOpenAiTab(providerId) {
    const used = new Set([...this.workers.values()].map((w) => w.aiTabId));
    return this._acquireAiTab(providerEntry(providerId), used);
  }

  /** Restore runtime after the MV3 service worker was suspended and restarted. */
  async restore() {
    try {
      const out = await chrome.storage.session.get(RUNTIME_KEY);
      const s = out[RUNTIME_KEY];
      if (!s || !s.isRunning || this.isRunning) return false;
      this.config = s.config || null;
      this.isRunning = true;
      this.isPaused = !!s.isPaused;
      this.workers = new Map((s.workers || []).map((w) => [w.elabTabId, w]));
      this.inProgressQuestions = new Set(s.inProgress || []);
      this.solvedQuestions = new Set(s.solved || []);
      this.unsolvableQuestions = new Set(s.unsolvable || []);
      for (const w of this.workers.values()) {
        await this._flush(w);
        this._rearm(w);
      }
      await this._log('INFO', 'Swarm runtime restored after service-worker restart.');
      this._emit();
      return true;
    } catch (_) {
      return false;
    }

  }

  /* =================================================================== */
  /* Internals                                                            */
  /* =================================================================== */

  _cfg() { return this.config || FALLBACK_CONFIG; }

  _key(n) {
    const c = this._cfg();
    return StorageManager.makeQuestionKey(c.course, c.topic, c.level, n);
  }

  _log(level, message, worker = null) {
    return StorageManager.addLog(
      level, message, worker ? worker.elabTabId : null, worker ? worker.currentQuestionNumber : null
    ).catch(() => {});
  }

  _newWorker(index, elabTabId, aiTabId, providerId) {
    return {
      workerIndex: index,
      elabTabId,
      aiTabId,
      currentQuestionNumber: null,
      currentQuestionKey: null,
      status: 'IDLE', // IDLE | NAVIGATING | WAITING_AI | EVALUATING | QUOTA_PAUSED | STALLED | DONE
      attempts: 0,
      lastQuestionData: null,
      sessionRecovering: false,
      // internal bookkeeping
      aiProvider: providerId,

      lastCode: '',
      lastEvalResult: null,
      lastRelay: null,
      lastInject: null,
      requiredComplexity: null,
      pending: null,   // { target: 'ai' | 'elab', message } not yet delivered
      afterNav: null,  // null | 'IGNORE' | 'INJECT' - what to do on next QUESTION_SCRAPED
      aiRetries: 0
    };
  }

  _hasActive(w) {
    return !!(w.currentQuestionNumber && this.inProgressQuestions.has(w.currentQuestionNumber));
  }

  _byAiTab(aiTabId) {
    for (const w of this.workers.values()) if (w.aiTabId === aiTabId) return w;
    return null;
  }

  _claimOf(w) {
    return { questionNumber: w.currentQuestionNumber, questionKey: w.currentQuestionKey, useNextButton: false, nextClicksCount: 0 };
  }

  _afterNavFor(status) {
    if (status === 'NAVIGATING' || status === 'IDLE') return null;
    if (status === 'EVALUATING') return 'INJECT';
    return 'IGNORE';
  }

  _navMessage(claim, extra = {}) {
    const c = this._cfg();

    return { action: MSG.NAVIGATE_TO_QUESTION, ...claim, course: c.course, topic: c.topic, level: String(c.level), ...extra };
  }

  _extractRequirements(q) {
    q = q || {};
    const nonEmpty = (v) => {
      if (v === undefined || v === null) return false;
      if (Array.isArray(v)) return v.length > 0;
      if (typeof v === 'object') return Object.keys(v).length > 0;
      return String(v).trim() !== '';
    };
    const first = (keys) => { for (const k of keys) if (nonEmpty(q[k])) return q[k]; return undefined; };
    const mandatory = first(['mandatoryKeywords', 'mandatoryTestCases', 'mandatoryTests', 'keywords']);
    const mandatoryKeywords = Array.isArray(mandatory)
      ? mandatory.map((m) => (typeof m === 'string' ? m : (m && (m.keyword ?? m.text ?? m.value ?? m.pattern)) || '')).filter(Boolean)
      : [];
    const requiredComplexity = first(['complexityTargets', 'complexityTestCases', 'complexity']) ?? {};
    return { mandatoryKeywords, requiredComplexity };
  }

  /** Initial prompt (+ pending debug prompt) for a brand-new chat. */
  _freshRelay(worker) {
    const cfg = this._cfg();
    const base = worker.lastRelay;
    const initial = PROMPT_TEMPLATES.buildInitialPrompt(worker.lastQuestionData, cfg.language);
    const prompt = base && base.isNewChat === false ? `${initial}\n\n${base.prompt}` : (base ? base.prompt : initial);
    return { action: MSG.RELAY_PROMPT_TO_AI, prompt, aiModel: cfg.aiModel, aiEfficiency: cfg.aiEfficiency, isNewChat: true };
  }

  /** In debug mode, hold the pipeline after each evaluation until the user steps/resumes. */
  _debugGate() {
    if (this._cfg().debugMode && this.isRunning && !this.isPaused) {

      this.isPaused = true;
      this._clearAllTimers();
      this._log('WARN', 'Debug mode: paused after evaluation. Use Step or Resume.');
    }
  }

  async _assignAndNavigate(worker, skipped = []) {
    const claim = this.claimNextQuestion(worker.elabTabId, skipped);
    if (!claim) {
      this._finishWorker(worker);
      return null;
    }
    await this._dispatch(worker, 'elab', this._navMessage(claim));
    return claim;
  }

  _finishWorker(worker) {
    worker.status = 'DONE';
    worker.pending = null;
    this._log('SUCCESS', 'No more unclaimed questions for this tab.', worker);
    const all = [...this.workers.values()];
    if (all.length && all.every((w) => w.status === 'DONE' || w.status === 'STALLED') && all.some((w) => w.status === 'DONE')) {
      this.isRunning = false;
      this._clearAllTimers();
      this._log('SUCCESS', `Swarm complete: ${this.solvedQuestions.size} solved, ${this.unsolvableQuestions.size} unsolvable.`);
      StorageManager.notify(
        'eLab Swarm finished',
        `${this.solvedQuestions.size} solved, ${this.unsolvableQuestions.size} unsolvable.`,
        'elab-complete'
      );
    }
    this._emit();

  }

  async _giveUp(worker, details) {
    const qn = worker.currentQuestionNumber;
    await StorageManager.markQuestionUnsolvable(worker.currentQuestionKey, {
      ...details,
      lastCode: details.lastCode ?? worker.lastCode,
      requiredComplexity: details.requiredComplexity ?? worker.requiredComplexity ?? {}
    });
    this.unsolvableQuestions.add(qn);
    this.inProgressQuestions.delete(qn);
    worker.status = 'IDLE';
    worker.pending = null;
    this._clearTimer(worker.elabTabId);
    await this._log('ERROR', `Q${qn} UNSOLVABLE - moving on.`, worker);
    this._debugGate();
    await this._assignAndNavigate(worker);
  }

  /* ----------------------------- messaging -------------------------- */
  async _dispatch(worker, target, message) {
    worker.pending = { target, message };
    this._emit();
    return this._flush(worker);
  }

  async _flush(worker) {
    const p = worker.pending;
    if (!p) return false;
    if (!this.isRunning || this.isPaused) return false;
    if (worker.status === 'QUOTA_PAUSED') return false;
    if (p.target === 'elab' && worker.sessionRecovering) return false;


    const tabId = p.target === 'ai' ? worker.aiTabId : worker.elabTabId;
    if (tabId === null || tabId === undefined) return false;

    worker.pending = null; // clear first so concurrent flushes can't double-send
    const ok = await this.sendToTab(tabId, p.message);
    if (!ok) {
      worker.pending = p; // keep for the next ready/resume event
      return false;
    }
    if (p.message.action === MSG.RELAY_PROMPT_TO_AI) {
      this._arm(worker, LIMITS.AI_RESPONSE_TIMEOUT_MS, () => this._onAiTimeout(worker));
    } else if (p.message.action === MSG.INJECT_AND_EVALUATE) {
      this._arm(worker, LIMITS.EVAL_TIMEOUT_MS, () => this._onEvalTimeout(worker));
    }
    this._emit();
    return true;
  }

  async _ensureWorkerAiTab(worker) {
    const cfg = this._cfg();
    if (worker.aiTabId !== null && worker.aiTabId !== undefined && worker.aiProvider === cfg.aiProvider) {
      try {
        await chrome.tabs.get(worker.aiTabId);
        return worker.aiTabId;
      } catch (_) { /* tab gone - reacquire below */ }
    }
    const used = new Set([...this.workers.values()].filter((w) => w !== worker).map((w) => w.aiTabId));
    const tab = await this._acquireAiTab(providerEntry(cfg.aiProvider), used);
    worker.aiTabId = tab.id;
    worker.aiProvider = cfg.aiProvider;
    return tab.id;

  }

  async _acquireAiTab(provider, usedIds) {
    const existing = await chrome.tabs.query({ url: provider.matchPattern });
    const free = existing.find((t) => !usedIds.has(t.id));
    if (free) return free;
    return chrome.tabs.create({ url: provider.url, active: false });
  }

  /* ------------------------------ timers ---------------------------- */
  _arm(worker, ms, fn) {
    this._clearTimer(worker.elabTabId);
    const id = setTimeout(() => {
      this.timers.delete(worker.elabTabId);
      if (!this.isRunning || this.isPaused) return;
      fn().catch(() => {});
    }, ms);
    this.timers.set(worker.elabTabId, id);
  }

  _clearTimer(elabTabId) {
    const id = this.timers.get(elabTabId);
    if (id !== undefined) clearTimeout(id);
    this.timers.delete(elabTabId);
  }

  _clearAllTimers() {
    for (const id of this.timers.values()) clearTimeout(id);
    this.timers.clear();
  }

  _rearm(worker) {

    if (this.timers.has(worker.elabTabId) || worker.pending || !this.isRunning || this.isPaused) return;
    if (worker.status === 'WAITING_AI') this._arm(worker, LIMITS.AI_RESPONSE_TIMEOUT_MS, () => this._onAiTimeout(worker));
    else if (worker.status === 'EVALUATING') this._arm(worker, LIMITS.EVAL_TIMEOUT_MS, () => this._onEvalTimeout(worker));
  }

  async _onAiTimeout(worker) {
    if (worker.status !== 'WAITING_AI') return;
    worker.aiRetries = (worker.aiRetries || 0) + 1;
    if (worker.aiRetries <= MAX_AI_RETRIES && worker.lastRelay) {
      await this._log('WARN', `AI response timeout; resending prompt (retry ${worker.aiRetries}/${MAX_AI_RETRIES}).`, worker);
      await this._dispatch(worker, 'ai', worker.lastRelay);
      return;
    }
    worker.status = 'STALLED';
    await this._log('ERROR', 'AI did not respond after retries; worker stalled. Check the AI tab, then Resume.', worker);
    StorageManager.notify('eLab Swarm stalled', `Worker ${worker.workerIndex + 1} got no AI response.`, `elab-stalled-${worker.elabTabId}`);
    this._emit();
  }

  async _onEvalTimeout(worker) {
    if (worker.status !== 'EVALUATING') return;
    await this._log('WARN', 'eLab evaluation timed out; counting as a failed attempt.', worker);
    await this.handleEvaluationResult(worker.elabTabId, {
      status: 'PARTIAL_FAIL',
      percentage: 0,
      failedBadges: ['Evaluation timed out on eLab'],
      compilerError: '',
      code: worker.lastCode
    });
  }

  /* ---------------------------- persistence ------------------------- */

  _emit() {
    this._schedulePersist();
    try { if (this.onStateChange) this.onStateChange(); } catch (_) { /* ignore */ }
  }

  _schedulePersist() {
    if (this._persistTimer) return;
    this._persistTimer = setTimeout(async () => {
      this._persistTimer = null;
      try {
        await chrome.storage.session.set({
          [RUNTIME_KEY]: {
            isRunning: this.isRunning,
            isPaused: this.isPaused,
            config: this.config,
            workers: Array.from(this.workers.values()),
            inProgress: [...this.inProgressQuestions],
            solved: [...this.solvedQuestions],
            unsolvable: [...this.unsolvableQuestions],
            savedAt: Date.now()
          }
        });
      } catch (_) { /* session storage unavailable */ }
    }, 300);
  }
}
