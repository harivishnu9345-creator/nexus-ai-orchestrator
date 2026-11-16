JavaScript
/**
 * contracts.js — shared interface contract for SRM eLab Swarm Solver & AI Relay (v6.0)
 *
 * Works in:
 *  - Classic content scripts (loaded via manifest "js"): sets globalThis.ELAB_CONTRACTS
 *  - ES module contexts (service worker, popup): `import '../common/contracts.js';`
 *    then read `globalThis.ELAB_CONTRACTS`.
 *  - MAIN world injection (<script src=chrome.runtime.getURL(...)>).
 */
(function (root) {
  'use strict';

  // Idempotent: don't redefine if already loaded in this realm.
  if (root.ELAB_CONTRACTS) return;

  /* ------------------------------------------------------------------ */
  /* Message action types                                               */
  /* ------------------------------------------------------------------ */
  const MSG = Object.freeze({
    SAVE_CREDENTIALS: 'SAVE_CREDENTIALS',
    GET_STATE: 'GET_STATE',
    START_SWARM: 'START_SWARM',
    STOP_SWARM: 'STOP_SWARM',
    PAUSE_SWARM: 'PAUSE_SWARM',
    SCAN_AI_MODELS: 'SCAN_AI_MODELS',
    AI_MODELS_SCANNED: 'AI_MODELS_SCANNED',
    SWITCH_AI_MODEL: 'SWITCH_AI_MODEL',
    ELAB_TAB_READY: 'ELAB_TAB_READY',
    ELAB_SESSION_EXPIRED: 'ELAB_SESSION_EXPIRED',
    ELAB_LOGIN_SUCCESS: 'ELAB_LOGIN_SUCCESS',
    ASSIGN_QUESTION: 'ASSIGN_QUESTION',
    NAVIGATE_TO_QUESTION: 'NAVIGATE_TO_QUESTION',
    QUESTION_SCRAPED: 'QUESTION_SCRAPED',
    RELAY_PROMPT_TO_AI: 'RELAY_PROMPT_TO_AI',
    AI_CODE_RESPONSE: 'AI_CODE_RESPONSE',
    AI_QUOTA_EXCEEDED: 'AI_QUOTA_EXCEEDED',
    INJECT_AND_EVALUATE: 'INJECT_AND_EVALUATE',
    EVALUATION_RESULT: 'EVALUATION_RESULT',
    MARK_UNSOLVABLE: 'MARK_UNSOLVABLE',
    DEBUG_STEP_ACTION: 'DEBUG_STEP_ACTION',
    LOG_EVENT: 'LOG_EVENT',
    STATE_UPDATED: 'STATE_UPDATED'
  });

  /* ------------------------------------------------------------------ */
  /* Courses & sunburst topic definitions                               */
  /* ------------------------------------------------------------------ */
  const COURSES = Object.freeze({
    'C PROGRAMMING': Object.freeze({
      code: 'c',
      topics: Object.freeze([
        'INPUT & OUTPUT',
        'FLOW CONTROL & ...',
        'ARRAYS & LOOPS',
        'STRINGS',
        'FUNCTIONS',
        'STRUCTURES AND ...',
        'POINTERS',
        'STRUCTURE POINT..',
        'ADVANCED PACKAG..',
        'ADVANCED CONCEP..'
      ])
    }),
    'DATA STRUCTURE': Object.freeze({
      code: 'c',
      topics: Object.freeze([
        'SEARCHING',
        'SORTING',
        'ARRAYS',
        'LINKED LIST',
        'STACK',
        'QUEUE',
        'TREE 1',
        'TREE 2',
        'GRAPH',
        'HASHING'
      ])
    })
  });

  /* ------------------------------------------------------------------ */
  /* Sunburst slice colour matchers (computed style / attribute values) */
  /* ------------------------------------------------------------------ */
  const SLICE_COLORS = Object.freeze({
    SOLVED_GREEN: Object.freeze([
      'rgb(52, 168, 83)', 'rgb(40, 167, 69)', 'rgb(76, 175, 80)',
      'green', '#34a853', '#28a745'
    ]),
    ATTEMPTED_YELLOW: Object.freeze([
      'rgb(251, 188, 4)', 'rgb(255, 193, 7)', 'yellow', '#fbbc04'
    ]),
    UNSOLVED_RED: Object.freeze([
      'rgb(234, 67, 53)', 'rgb(220, 53, 69)', 'red', '#ea4335', '#ff0000'
    ])
  });

  /* ------------------------------------------------------------------ */
  /* AI providers (supports both UPPERCASE and lowercase key lookup)    */
  /* ------------------------------------------------------------------ */
  const GEMINI_PROVIDER = Object.freeze({
    id: 'gemini',
    name: 'Google Gemini',
    url: 'https://gemini.google.com/app',
    matchPattern: '*://gemini.google.com/*'
  });
  const CHATGPT_PROVIDER = Object.freeze({
    id: 'chatgpt',
    name: 'OpenAI ChatGPT',
    url: 'https://chatgpt.com/',
    matchPattern: '*://chatgpt.com/*'
  });
  const CLAUDE_PROVIDER = Object.freeze({
    id: 'claude',
    name: 'Anthropic Claude',
    url: 'https://claude.ai/new',
    matchPattern: '*://claude.ai/*'
  });

  const AI_PROVIDERS = Object.freeze({
    GEMINI: GEMINI_PROVIDER,
    CHATGPT: CHATGPT_PROVIDER,
    CLAUDE: CLAUDE_PROVIDER,
    gemini: GEMINI_PROVIDER,
    chatgpt: CHATGPT_PROVIDER,
    claude: CLAUDE_PROVIDER
  });

  /* ------------------------------------------------------------------ */
  /* Limits                                                             */
  /* ------------------------------------------------------------------ */
  const LIMITS = Object.freeze({
    MAX_SWARM_TABS: 5,
    MIN_SWARM_TABS: 1,
    MAX_DEBUG_ATTEMPTS: 5,
    EVAL_TIMEOUT_MS: 45000,
    AI_RESPONSE_TIMEOUT_MS: 90000
  });

  /* ------------------------------------------------------------------ */
  /* Prompt template helpers                                            */
  /* ------------------------------------------------------------------ */
  const str = (v) => (v === undefined || v === null ? '' : String(v).trim());
  const pick = (obj, keys) => {
    if (!obj) return undefined;
    for (const k of keys) {
      const val = obj[k];
      if (val === undefined || val === null) continue;
      if (Array.isArray(val)) {
        if (val.length > 0) return val;
        continue;
      }
      if (typeof val === 'object') {
        if (Object.keys(val).length > 0) return val;
        continue;
      }
      if (String(val).trim() !== '') return val;
    }
    return undefined;
  };

  const normLang = (language) => {
    const l = str(language).toLowerCase();
    return l === 'cpp' || l === 'c++' ? 'cpp' : 'c';
  };
  const langLabel = (lang) => (lang === 'cpp' ? 'C++' : 'C');

  function formatLogicalCases(cases) {
    if (!Array.isArray(cases) || cases.length === 0) return '(none provided)';
    return cases.map((tc, i) => {
      const input = pick(tc, ['input', 'in', 'stdin']);
      const output = pick(tc, ['expectedOutput', 'expected_output', 'output', 'out', 'expected']);
      return [
        `Test Case ${i + 1}:`,
        `INPUT (STDIN):`,
        str(input) || '(empty)',
        `EXPECTED OUTPUT:`,
        str(output) || '(empty)'
      ].join('\n');
    }).join('\n\n');
  }

  function formatMandatoryCases(cases) {
    if (!Array.isArray(cases) || cases.length === 0) return '(none provided)';
    return cases.map((tc, i) => {
      const kw = typeof tc === 'string' ? tc : pick(tc, ['keyword', 'text', 'value', 'pattern']);
      return `Test Case ${i + 1} KEYWORD:\n${str(kw)}`;
    }).join('\n');
  }

  function formatComplexityTargets(c) {
    if (!c) return '(none provided)';
    if (Array.isArray(c)) {
      return c.map((t, i) => `Complexity Test Case ${i + 1}: ${formatComplexityLine(t)}`).join('\n');
    }
    return formatComplexityLine(c);
  }

  function formatComplexityLine(c) {
    const cc = pick(c, ['cyclomaticComplexity', 'cyclomatic', 'cc', 'CYCLOMATIC COMPLEXITY']);
    const tk = pick(c, ['tokenCount', 'tokens', 'token', 'TOKEN COUNT']);
    const nl = pick(c, ['nloc', 'NLOC']);
    return `Cyclomatic Complexity: ${str(cc) || 'N/A'}, Token Count: ${str(tk) || 'N/A'}, NLOC: ${str(nl) || 'N/A'}`;
  }

  function formatMeasured(m) {
    if (!m) return '(not reported)';
    return formatComplexityLine(m);
  }

  function buildInitialPrompt(questionData, language) {
    const lang = normLang(language);
    const q = questionData || {};
    const title = str(pick(q, ['questionInfo', 'title', 'name', 'questionTitle']));
    const description = str(pick(q, ['problemDescription', 'description', 'problem']));
    const constraints = str(pick(q, ['constraints']));
    const inputFormat = str(pick(q, ['inputFormat', 'input_format']));
    const outputFormat = str(pick(q, ['outputFormat', 'output_format']));
    const logical = pick(q, ['logicalTestCases', 'logicalTests', 'testCases']);
    const mandatory = pick(q, ['mandatoryKeywords', 'mandatoryTestCases', 'mandatoryTests', 'keywords']);
    const complexity = pick(q, ['complexityTargets', 'complexityTestCases', 'complexity']);

    const parts = [
      `Write a complete, compilable ${langLabel(lang)} program that solves the following SRM eLab programming problem.`,
      title ? `Challenge: ${title}` : '',
      `Problem Description:\n${description || '(not provided)'}`
    ];

    if (constraints && !description.includes(constraints)) {
      parts.push(`Constraints:\n${constraints}`);
    }
    if (inputFormat && !description.includes(inputFormat)) {
      parts.push(`Input Format:\n${inputFormat}`);
    }
    if (outputFormat && !description.includes(outputFormat)) {
      parts.push(`Output Format:\n${outputFormat}`);
    }

    parts.push(
      `Logical Test Cases (Input & Expected Output):\n${formatLogicalCases(logical)}`,
      `Mandatory Test Cases:\n` +
        `CRITICAL: Include every Mandatory Test Case KEYWORD string character-for-character in your source code with exact spacing (do NOT add or remove spaces around commas, parentheses, or operators):\n` +
        formatMandatoryCases(mandatory),
      `Complexity Test Cases:\n` +
        `CRITICAL: Cyclomatic Complexity, Token Count, and NLOC must each be LESS THAN OR EQUAL TO these maximum targets:\n` +
        formatComplexityTargets(complexity),
      `Output ONLY the complete code in a single ${langLabel(lang)} code block.`,
      `need answer in ${lang}`
    );

    return parts.filter(Boolean).join('\n\n');
  }

  function buildDebugPrompt(questionData, evalResult, attemptNumber, language) {
    const lang = normLang(language);
    const q = questionData || {};
    const r = evalResult || {};
    const complexity = pick(q, ['complexityTargets', 'complexityTestCases', 'complexity']);
    const mandatory = pick(q, ['mandatoryKeywords', 'mandatoryTestCases', 'mandatoryTests', 'keywords']);
    const attempt = Number(attemptNumber) || 1;

    const parts = [
      `Debug attempt ${attempt} of ${LIMITS.MAX_DEBUG_ATTEMPTS}. Your previous ${langLabel(lang)} solution did not achieve 100% on SRM eLab.`
    ];

    const compilerError = str(r.compilerError);
    if (compilerError) {
      parts.push(`Compilation error :(\n${compilerError}`);
    } else if (r.percentage !== undefined && r.percentage !== null && str(r.percentage) !== '') {
      const pct = String(r.percentage).replace(/%$/, '');
      parts.push(`Something Wrong :(\nScore achieved: ${pct}% (Requires 100%)`);
    } else {
      parts.push('Something Wrong :(');
    }

    const badges = Array.isArray(r.failedBadges) ? r.failedBadges.filter(Boolean) : [];
    parts.push(
      `Failed Test Case Badges:\n` +
      (badges.length ? badges.map((b) => `- ${str(b)}`).join('\n') : '(none reported)')
    );

    if (str(r.outputText) && !compilerError) {
      parts.push(`Program Output Panel:\n${str(r.outputText)}`);
    }

    parts.push(
      `Complexity Analysis:\n` +
      `- Actual Measured on eLab: ${formatMeasured(r.measuredComplexity)}\n` +
      `- Required Maximum Targets (must be <=): ${formatComplexityTargets(complexity)}`
    );

    if (Array.isArray(mandatory) && mandatory.length) {
      parts.push(
        `Mandatory Test Cases:\n` +
        `CRITICAL: Every Mandatory KEYWORD string below MUST appear verbatim as an exact substring in your code (watch exact spaces around commas and operators):\n` +
        formatMandatoryCases(mandatory)
      );
    }

    parts.push(
      `Fix all failed checks above while keeping all passing checks intact. Output ONLY the complete corrected ${langLabel(lang)} code in a single code block, with no explanation.`,
      `need answer in ${lang}`
    );

    return parts.join('\n\n');
  }

  const PROMPT_TEMPLATES = Object.freeze({ buildInitialPrompt, buildDebugPrompt });

  /* ------------------------------------------------------------------ */
  /* Export                                                             */
  /* ------------------------------------------------------------------ */
  root.ELAB_CONTRACTS = Object.freeze({
    MSG,
    COURSES,
    SLICE_COLORS,
    AI_PROVIDERS,
    LIMITS,
    PROMPT_TEMPLATES
  });
})(typeof globalThis !== 'undefined' ? globalThis : (typeof self !== 'undefined' ? self : window));

contracts
You said [MODE B BRANCH VERIFICATION] Attached is `contracts.js` harvested live from child node `Harivishnu93…

[MODE B BRANCH VERIFICATION] Attached is `contracts.js` harvested live from child node `Harivishnu9345`.

Please audit this file for interface compliance, imports, and edge-case bugs without rewriting unchanged boilerplate. If fixes are needed, output the corrected `===FILE: contracts.js===` block.

Gemini said

An audit of contracts.js (contracts_2.js) identifies three interface adjustments required for full cross-module compatibility:

mandatoryKeywords Key Lookup: elab_scraper_eval.js outputs questionData.mandatoryKeywords, whereas buildInitialPrompt and buildDebugPrompt only checked ['mandatoryTestCases', 'mandatoryTests']. Adding 'mandatoryKeywords' and 'keywords' prevents Mandatory Test Case strings from being dropped.   
contracts.js
+ 1

Case-Insensitive AI_PROVIDERS Access: swarmConfig.aiProvider stores lowercase provider IDs ('gemini', 'chatgpt', 'claude'), while AI_PROVIDERS only defined uppercase keys (GEMINI, CHATGPT, CLAUDE). Adding lowercase key aliases allows direct lookup via AI_PROVIDERS[config.aiProvider].   
contracts.js

Embedded Section Deduplication: buildInitialPrompt and buildDebugPrompt now avoid printing (not provided) when Constraints, Input Format, or Output Format are already part of problemDescription, and include evalResult.outputText when logical test cases fail.   
contracts.js
