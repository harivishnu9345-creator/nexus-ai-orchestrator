
javascript
// src/background/background.js
import '../common/contracts.js';
import { StorageManager } from './storage_manager.js';
import { SwarmCoordinator } from './swarm_coordinator.js';

const { MSG, AI_PROVIDERS } = globalThis.ELAB_CONTRACTS;

/* ------------------------------------------------------------------ */
/* Bootstrap                                                          */
/* ------------------------------------------------------------------ */
const coordinator = new SwarmCoordinator();

// Every handler awaits `ready` so a cold-started service worker never races its own init.
const ready = (async () => {
  await StorageManager.initDefaults();
  await coordinator.restore();
})().catch((err) => console.error('[eLab Swarm] init failed', err));

/* ------------------------------------------------------------------ */
/* State broadcast                                                    */
/* ------------------------------------------------------------------ */
async function broadcastStateUpdate() {
  try {
    const state = await StorageManager.getFullState();
    state.runtime = coordinator.getSwarmRuntimeSnapshot();
    await chrome.runtime.sendMessage({ action: MSG.STATE_UPDATED, state });
  } catch (_) {
    /* no popup open - nothing to notify */
  }
}

let broadcastTimer = null;

function scheduleBroadcast() {
  if (broadcastTimer) return;
  broadcastTimer = setTimeout(() => {
    broadcastTimer = null;
    broadcastStateUpdate();
  }, 150);
}
coordinator.onStateChange = scheduleBroadcast;

/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */
function providerFromUrl(url) {
  try {
    const host = new URL(url).hostname;
    for (const p of Object.values(AI_PROVIDERS)) {
      if (new URL(p.url).hostname === host) return p.id;
    }
  } catch (_) { /* ignore */ }
  return null;
}

function stripAction(msg) {
  const { action, ...rest } = msg;
  return rest;
}

const HANDLED = new Set([
  MSG.GET_STATE, MSG.SAVE_CREDENTIALS, MSG.START_SWARM, MSG.STOP_SWARM, MSG.PAUSE_SWARM,
  MSG.SCAN_AI_MODELS, MSG.AI_MODELS_SCANNED, MSG.SWITCH_AI_MODEL,
  MSG.ELAB_TAB_READY, MSG.ELAB_SESSION_EXPIRED, MSG.ELAB_LOGIN_SUCCESS,
  MSG.ASSIGN_QUESTION, MSG.QUESTION_SCRAPED, MSG.AI_CODE_RESPONSE, MSG.AI_QUOTA_EXCEEDED,

  MSG.EVALUATION_RESULT, MSG.MARK_UNSOLVABLE, MSG.DEBUG_STEP_ACTION, MSG.LOG_EVENT
]);

/* ------------------------------------------------------------------ */
/* Message router                                                     */
/* ------------------------------------------------------------------ */
async function handleMessage(msg, sender) {
  await ready;
  const tabId = sender && sender.tab ? sender.tab.id : (msg.tabId ?? null);

  switch (msg.action) {
    case MSG.GET_STATE: {
      const state = await StorageManager.getFullState();
      state.runtime = coordinator.getSwarmRuntimeSnapshot();
      return { ok: true, state };
    }

    case MSG.SAVE_CREDENTIALS: {
      const c = msg.credentials || msg;
      const saved = await StorageManager.saveCredentials(c.username, c.password, c.autoLogin);
      await StorageManager.addLog('INFO', `Credentials saved for ${saved.username} (auto-login ${saved.autoLogin ? 'on' : 'off'}).`);
      return { ok: true, credentials: saved };
    }

    case MSG.START_SWARM: {
      const runtime = await coordinator.startSwarm(msg.config || {});
      return { ok: true, runtime };
    }

    case MSG.STOP_SWARM:
      return { ok: true, runtime: await coordinator.stopSwarm() };


    case MSG.PAUSE_SWARM: {
      const wantsResume = msg.resume === true || msg.paused === false ||
        (msg.resume === undefined && msg.paused === undefined && coordinator.isPaused);
      const runtime = wantsResume
        ? await coordinator.resumeSwarm()
        : await coordinator.pauseSwarm(msg.reason || 'User paused');
      return { ok: true, runtime };
    }

    case MSG.SCAN_AI_MODELS: {
      const cfg = await StorageManager.getSwarmConfig();
      const provider = String(msg.provider || cfg.aiProvider).toLowerCase();
      const tab = await coordinator.getOrOpenAiTab(provider);
      const delivered = await coordinator.sendToTab(tab.id, { action: MSG.SCAN_AI_MODELS, provider });
      await StorageManager.addLog(delivered ? 'INFO' : 'ERROR',
        delivered ? `Scanning ${provider} models...` : `Could not reach ${provider} tab for model scan.`);
      return { ok: delivered, provider, tabId: tab.id };
    }

    case MSG.AI_MODELS_SCANNED: {
      const provider = String(msg.provider || providerFromUrl(sender && sender.tab && sender.tab.url) || '').toLowerCase();
      const data = msg.inventory || msg.data || msg;
      const entry = await StorageManager.updateAiInventory(provider, {
        plan: data.plan, models: data.models, efficiencies: data.efficiencies
      });
      await StorageManager.addLog('SUCCESS',
        `${provider}: plan ${entry.plan}, ${entry.models.length} model(s), ${entry.efficiencies.length} efficiency level(s).`);
      return { ok: true, provider, inventory: entry };
    }

    case MSG.SWITCH_AI_MODEL: {
      const runtime = await coordinator.switchAiModelAndResume(

        msg.provider, msg.model ?? msg.aiModel, msg.efficiency ?? msg.aiEfficiency
      );
      return { ok: true, runtime };
    }

    case MSG.ELAB_TAB_READY:
      await coordinator.handleTabReady(tabId, msg);
      return { ok: true };

    case MSG.ELAB_SESSION_EXPIRED:
      await coordinator.handleSessionExpired(tabId);
      return { ok: true };

    case MSG.ELAB_LOGIN_SUCCESS:
      await coordinator.handleLoginSuccess(tabId);
      return { ok: true };

    case MSG.ASSIGN_QUESTION: {
      const skipped = msg.skippedGreenNumbers || msg.skippedGreen || msg.skipped || [];
      const claim = coordinator.claimNextQuestion(tabId, skipped);
      return { ok: true, claim, ...(claim || { done: true }) };
    }

    case MSG.QUESTION_SCRAPED:
      await coordinator.handleQuestionScraped(tabId, msg.questionData ?? msg.data ?? stripAction(msg));
      return { ok: true };

    case MSG.AI_CODE_RESPONSE:
      await coordinator.handleAiCodeResponse(tabId, msg.code);
      return { ok: true };

    case MSG.AI_QUOTA_EXCEEDED: {

      const provider = msg.provider || providerFromUrl(sender && sender.tab && sender.tab.url);
      await coordinator.handleQuotaExceeded(tabId, provider, msg.details ?? msg.reason ?? null);
      return { ok: true };
    }

    case MSG.EVALUATION_RESULT:
      await coordinator.handleEvaluationResult(tabId, msg.evalResult ?? msg.result ?? stripAction(msg));
      return { ok: true };

    case MSG.MARK_UNSOLVABLE:
      await coordinator.handleMarkUnsolvable(tabId, msg.details ?? stripAction(msg));
      return { ok: true };

    case MSG.DEBUG_STEP_ACTION: {
      const step = String(msg.step ?? msg.type ?? msg.command ?? '').toUpperCase();
      if (step === 'PAUSE') await coordinator.pauseSwarm('Debug pause');
      else if (step === 'RESUME' || step === 'CONTINUE') await coordinator.resumeSwarm();
      else if (step === 'STEP' || step === 'NEXT') await coordinator.debugStep();
      else await StorageManager.addLog('WARN', `Unknown debug step action: ${step || '(none)'}`);
      return { ok: true, runtime: coordinator.getSwarmRuntimeSnapshot() };
    }

    case MSG.LOG_EVENT:
      await StorageManager.addLog(msg.level || 'INFO', msg.message, tabId, msg.questionNumber ?? null);
      return { ok: true };

    default:
      return { ok: false, error: `Unhandled action ${msg.action}` };
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {

  if (!msg || typeof msg.action !== 'string' || !HANDLED.has(msg.action)) return false;

  handleMessage(msg, sender).then(
    (res) => sendResponse(res === undefined ? { ok: true } : res),
    async (err) => {
      const message = String((err && err.message) || err);
      console.error(`[eLab Swarm] ${msg.action} failed:`, err);
      try { await StorageManager.addLog('ERROR', `${msg.action} failed: ${message}`); } catch (_) { /* ignore */ }
      sendResponse({ ok: false, error: message });
    }
  );
  return true; // keep the channel open for the async response
});

/* ------------------------------------------------------------------ */
/* Browser event wiring                                               */
/* ------------------------------------------------------------------ */
chrome.tabs.onRemoved.addListener((tabId) => {
  ready.then(() => coordinator.handleTabClosed(tabId)).catch(() => {});
});

// Any storage change (logs, ledger, credentials, config) refreshes open popups.
chrome.storage.onChanged.addListener((_changes, area) => {
  if (area === 'local') scheduleBroadcast();
});

chrome.runtime.onInstalled.addListener(() => {
  StorageManager.initDefaults().catch(() => {});
});

chrome.runtime.onStartup.addListener(() => {
  ready.catch(() => {});

});

chrome.notifications.onClicked.addListener((id) => {
  chrome.notifications.clear(id);
});
