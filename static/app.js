// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
'use strict';

const el = (id) => document.getElementById(id);
const logs = { red: el('red-log'), blue: el('blue-log'), system: el('sys-log') };
const STAGES = ['sandbox', 'baseline', 'analysis', 'probe', 'patch', 'regression', 'cleanup'];
const RESULT_LABELS = {
  verified: 'Boundary check passed',
  not_confirmed: 'Boundary not confirmed',
  rejected: 'Candidate patch rejected',
  failed: 'Boundary still reachable',
  no_findings: 'No findings',
  partial: 'Verification partially completed',
  completed: 'Project verification completed',
  error: 'Scan could not complete'
};
const MAX_ENTRIES = 300;
const SCAN_PROFILE_CYCLES = {
  extra_light: 1,
  light: 3,
  medium: 5,
  heavy: 8,
  super_heavy: 12,
  ultra_heavy: 12
};

let targets = {};
let socket = null;
let latestResult = null;
let configured = false;
const RED_NAMES = ['Breakwater', 'Lockpick', 'Bloodhound', 'Sparkler', 'Cartographer', 'Breakwater', 'Lockpick', 'Bloodhound', 'Sparkler', 'Cartographer', 'Breakwater', 'Lockpick'];
const BLUE_NAMES = ['Bastion', 'Stitch', 'Librarian', 'Sentinel', 'Proofreader', 'Bastion', 'Stitch', 'Librarian', 'Sentinel', 'Proofreader', 'Bastion', 'Stitch'];
let startedAt = 0;
let timer = null;
let eventCount = 0;
let currentStage = -1;
let activeFilter = 'all';
let popCount = 0;
let profiles = [];
let selectedProfile = 'custom';
let sourceMode = 'demo';
let inferenceMode = 'hosted';

/* ---------- small helpers ---------- */

function status(text, state = 'idle') {
  el('status').textContent = text;
  el('status').dataset.state = state;
}

function chip(id, state, label) {
  const node = el(id);
  node.dataset.state = state;
  if (label) node.lastChild.textContent = label;
}

let toastTimer = null;
function toast(text) {
  const node = el('toast');
  node.textContent = text;
  node.hidden = false;
  node.classList.remove('show');
  void node.offsetWidth;
  node.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, 2200);
}

async function copyText(text, label) {
  if (!text) { toast('Nothing to copy yet'); return; }
  try {
    await navigator.clipboard.writeText(text);
    toast(`${label} copied`);
  } catch {
    toast('Clipboard unavailable in this browser context');
  }
}

function formatElapsed(ms) {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes}m ${String(seconds % 60).padStart(2, '0')}s` : `${seconds}s`;
}

/* ---------- logs ---------- */

function clearEmpty(area) {
  const empty = area.querySelector('.empty');
  if (empty) empty.remove();
}

function buildEntry(team, text, withTag) {
  const line = document.createElement('div');
  line.className = 'entry';
  line.dataset.team = team;
  const stamp = document.createElement('time');
  stamp.textContent = new Date().toLocaleTimeString([], { hour12: false });
  line.append(stamp);
  if (withTag) {
    const tag = document.createElement('span');
    tag.className = `tag tag-${team}`;
    tag.textContent = team;
    line.append(tag);
  }
  const body = document.createElement('span');
  body.className = 'msg';
  body.textContent = String(text);
  line.append(body);
  if (activeFilter !== 'all' && withTag && team !== activeFilter) line.hidden = true;
  return line;
}

function append(area, line) {
  clearEmpty(area);
  const pinned = area.scrollHeight - area.scrollTop - area.clientHeight < 40;
  area.append(line);
  while (area.children.length > MAX_ENTRIES) area.firstChild.remove();
  if (pinned) area.scrollTop = area.scrollHeight;
}

function spawnTerminalPop(team, text) {
  try {
    if (document.querySelectorAll('.terminal-pop').length >= 3) document.querySelector('.terminal-pop').remove();
    const pop = document.createElement('div');
    pop.className = 'terminal-pop';
    const titles = { red: 'red-team · boundary probe', blue: 'blue-team · sanitizer', system: 'orchestrator · sandbox' };
    pop.style.right = `${18 + (popCount % 3) * 316}px`;
    pop.style.bottom = '86px';
    popCount += 1;
    const head = document.createElement('header');
    ['r','y','g'].forEach(() => head.append(document.createElement('i')));
    const label = document.createElement('span');
    label.textContent = titles[team] || titles.system;
    label.style.marginLeft = '6px';
    head.append(label);
    const bar = document.createElement('div');
    bar.className = 'bar';
    const pre = document.createElement('pre');
    pre.textContent = String(text).slice(0, 280);
    pop.append(head, pre, bar);
    document.body.append(pop);
    setTimeout(() => pop.remove(), 4200);
  } catch { /* decorative only */ }
}

const CHATTER_RE = /(Breakwater|Lockpick|Bloodhound|Sparkler|Cartographer|Bastion|Stitch|Librarian|Sentinel|Proofreader|Warlord|Warden|Greenhouse)/;
function buildRoster(node, names, leader) {
  node.replaceChildren();
  const lead = document.createElement('span');
  lead.className = 'agent-chip leader';
  lead.textContent = '';
  const dot = document.createElement('i');
  const label = document.createElement('span');
  label.textContent = leader;
  lead.append(dot, label);
  node.append(lead);
  names.forEach((name) => {
    const chip = document.createElement('span');
    chip.className = 'agent-chip';
    chip.dataset.name = name;
    const d = document.createElement('i');
    const l = document.createElement('span');
    l.textContent = name;
    chip.append(d, l);
    node.append(chip);
  });
}
function lightAgent(name) {
  document.querySelectorAll('.agent-chip').forEach((chip) => chip.classList.remove('speaking'));
  const chip = document.querySelector(`.agent-chip[data-name="${name}"]`);
  if (chip) chip.classList.add('speaking');
  const comms = el('comms-log');
  if (comms) {
    const empty = comms.querySelector('.empty');
    if (empty) empty.remove();
  }
}
function writeComms(team, text) {
  const comms = el('comms-log');
  if (!comms) return;
  const m = CHATTER_RE.exec(String(text));
  if (!m) return;
  lightAgent(m[1]);
  const line = buildEntry(team === 'green' ? 'system' : team, text, true);
  append(comms, line);
}
function writeLine(team, text) {
  const known = team === 'red' || team === 'blue' ? team : 'system';
  if (known !== 'system') {
    append(logs[known], buildEntry(known, text, false));
    document.querySelectorAll('.panel').forEach((panel) => panel.classList.toggle('active', panel.dataset.team === known));
  }
  // The activity timeline records every event so it can be filtered.
  append(logs.system, buildEntry(known, text, true));
  writeComms(known, text);
  if (team !== 'system' || /Cycle|probe|patch|regression|cleanup|Docker|Muse/i.test(String(text))) spawnTerminalPop(team, text);
  eventCount += 1;
  el('event-count').textContent = String(eventCount);
  advanceStage(known, String(text));
}

function logText(team) {
  return [...logs[team].querySelectorAll('.entry')]
    .filter((entry) => !entry.hidden)
    .map((entry) => entry.innerText.replace(/\n/g, ' '))
    .join('\n');
}

/* ---------- pipeline ---------- */

function setStage(name, state = 'active') {
  const index = STAGES.indexOf(name);
  if (index < 0) return;
  if (state === 'active' && index < currentStage) return;
  document.querySelectorAll('#pipeline li').forEach((item, i) => {
    if (state === 'active') {
      if (i < index) item.dataset.state = item.dataset.state === 'skipped' ? 'skipped' : 'done';
      if (i === index) item.dataset.state = 'active';
    }
  });
  if (state !== 'active') document.querySelector(`#pipeline li[data-stage="${name}"]`).dataset.state = state;
  currentStage = Math.max(currentStage, index);
  const fraction = (index + (state === 'active' ? 0.5 : 1)) / STAGES.length;
  el('progress').style.setProperty('--value', String(Math.min(1, fraction)));
}

function advanceStage(team, text) {
  const t = text.toLowerCase();
  if (t.includes('original-project baseline checks')) { setStage('sandbox'); setStage('baseline'); }
  else if (team === 'red' && t.includes('reviewing the cumulative verified snapshot')) { resetPipeline(); setStage('analysis'); }
  else if (team === 'red' && t.includes('proving the finding')) setStage('probe');
  else if (team === 'blue' && t.includes('bounded sanitation-only replacements')) setStage('patch');
  else if (t.includes('verifying a fresh target with the original probe')) setStage('regression');
  else if (t.includes('removing project session containers')) setStage('cleanup');
  else if (t.includes('creating an internal docker network')) setStage('sandbox');
  else if (t.includes('normal-input checks passed') && currentStage < 2) setStage('baseline');
  else if (team === 'red' && t.startsWith('analyzing')) setStage('analysis');
  else if (team === 'red' && t.includes('boundary check exited')) setStage('probe');
  else if (team === 'blue' && t.startsWith('requesting a sanitization patch')) setStage('patch');
  else if (t.includes('starting a fresh target from the patched snapshot')) setStage('regression');
  else if (t.includes('session containers, snapshots, and network removed')) setStage('cleanup');
}

function resetPipeline() {
  currentStage = -1;
  document.querySelectorAll('#pipeline li').forEach((item) => { delete item.dataset.state; });
  el('progress').style.setProperty('--value', '0');
}

function finishPipeline(result) {
  const items = [...document.querySelectorAll('#pipeline li')];
  const ok = ['verified', 'not_confirmed', 'no_findings', 'completed'].includes(result.status);
  items.forEach((item, i) => {
    if (item.dataset.state === 'active') item.dataset.state = ok ? 'done' : 'failed';
    else if (!item.dataset.state && i < STAGES.length - 1) item.dataset.state = 'skipped';
  });
  const cleanup = items[items.length - 1];
  cleanup.dataset.state = result.cleanup_ok ? 'done' : 'failed';
  el('progress').style.setProperty('--value', '1');
  el('progress').dataset.state = result.status;
}

/* ---------- targets ---------- */

function selectTarget(key, focus = false) {
  if (!targets[key] || socket) return;
  el('target-select').value = key;
  document.querySelectorAll('.target[data-key]').forEach((card) => {
    const selected = card.dataset.key === key;
    card.setAttribute('aria-checked', String(selected));
    card.tabIndex = selected ? 0 : -1;
    if (selected && focus) card.focus();
  });
  el('target-description').textContent = `Selected ${targets[key].title} · ${targets[key].filename}. The original fixture is never modified.`;
}

const TARGET_ICONS = { node_query_sink: 'JS', php_command_sink: 'PHP', mysql_insecure_conf: 'SQL' };

function renderTargets() {
  const list = el('target-list');
  list.replaceChildren();
  el('target-select').replaceChildren();
  Object.entries(targets).forEach(([key, target], index) => {
    const option = document.createElement('option');
    option.value = key;
    option.textContent = target.title;
    el('target-select').append(option);

    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'target';
    card.dataset.key = key;
    card.setAttribute('role', 'radio');
    card.setAttribute('aria-checked', 'false');
    const badge = document.createElement('span');
    badge.className = 'badge';
    badge.textContent = TARGET_ICONS[key] || String(index + 1);
    const title = document.createElement('strong');
    title.textContent = target.title;
    const file = document.createElement('code');
    file.textContent = target.filename;
    const desc = document.createElement('small');
    desc.textContent = target.description;
    const key_hint = document.createElement('kbd');
    key_hint.textContent = String(index + 1);
    card.append(badge, key_hint, title, file, desc);
    card.addEventListener('click', () => selectTarget(key));
    card.addEventListener('pointermove', (event) => {
      const box = card.getBoundingClientRect();
      card.style.setProperty('--mx', `${event.clientX - box.left}px`);
      card.style.setProperty('--my', `${event.clientY - box.top}px`);
    });
    list.append(card);
  });
  list.addEventListener('keydown', (event) => {
    const keys = Object.keys(targets);
    const index = keys.indexOf(el('target-select').value);
    const move = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (move === undefined) return;
    event.preventDefault();
    selectTarget(keys[(index + move + keys.length) % keys.length], true);
  });
  const first = Object.keys(targets)[0];
  if (first) selectTarget(first);
}

function lockTargets(locked) {
  document.querySelectorAll('.target[data-key]').forEach((card) => { card.disabled = locked; });
  el('target-list').classList.toggle('locked', locked);
}

function setSourceMode(mode) {
  if (socket || !['demo', 'project'].includes(mode)) return;
  sourceMode = mode;
  document.querySelectorAll('.mode').forEach((button) => {
    const active = button.dataset.mode === mode;
    button.classList.toggle('active', active);
    button.setAttribute('aria-checked', String(active));
  });
  el('demo-config').hidden = mode !== 'demo';
  el('project-form').hidden = mode !== 'project';
  el('run-label').textContent = mode === 'project' ? 'Run project verification' : 'Run demo verification';
  el('target-description').textContent = mode === 'project'
    ? 'The repository is copied into an isolated sandbox. Source may be sent to the configured Muse endpoint only after consent.'
    : (targets[el('target-select').value] ? `Selected ${targets[el('target-select').value].title} · ${targets[el('target-select').value].filename}. The original fixture is never modified.` : 'Choose a bundled fixture.');
  el('project-errors').hidden = true;
}

function parseArgv(id, label, errors) {
  const node = el(id);
  node.removeAttribute('aria-invalid');
  try {
    const value = JSON.parse(node.value);
    if (!Array.isArray(value) || !value.length || value.some((part) => typeof part !== 'string' || !part.length)) throw new Error();
    return value;
  } catch {
    node.setAttribute('aria-invalid', 'true');
    errors.push(`${label} must be a non-empty JSON array of strings.`);
    return null;
  }
}

function updateScanProfile() {
  const key = el('project-scan-profile').value;
  const cycles = SCAN_PROFILE_CYCLES[key];
  const custom = key === 'custom';
  const ultra = key === 'ultra_heavy';
  el('project-cycles').readOnly = !custom;
  el('project-red-agents').disabled = !ultra;
  el('project-blue-agents').disabled = !ultra;
  if (!custom) el('project-cycles').value = String(cycles);
  const cycleLabel = cycles === 1 ? '1 cycle' : `${cycles} cycles`;
  el('project-scan-description').textContent = custom
    ? 'Legacy compatibility mode · choose 1 to 20 single-pass cycles.'
    : `${cycleLabel} · each cycle runs Red, Blue, Red, Blue with cumulative focus${key === 'ultra_heavy' ? ' and bounded automatic discovery from the first pass' : ''}.`;
}

function projectSpec() {
  const errors = [];
  el('project-form').querySelectorAll('input, textarea, select').forEach((node) => node.removeAttribute('aria-invalid'));
  const path = el('project-path').value.trim();
  const image = el('project-image').value.trim();
  const contract = el('project-contract').value.trim();
  const scanProfile = el('project-scan-profile').value;
  const cycles = Number(el('project-cycles').value);
  const redAgents = Number(el('project-red-agents').value);
  const blueAgents = Number(el('project-blue-agents').value);
  const contextBudget = Number(el('project-budget').value);
  if (!path.startsWith('/')) { el('project-path').setAttribute('aria-invalid', 'true'); errors.push('Repository path must be absolute and start with /.'); }
  if (!image) { el('project-image').setAttribute('aria-invalid', 'true'); errors.push('Preloaded sandbox image is required.'); }
  if (!contract) { el('project-contract').setAttribute('aria-invalid', 'true'); errors.push('Behavior contract is required.'); }
  if (scanProfile !== 'custom' && !Object.hasOwn(SCAN_PROFILE_CYCLES, scanProfile)) { el('project-scan-profile').setAttribute('aria-invalid', 'true'); errors.push('Choose a valid scan intensity.'); }
  if (!Number.isInteger(cycles) || cycles < 1 || cycles > 20) { el('project-cycles').setAttribute('aria-invalid', 'true'); errors.push('Cycles must be a whole number from 1 to 20.'); }
  if (!Number.isInteger(redAgents) || redAgents < 1 || redAgents > 12) { el('project-red-agents').setAttribute('aria-invalid', 'true'); errors.push('Red agents must be a whole number from 1 to 12.'); }
  if (!Number.isInteger(blueAgents) || blueAgents < 1 || blueAgents > 12) { el('project-blue-agents').setAttribute('aria-invalid', 'true'); errors.push('Blue agents must be a whole number from 1 to 12.'); }
  if (!Number.isInteger(contextBudget) || contextBudget < 1024 || contextBudget > 131072) { el('project-budget').setAttribute('aria-invalid', 'true'); errors.push('Context budget must be a whole number from 1024 to 131072.'); }
  if (inferenceMode !== 'local' && !el('allow-remote').checked) errors.push('Confirm that source may be sent to the configured Muse endpoint.');
  const command = parseArgv('project-command', 'Start command', errors);
  const testCommand = parseArgv('project-test-command', 'Regression test command', errors);
  el('project-errors').hidden = errors.length === 0;
  el('project-errors').textContent = errors.join(' ');
  if (errors.length) return null;
  return { path, image, command, test_command: testCommand, contract, scan_profile: scanProfile, cycles, red_agents: redAgents, blue_agents: blueAgents, context_budget: contextBudget, allow_remote_inference: inferenceMode !== 'local' && el('allow-remote').checked };
}

function lockProjectForm(locked) {
  el('project-form').querySelectorAll('input, textarea, select').forEach((node) => { node.disabled = locked; });
  document.querySelectorAll('.mode').forEach((node) => { node.disabled = locked; });
  if (!locked) updateScanProfile();
}

/* ---------- model profiles ---------- */

function selectProfile(key) {
  if (socket || !profiles.some((p) => p.key === key)) return;
  selectedProfile = key;
  document.querySelectorAll('.profile').forEach((button) => {
    const on = button.dataset.key === key;
    button.setAttribute('aria-checked', String(on));
    button.tabIndex = on ? 0 : -1;
  });
  const chosen = profiles.find((p) => p.key === key);
  el('red-model').textContent = chosen.red_model;
  el('blue-model').textContent = chosen.blue_model;
}

function renderProfiles(health) {
  profiles = health.profiles || [];
  el('profile-row').hidden = profiles.length === 0;
  const list = el('profile-list');
  list.replaceChildren();
  profiles.forEach((profile) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'profile';
    button.dataset.key = profile.key;
    button.setAttribute('role', 'radio');
    button.title = `Red: ${profile.red_model} · Blue: ${profile.blue_model}`;
    const name = document.createElement('strong');
    name.textContent = profile.label;
    const desc = document.createElement('small');
    desc.textContent = profile.description;
    button.append(name, desc);
    button.addEventListener('click', () => selectProfile(profile.key));
    list.append(button);
  });
  if (profiles.length) selectProfile(profiles.some((p) => p.key === health.default_profile) ? health.default_profile : profiles[0].key);
}

function lockProfiles(locked) {
  document.querySelectorAll('.profile').forEach((button) => { button.disabled = locked; });
}

/* ---------- result ---------- */

function renderDiff(diff) {
  const pre = el('diff');
  pre.replaceChildren();
  let added = 0;
  let removed = 0;
  diff.split('\n').forEach((text) => {
    const line = document.createElement('span');
    if (text.startsWith('+') && !text.startsWith('+++')) { line.className = 'add'; added += 1; }
    else if (text.startsWith('-') && !text.startsWith('---')) { line.className = 'del'; removed += 1; }
    else if (text.startsWith('@@')) line.className = 'hunk';
    else if (text.startsWith('+++') || text.startsWith('---')) line.className = 'file';
    line.textContent = `${text}\n`;
    pre.append(line);
  });
  el('diff-stats').textContent = `+${added} −${removed}`;
}

function fact(id, value, good) {
  const node = el(id);
  node.textContent = value;
  node.dataset.state = good === undefined ? 'neutral' : good ? 'good' : 'bad';
}

function probeLabel(code) {
  if (code === null || code === undefined) return ['Not run', undefined];
  if (code === 0) return ['Exit 0 · reachable', false];
  if (code === 1) return ['Exit 1 · blocked', true];
  return [`Exit ${code} · inconclusive`, false];
}

function formatCost(value) {
  if (value === null || value === undefined) return 'Unknown';
  if (value < 0.01) return `$${value.toFixed(4)}`;
  return `$${value.toFixed(3)}`;
}

function renderUsage(payload) {
  const calls = (payload.usage && payload.usage.calls) || [];
  el('usage').hidden = calls.length === 0;
  if (!calls.length) return;
  el('usage-cost').textContent = formatCost(payload.cost_usd);
  el('usage-tokens').textContent = `${(payload.total_tokens || 0).toLocaleString()} tokens · ${calls.length} model call${calls.length === 1 ? '' : 's'}`;
  const list = el('usage-calls');
  list.replaceChildren();
  calls.forEach((call) => {
    const item = document.createElement('li');
    const blue = call.role === 'blue' || (call.role || '').startsWith('project_blue_');
    item.dataset.team = blue ? 'blue' : 'red';
    const who = document.createElement('strong');
    who.textContent = blue ? 'Blue' : 'Red';
    const model = document.createElement('code');
    model.textContent = call.model;
    const detail = document.createElement('span');
    detail.textContent = `${call.prompt_tokens.toLocaleString()} in · ${call.completion_tokens.toLocaleString()} out (${call.reasoning_tokens.toLocaleString()} thinking) · ${call.seconds.toFixed(1)}s`;
    const cost = document.createElement('em');
    cost.textContent = formatCost(call.cost_usd);
    item.append(who, model, detail, cost);
    list.append(item);
  });
}

function redactEvidence(value) {
  if (Array.isArray(value)) return value.map(redactEvidence);
  if (value && typeof value === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      if (k === 'verification_script_python') out[k] = '[exploit details withheld]';
      else if (k === 'output' && typeof v === 'string' && v.length > 500) out[k] = v.slice(0, 500) + '\n[probe output truncated]';
      else out[k] = redactEvidence(v);
    }
    return out;
  }
  return value;
}

function renderCycles(cycles) {
  const list = el('cycle-list');
  list.replaceChildren();
  el('cycle-reports').hidden = !Array.isArray(cycles) || cycles.length === 0;
  if (!Array.isArray(cycles)) return;
  cycles.forEach((cycle, index) => {
    const details = document.createElement('details');
    details.className = 'cycle-report';
    if (index === cycles.length - 1) details.open = true;
    const summary = document.createElement('summary');
    summary.textContent = `Cycle ${cycle.cycle || index + 1}${cycle.pass_number ? ` · pass ${cycle.pass_number}` : ''}${cycle.status ? ` · ${cycle.status}` : ''}`;
    const body = document.createElement('div');
    body.className = 'cycle-body';
    [['Report', cycle.report || cycle.message], ['Evidence', cycle.evidence], ['Diff', cycle.diff]].forEach(([heading, value]) => {
      if (value === null || value === undefined || value === '') return;
      const section = document.createElement('section');
      const title = document.createElement('strong');
      title.textContent = heading;
      const content = document.createElement(Array.isArray(value) || typeof value === 'object' ? 'pre' : 'p');
      content.textContent = typeof value === 'string' ? value : JSON.stringify(redactEvidence(value), null, 2);
      section.append(title, content);
      body.append(section);
    });
    details.append(summary, body);
    list.append(details);
  });
}

function summaryEvidence(payload) {
  if (!Array.isArray(payload.cycle_reports)) return payload;
  const cycles = payload.cycle_reports;
  const before = cycles.map((cycle) => cycle.evidence && cycle.evidence.pre_verification).filter(Boolean);
  const after = cycles.map((cycle) => cycle.evidence && cycle.evidence.patched_verification).filter(Boolean);
  const baseline = payload.baseline_verification;
  return {
    ...payload,
    baseline_passed: baseline ? baseline.fresh_target && baseline.regression.exit_code === 0 : undefined,
    pre_exit_code: before.length === 1 ? before[0].probe.exit_code : undefined,
    post_exit_code: after.length === 1 ? after[0].probe.exit_code : undefined,
    regression_passed: after.length ? after.every((check) => check.fresh_target && check.regression.exit_code === 0) : undefined,
    pre_summary: before.length > 1 ? `${before.filter((check) => check.probe.exit_code === 0).length}/${before.length} reachable` : undefined,
    post_summary: after.length > 1 ? `${after.filter((check) => check.probe.exit_code === 1).length}/${after.length} blocked` : undefined,
    pre_good: before.every((check) => check.probe.exit_code === 0),
    post_good: after.every((check) => check.probe.exit_code === 1)
  };
}

function showResult(payload) {
  latestResult = payload;
  const evidence = summaryEvidence(payload);
  const diff = payload.diff || payload.cumulative_diff || '';
  const cycles = payload.cycles || payload.cycle_reports || [];
  const cleanupOk = payload.cleanup_ok !== undefined ? payload.cleanup_ok : !payload.cleanup || payload.cleanup.succeeded;
  const displayPayload = { ...payload, cost_usd: payload.cost_usd ?? payload.total_cost_usd };
  const label = RESULT_LABELS[payload.status] || 'Scan finished';
  el('result-panel').dataset.status = payload.status;
  el('result-title').textContent = label;
  el('result-message').textContent = payload.message;
  fact('fact-baseline', evidence.baseline_passed === undefined ? 'Not reported' : evidence.baseline_passed ? 'Passed' : 'Not passed', evidence.baseline_passed);
  const pre = evidence.pre_summary ? [evidence.pre_summary, evidence.pre_good ? undefined : false] : probeLabel(evidence.pre_exit_code);
  fact('fact-pre', pre[0], evidence.pre_exit_code === 0 ? undefined : pre[1]);
  fact('fact-regression', evidence.regression_passed === undefined ? 'Not reported' : evidence.regression_passed ? 'Passed' : 'Not passed', evidence.regression_passed);
  fact('fact-post', ...(evidence.post_summary ? [evidence.post_summary, evidence.post_good] : probeLabel(evidence.post_exit_code)));
  fact('fact-cleanup', cleanupOk ? 'Resources removed' : 'Inspect Docker', cleanupOk);
  renderUsage(displayPayload);
  renderCycles(cycles);
  if (diff) {
    renderDiff(diff);
    el('diff-wrap').hidden = false;
  } else {
    el('diff-wrap').hidden = true;
  }
  el('download-patch-btn').hidden = !diff;
  el('result-panel').hidden = false;
  el('result-panel').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'nearest' });
  status(label, payload.status);
  finishPipeline({ ...payload, cleanup_ok: cleanupOk });
}

/* ---------- lifecycle ---------- */

async function initialize() {
  try {
    const responses = await Promise.all([fetch('/api/targets'), fetch('/api/health')]);
    if (!responses.every((response) => response.ok)) throw new Error('Configuration unavailable. Check the server terminal.');
    const [targetData, health] = await Promise.all(responses.map((response) => response.json()));
    targets = targetData;
    renderTargets();
    el('red-model').textContent = health.red_model;
    el('blue-model').textContent = health.blue_model;
    renderProfiles(health);
    inferenceMode = health.inference_mode || 'hosted';
    configured = health.inference_ready === true || (inferenceMode !== 'local' && health.api_key_configured === true);
    el('allow-remote').closest('label').hidden = inferenceMode === 'local';
    el('allow-remote').required = inferenceMode !== 'local';
    const setupNotes = [];
    chip('chip-server', 'ok');
    const dockerState = (health.docker && health.docker.state) || 'unavailable';
    const dockerReady = dockerState === 'ready';
    chip('chip-docker', dockerReady ? 'ok' : 'error', { ready: 'Docker', images_missing: 'Images missing', unavailable: 'Docker offline' }[dockerState] || 'Docker');
    chip('chip-key', configured ? 'ok' : 'warn', inferenceMode === 'local' ? 'Local inference' : (configured ? 'API key' : 'No API key'));
    if (!configured) setupNotes.push('Set META_MUSE_API_KEY in .env, export it, and restart the server.');
    if (dockerState === 'unavailable') setupNotes.push('Docker is not reachable. Start the Docker service and make sure your user can access it.');
    if (dockerState === 'images_missing') setupNotes.push('Sandbox images are missing. Run python main.py --init-images.');
    configured = configured && dockerReady;
    el('run-btn').disabled = !configured;
    status(configured ? 'Ready to verify' : 'Setup required', configured ? 'ready' : 'warn');
    if (setupNotes.length) {
      el('setup').hidden = false;
      el('setup').textContent = `${setupNotes.join(' ')} You can explore the dashboard meanwhile.`;
    }
  } catch (error) {
    chip('chip-server', 'error', 'Offline');
    status('Unable to connect', 'error');
    el('setup').hidden = false;
    el('setup').textContent = error.message;
  }
}

function startScan() {
  if (socket || !configured) return;
  const key = el('target-select').value;
  if (sourceMode === 'demo' && !targets[key]) return;
  const spec = sourceMode === 'project' ? projectSpec() : null;
  if (sourceMode === 'project' && !spec) { status('Fix project details', 'warn'); return; }
  latestResult = null;
  eventCount = 0;
  el('event-count').textContent = '0';
  el('result-panel').hidden = true;
  delete el('progress').dataset.state;
  Object.values(logs).forEach((area) => area.replaceChildren());
  resetPipeline();
  document.body.classList.add('scanning');
  el('run-btn').disabled = true;
  lockTargets(true);
  lockProfiles(true);
  lockProjectForm(true);
  try {
    buildRoster(el('red-roster'), RED_NAMES.slice(0, (spec && spec.red_agents) || 5), 'Warlord');
    buildRoster(el('blue-roster'), BLUE_NAMES.slice(0, (spec && spec.blue_agents) || 5), 'Warden');
    buildRoster(el('green-roster'), [], 'Greenhouse');
  } catch { /* decorative */ }
  el('stop-btn').hidden = false;
  el('stop-btn').disabled = false;
  status('Verification running', 'running');
  startedAt = Date.now();
  el('elapsed').textContent = '0s';
  timer = setInterval(() => { el('elapsed').textContent = formatElapsed(Date.now() - startedAt); }, 1000);
  const profileQuery = profiles.length ? `?profile=${encodeURIComponent(selectedProfile)}` : '';
  const base = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`;
  socket = new WebSocket(sourceMode === 'project' ? `${base}/ws/project${profileQuery}` : `${base}/ws/combat/${encodeURIComponent(key)}${profileQuery}`);
  if (spec) socket.onopen = () => {
    socket.send(JSON.stringify(spec));
    writeLine('system', `Project specification accepted · ${spec.scan_profile} intensity · ${spec.cycles} cycle${spec.cycles === 1 ? '' : 's'} · ${spec.red_agents} red / ${spec.blue_agents} blue agents.`);
  };
  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.type === 'result') {
        showResult(payload);
      } else {
        writeLine(payload.team, payload.msg);
        if (payload.type === 'busy') status('Another scan is running', 'error');
      }
    } catch {
      writeLine('system', 'Received an unreadable server event.');
    }
  };
  socket.onerror = () => { writeLine('system', 'Connection failed. Check the server terminal.'); };
  socket.onclose = () => {
    clearInterval(timer);
    socket = null;
    document.body.classList.remove('scanning');
    document.querySelectorAll('.panel').forEach((panel) => panel.classList.remove('active'));
    el('run-btn').disabled = !configured;
    lockTargets(false);
    lockProfiles(false);
    lockProjectForm(false);
    el('stop-btn').hidden = true;
    el('elapsed').textContent = formatElapsed(Date.now() - startedAt);
    if (!latestResult) {
      status('Session ended without a result', 'error');
      writeLine('system', 'Connection closed. The server will finish cleanup before accepting another scan.');
      document.querySelectorAll('#pipeline li[data-state="active"]').forEach((item) => { item.dataset.state = 'failed'; });
    }
  };
}

function stopScan() {
  if (!socket) return;
  el('stop-btn').disabled = true;
  status('Stopping scan', 'running');
  socket.close(1000, 'User cancelled');
}

/* ---------- wiring ---------- */

el('run-btn').addEventListener('click', startScan);
el('stop-btn').addEventListener('click', stopScan);
el('project-scan-profile').addEventListener('change', updateScanProfile);
document.querySelectorAll('.mode').forEach((button) => button.addEventListener('click', () => setSourceMode(button.dataset.mode)));

el('download-btn').addEventListener('click', () => {
  if (!latestResult) return;
  const report = {
    notice: 'Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.',
    license_url: 'https://polyformproject.org/licenses/noncommercial/1.0.0',
    ...latestResult
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `secure-mitigation-${latestResult.target || latestResult.project || 'project'}-report.json`;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast('Report downloaded');
});

el('download-patch-btn').addEventListener('click', () => {
  const diff = latestResult && (latestResult.diff || latestResult.cumulative_diff);
  if (!diff) return;
  const url = URL.createObjectURL(new Blob([diff], { type: 'text/x-diff' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'candidate.patch';
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast('Candidate patch downloaded');
});

document.querySelectorAll('[data-copy]').forEach((button) => {
  button.addEventListener('click', () => {
    const team = button.dataset.copy;
    copyText(logText(team), team === 'system' ? 'Activity' : `${team[0].toUpperCase()}${team.slice(1)} trace`);
  });
});

el('copy-diff').addEventListener('click', (event) => {
  event.preventDefault();
  copyText(latestResult && latestResult.diff, 'Diff');
});

document.querySelectorAll('.filter').forEach((button) => {
  button.addEventListener('click', () => {
    activeFilter = button.dataset.filter;
    document.querySelectorAll('.filter').forEach((other) => {
      const on = other === button;
      other.classList.toggle('active', on);
      other.setAttribute('aria-pressed', String(on));
    });
    logs.system.querySelectorAll('.entry').forEach((entry) => {
      entry.hidden = activeFilter !== 'all' && entry.dataset.team !== activeFilter;
    });
  });
});

document.addEventListener('keydown', (event) => {
  const tag = (event.target.tagName || '').toLowerCase();
  if (event.altKey || event.ctrlKey || event.metaKey || tag === 'input' || tag === 'textarea') return;
  if (event.key === 'Escape' && socket) { stopScan(); return; }
  const index = Number.parseInt(event.key, 10);
  const keys = Object.keys(targets);
  if (sourceMode === 'demo' && index >= 1 && index <= keys.length && !socket) { selectTarget(keys[index - 1], true); return; }
  if (event.key === 'Enter' && !socket && configured && (tag === 'body' || event.target.classList.contains('target'))) {
    event.preventDefault();
    startScan();
  }
});

updateScanProfile();
initialize();
