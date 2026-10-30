// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
'use strict';

const el = (id) => document.getElementById(id);
const logs = { red: el('red-log'), blue: el('blue-log'), system: el('sys-log') };
const STAGES = ['sandbox', 'baseline', 'analysis', 'probe', 'patch', 'regression', 'cleanup'];
const RESULT_LABELS = {
  verified: 'Boundary check passed',
  not_confirmed: 'Boundary not confirmed',
  no_finding: 'No finding this cycle',
  inconclusive: 'Probe inconclusive',
  rolled_back: 'Change rolled back',
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
// Server-sent health.scan_profiles overrides these defaults once loaded
// (renderProfiles copies them into scanProfiles; updateScanProfile prefers them).
let scanProfiles = [];
const scanProfileCycles = (key) => {
  const server = scanProfiles.find((p) => p.key === key);
  return server ? server.cycles : SCAN_PROFILE_CYCLES[key];
};

let targets = {};
let socket = null;
let latestResult = null;
let closeReason = null; // 'invalid' | 'busy' | null — set when the server refuses a scan, so onclose keeps the specific next step instead of overwriting it.
let userCancelled = false; // set by stopScan so onclose reports "Stopped" instead of a false error.
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
  const node = el('status');
  if (!node) return;
  node.textContent = text;
  node.dataset.state = state;
}

function chip(id, state, label) {
  const node = el(id);
  if (!node) return;
  node.dataset.state = state;
  if (label && node.lastChild) node.lastChild.textContent = label;
}

let toastTimer = null;
function toast(text) {
  const node = el('toast');
  if (!node) return;
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
    try {
      const area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.append(area);
      area.select();
      document.execCommand('copy');
      area.remove();
      toast(`${label} copied`);
    } catch {
      toast('Clipboard unavailable in this browser context');
    }
  }
}

function formatElapsed(ms) {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes}m ${String(seconds % 60).padStart(2, '0')}s` : `${seconds}s`;
}

/* ---------- logs ---------- */

function clearEmpty(area) {
  if (!area) return;
  const empty = area.querySelector('.empty');
  if (empty) empty.remove();
}

function buildEntry(team, text, withTag) {
  const normalized = team === 'red' || team === 'blue' || team === 'research' || team === 'green' ? team : 'system';
  const line = document.createElement('div');
  line.className = 'entry';
  line.dataset.team = normalized;
  const stamp = document.createElement('time');
  stamp.textContent = new Date().toLocaleTimeString([], { hour12: false });
  line.append(stamp);
  if (withTag) {
    const tag = document.createElement('span');
    tag.className = `tag tag-${normalized}`;
    tag.textContent = normalized;
    line.append(tag);
  }
  const body = document.createElement('span');
  body.className = 'msg';
  body.textContent = String(text);
  line.append(body);
  if (activeFilter !== 'all' && withTag && normalized !== activeFilter) line.hidden = true;
  return line;
}

function append(area, line) {
  if (!area || !line) return;
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
  if (!node) return;
  node.replaceChildren();
  if (leader) {
    const lead = document.createElement('span');
    lead.className = 'agent-chip leader';
    lead.dataset.name = leader;
    lead.textContent = '';
    const dot = document.createElement('i');
    const label = document.createElement('span');
    label.textContent = leader;
    lead.append(dot, label);
    node.append(lead);
  }
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
function updatePassChip(text) {
  const chip = el('pass-chip');
  if (!chip) return;
  const start = /\[sweep (standard|deep|threat_actor)\]/.exec(text);
  if (start) {
    const n = start[1] === 'standard' ? 1 : start[1] === 'deep' ? 2 : 3;
    const label = start[1] === 'standard' ? 'standard' : start[1] === 'deep' ? 'deep' : 'threat-actor';
    chip.textContent = `Pass ${n}: ${label}`;
    chip.dataset.state = 'running';
    return;
  }
  if (/sweep verified/i.test(text) || /sweep failed/i.test(text)) {
    chip.textContent = 'Pass done';
    chip.dataset.state = 'idle';
  }
}
function writeComms(team, text) {
  const comms = el('comms-log');
  if (!comms) return;
  const m = CHATTER_RE.exec(String(text));
  if (!m) return;
  lightAgent(m[1]);
  const known = team === 'red' || team === 'blue' || team === 'research' || team === 'green' ? team : 'system';
  const line = buildEntry(known, text, true);
  append(comms, line);
}
function writeLine(team, text) {
  const known = team === 'red' || team === 'blue' || team === 'research' || team === 'green' ? team : 'system';
  updatePassChip(String(text));
  try { if (window.Panels && typeof window.Panels.renderTimeline === 'function') window.Panels.renderTimeline(known, text); } catch { /* timeline is decorative */ }
  if (known === 'red' || known === 'blue') {
    append(logs[known], buildEntry(known, text, false));
    document.querySelectorAll('.panel').forEach((panel) => panel.classList.toggle('active', panel.dataset.team === known));
  }
  // The activity timeline records every event so it can be filtered.
  append(logs.system, buildEntry(known, text, true));
  writeComms(known, text);
  if (team !== 'system' || /Cycle|probe|patch|regression|cleanup|Docker|Muse/i.test(String(text))) spawnTerminalPop(team, text);
  eventCount += 1;
  const counter = el('event-count');
  if (counter) counter.textContent = String(eventCount);
  advanceStage(known, String(text));
  if (window.SMSFx) window.SMSFx.onEvent(known, String(text));
}

function logText(team) {
  const area = logs[team];
  if (!area) return '';
  return [...area.querySelectorAll('.entry')]
    .filter((entry) => !entry.hidden)
    .map((entry) => entry.innerText.replace(/\n/g, ' '))
    .join('\n');
}

/* ---------- pipeline ---------- */

function setStage(name, state = 'active') {
  const index = STAGES.indexOf(name);
  if (index < 0) return;
  if (state === 'active' && index < currentStage) return;
  if (window.SMSFx) window.SMSFx.onStage(name, state);
  document.querySelectorAll('#pipeline li').forEach((item, i) => {
    if (state === 'active') {
      if (i < index) item.dataset.state = item.dataset.state === 'skipped' ? 'skipped' : 'done';
      if (i === index) item.dataset.state = 'active';
    }
  });
  if (state !== 'active') document.querySelector(`#pipeline li[data-stage="${name}"]`).dataset.state = state;
  currentStage = Math.max(currentStage, index);
  const fraction = (index + (state === 'active' ? 0.5 : 1)) / STAGES.length;
  const progress = el('progress');
  if (progress) progress.style.setProperty('--value', String(Math.min(1, fraction)));
}

function advanceStage(team, text) {
  const t = text.toLowerCase();
  // Green builder runs before the sandbox exists: pin its intel/generation
  // lines to the sandbox node so the pipeline lights up live without
  // blocking later stages (sandbox index 0 never regresses the guard).
  if (team === 'green') { setStage('sandbox'); return; }
  if (team === 'research') setStage('analysis');
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
  const progress = el('progress');
  if (progress) progress.style.setProperty('--value', '0');
}

function finishPipeline(result) {
  const items = [...document.querySelectorAll('#pipeline li')];
  const ok = ['verified', 'not_confirmed', 'no_findings', 'completed'].includes(result.status);
  items.forEach((item, i) => {
    if (item.dataset.state === 'active') item.dataset.state = ok ? 'done' : 'failed';
    else if (!item.dataset.state && i < STAGES.length - 1) item.dataset.state = 'skipped';
  });
  const cleanup = items[items.length - 1];
  if (cleanup) cleanup.dataset.state = result.cleanup_ok ? 'done' : 'failed';
  const progress = el('progress');
  if (progress) {
    progress.style.setProperty('--value', '1');
    progress.dataset.state = result.status;
  }
  if (window.SMSFx) window.SMSFx.onFinish(result);
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
  const select = el('target-select');
  if (!list || !select) return;
  list.replaceChildren();
  select.replaceChildren();
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
  if (socket || !['demo', 'demo-build', 'project', 'mcp', 'binary'].includes(mode)) return;
  sourceMode = mode;
  document.querySelectorAll('.mode').forEach((button) => {
    const active = button.dataset.mode === mode;
    button.classList.toggle('active', active);
    button.setAttribute('aria-checked', String(active));
    button.tabIndex = active ? 0 : -1;
  });
  el('demo-config').hidden = mode !== 'demo';
  el('demo-build-config').hidden = mode !== 'demo-build';
  el('project-form').hidden = mode !== 'project';
  el('mcp-form').hidden = mode !== 'mcp';
  el('binary-form').hidden = mode !== 'binary';
  el('run-label').textContent = mode === 'project' ? 'Run project verification' : mode === 'demo-build' ? 'Grow and verify demo' : mode === 'mcp' ? 'Verify snippet in Docker' : mode === 'binary' ? 'Sweep binary in Docker' : 'Run demo verification';
  el('target-description').textContent = mode === 'project'
    ? 'The repository is copied into an isolated sandbox. Source may be sent to the configured Muse endpoint only after consent.'
    : mode === 'demo-build'
      ? 'Greenhouse grows a fresh demo from your build brief and vulnerabilities below, then red and blue exercise it in Docker.'
      : mode === 'mcp'
        ? 'Paste a snippet below — the same red/blue Docker loop verifies it and returns the VerdictReceipt plus exit codes (also at POST /mcp).'
        : mode === 'binary'
          ? 'Upload a compiled binary — static reversing profiles it, then the same 3-pass loop probes it through the trusted harness (also at /ws/binary).'
          : (targets[el('target-select').value] ? `Selected ${targets[el('target-select').value].title} · ${targets[el('target-select').value].filename}. The original fixture is never modified.` : 'Choose a bundled fixture.');
  el('project-errors').hidden = true;
  // Build-brief affordance: landing on Green build puts the cursor in the
  // brief field so the Wonder-built flow starts with one keystroke.
  if (mode === 'demo-build' && el('demo-build-brief')) el('demo-build-brief').focus({ preventScroll: true });
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
  const cycles = scanProfileCycles(key);
  const server = scanProfiles.find((p) => p.key === key);
  const description = server ? server.description : '';
  const custom = key === 'custom';
  const ultra = key === 'ultra_heavy';
  el('project-cycles').readOnly = !custom;
  el('project-red-agents').disabled = !ultra;
  el('project-blue-agents').disabled = !ultra;
  if (!custom) el('project-cycles').value = String(cycles);
  const cycleLabel = cycles === 1 ? '1 cycle' : `${cycles} cycles`;
  el('project-scan-description').textContent = custom
    ? 'Legacy compatibility mode · choose 1 to 20 single-pass cycles.'
    : `${cycleLabel} · each cycle runs Red, Blue, Red, Blue with cumulative focus${key === 'ultra_heavy' ? ' and bounded automatic discovery from the first pass' : ''}${description ? ` · ${description}` : ''}`;
  updateDemoScanProfile();
}

function updateDemoScanProfile() {
  const sel = el('demo-scan-profile');
  if (!sel) return;
  const key = sel.value;
  const cycles = scanProfileCycles(key);
  const custom = key === 'custom';
  const ultra = key === 'ultra_heavy';
  el('demo-cycles').readOnly = !custom;
  el('demo-red-agents').disabled = !ultra;
  el('demo-blue-agents').disabled = !ultra;
  if (!custom) el('demo-cycles').value = String(cycles);
  const cycleLabel = cycles === 1 ? '1 cycle' : `${cycles} cycles`;
  el('demo-scan-description').textContent = custom
    ? 'Legacy compatibility mode · choose 1 to 20 single-pass cycles.'
    : `${cycleLabel} · each cycle runs Red, Blue, Red, Blue with cumulative focus${key === 'ultra_heavy' ? ' and bounded automatic discovery from the first pass' : ''}`;
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
  if (scanProfile !== 'custom' && scanProfileCycles(scanProfile) === undefined) { el('project-scan-profile').setAttribute('aria-invalid', 'true'); errors.push('Choose a valid scan intensity.'); }
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
  scanProfiles = health.scan_profiles || [];
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
  const before = node.textContent;
  node.textContent = value;
  node.dataset.state = good === undefined ? 'neutral' : good ? 'good' : 'bad';
  // Facts that flip between scans flash once so regressions catch the eye.
  if (before !== '—' && before !== String(value)) {
    node.classList.remove('fact-flash');
    void node.offsetWidth;
    node.classList.add('fact-flash');
  }
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
  const compression = payload.compression || {};
  const raw = Number(compression.raw_tokens_estimated || 0);
  const sent = Number(compression.compressed_tokens_sent || 0);
  const saved = Number(compression.tokens_saved || 0);
  const ratio = Number(compression.compression_ratio || 0);
  const badge = el('fact-compression');
  if (badge) badge.textContent = raw ? `${raw.toLocaleString()} → ${sent.toLocaleString()} tokens (saved ${saved.toLocaleString()}, ${Math.round(ratio * 100)}%)` : '—';
  const vaultBadge = el('fact-vault');
  if (vaultBadge) {
    const recall = payload.vault_recall || '';
    const namespaces = (payload.vault_namespaces || []).join(',');
    vaultBadge.textContent = recall && recall !== 'VAULT_UNAVAILABLE' ? `${recall}${namespaces ? ` (${namespaces})` : ''}` : '—';
  }
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

function renderCycles(cycles, records) {
  const list = el('cycle-list');
  list.replaceChildren();
  el('cycle-reports').hidden = (!Array.isArray(cycles) || cycles.length === 0) && (!Array.isArray(records) || records.length === 0);
  if (Array.isArray(records) && records.length) {
    const details = document.createElement('details');
    details.className = 'cycle-report';
    const summary = document.createElement('summary');
    summary.textContent = `Threat intel · ${records.length} record${records.length === 1 ? '' : 's'} (untrusted grounding, Docker evidence decided)`;
    const body = document.createElement('div');
    body.className = 'cycle-body';
    const pre = document.createElement('pre');
    pre.textContent = records.slice(0, 16).map((r) => `${r.cve_id || '?'} [${r.source || r.scanner || '?'}] ${r.severity || ''} ${r.title || ''}`.trim()).join('\n');
    body.append(pre);
    details.append(summary, body);
    list.append(details);
  }
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

/* ---------- Wave 2 items 1-4 defensive collectors (SPEC 14.8) ----------
   Read-only probes: every field optional, absent/odd shapes degrade to
   null (never throw). Surfaces: receipt facts + receipt.json download,
   guard rationale list, fast-lane topping list, mutation evidence facts. */

function w2v2AsRecord(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) return value;
  return null;
}

function w2v2Receipt(payload) {
  try {
    // REAL first: result.receipt (VerdictReceipt) or any cycle.receipt
    // (CycleReceipt); legacy verdict_receipt fallback.
    let receipt = w2v2AsRecord(payload && payload.receipt);
    if (!receipt && Array.isArray(payload && (payload.cycle_reports || payload.cycles))) {
      for (const cycle of payload.cycle_reports || payload.cycles) {
        receipt = w2v2AsRecord(cycle && cycle.receipt);
        if (receipt) break;
      }
    }
    if (!receipt) receipt = w2v2AsRecord(payload && payload.verdict_receipt);
    if (!receipt) return null;
    const parts = [];
    const fixture = receipt.fixture || receipt.target;
    if (fixture) parts.push(String(fixture).slice(0, 64));
    const pre = receipt.pre_exit_code ?? receipt.pre_probe_exit;
    const post = receipt.post_exit_code ?? receipt.post_probe_exit;
    if (pre !== undefined || post !== undefined) {
      parts.push(`probe ${pre}/${post}`);
    }
    if (receipt.regression_passed) parts.push('regression passed');
    else if (receipt.baseline_regression_exit !== undefined || receipt.patched_regression_exit !== undefined) {
      parts.push(`regression ${receipt.baseline_regression_exit}/${receipt.patched_regression_exit}`);
    }
    if (receipt.differential_passed === true) parts.push('differential passed');
    if (receipt.property_passed === true) parts.push('properties passed');
    const hash = receipt.patch_sha256 || receipt.patch_hash || receipt.patch_sha;
    if (hash) parts.push(`sha ${String(hash).slice(0, 16)}`);
    return parts.length ? parts.join(' · ').slice(0, 200) : null;
  } catch { return null; }
}

function w2v2Guards(payload) {
  try {
    // REAL first: GuardRationale at evidence.replacement_validation or
    // evidence root (guard_id/reason/trigger); legacy list fallback.
    const found = [];
    const readGuard = (item) => {
      if (typeof item === 'string') return item.trim() ? { text: item.slice(0, 80) } : null;
      const row = w2v2AsRecord(item);
      if (!row) return null;
      const guard = row.guard_id || row.guard || row.rule || row.check || 'guard';
      const line = row.trigger || row.protected_line || row.line || '';
      const reason = row.reason || row.action || '';
      if (!row.guard_id && !row.guard && !reason) return null;
      return { guard: String(guard).slice(0, 80), line: String(line).slice(0, 80), reason: String(reason).slice(0, 160) };
    };
    const top = payload && payload.guard_rationale;
    if (top) {
      const g = readGuard(top);
      if (g) found.push(g);
    }
    const cycles = (payload && (payload.cycle_reports || payload.cycles)) || [];
    if (Array.isArray(cycles)) {
      for (const cycle of cycles) {
        const ev = cycle && cycle.evidence;
        const rv = ev && ev.replacement_validation;
        for (const cand of [(rv && rv.guard_rationale), ev && ev.guard_rationale]) {
          if (!cand) continue;
          const g = readGuard(cand);
          if (g && !found.some((h) => (h.guard || h.text) === (g.guard || g.text))) found.push(g);
        }
        if (found.length >= 3) break;
      }
    }
    if (found.length) return found.slice(0, 8);
    const raw = (payload && (payload.guard_rationales || payload.guard_evidence)) || null;
    if (!Array.isArray(raw) || !raw.length) return [];
    return raw.slice(0, 8).map(readGuard).filter(Boolean);
  } catch { return []; }
}

function w2v2Topping(payload) {
  try {
    const vulns = payload && payload.vulnerabilities;
    if (!Array.isArray(vulns) || !vulns.length) return [];
    return vulns.slice(0, 10)
      .map((v) => w2v2AsRecord(v))
      .filter((v) => v && (v.queue_evidence || v.reach_score !== undefined && v.reach_score !== null))
      .map((v) => ({
        id: String((v.cves && v.cves[0]) || v.id || 'vuln').slice(0, 40),
        score: v.reach_score,
        queue: typeof v.queue_evidence === 'string' ? v.queue_evidence.slice(0, 120) : null,
        fixed: Array.isArray(v.fixed_versions) ? v.fixed_versions.slice(0, 4) : [],
        kev: Boolean(v.kev_listed),
        epss: typeof v.epss_percentile === 'number' ? v.epss_percentile : null,
        evidence: Array.isArray(v.reach_evidence) ? v.reach_evidence.slice(0, 4).map((e) => String(e).slice(0, 160)) : []
      }));
  } catch { return []; }
}

function w2v2Mutation(payload) {
  try {
    // REAL first: ExecutionEvidence at cycle evidence verifications
    // (exit_code/output, N/M parsed from output); legacy dict fallback.
    const readEv = (ev) => {
      const row = w2v2AsRecord(ev);
      if (!row || row.exit_code === undefined) return null;
      const text = String(row.output || '');
      const match = text.match(/(\d+\s*\/\s*\d+)/);
      const verb = row.exit_code === 0 ? 'held' : 'failed';
      if (match) return { text: `${match[1]} mutations ${verb} (exit ${row.exit_code})`.slice(0, 200), failures: 0, total: 0, verdict: verb };
      return { text: `mutations ${verb} (exit ${row.exit_code})`.slice(0, 80), failures: 0, total: 0, verdict: verb };
    };
    const cycles = (payload && (payload.cycle_reports || payload.cycles)) || [];
    if (Array.isArray(cycles)) {
      for (const cycle of cycles) {
        const ev = cycle && cycle.evidence;
        for (const section of ['patched_verification', 'pre_verification']) {
          const got = ev && ev[section] && readEv(ev[section].mutations);
          if (got) return got;
        }
        const direct = ev && readEv(ev.mutations);
        if (direct) return direct;
      }
    }
    if (payload && payload.mutations !== undefined && !w2v2AsRecord(payload.mutations)) {
      const got = readEv(payload.mutations);
      if (got) return got;
    }
    const row = w2v2AsRecord(payload && (payload.mutation_evidence || payload.mutations));
    if (!row) return null;
    const total = row.mutations ?? row.count ?? row.total;
    const failures = row.failures ?? row.failed ?? 0;
    const verdict = row.verdict || row.status || '';
    if (typeof total === 'number') return { text: `${failures}/${total} failed${verdict ? ` (${verdict})` : ''}`.slice(0, 200), failures, total, verdict: String(verdict).slice(0, 40) };
    if (verdict) return { text: String(verdict).slice(0, 80), failures: 0, total: 0, verdict: String(verdict).slice(0, 40) };
    if (row.exit_code !== undefined) return readEv(row);
    return null;
  } catch { return null; }
}

function renderW2v2(payload) {
  try {
    const receipt = w2v2Receipt(payload);
    fact('fact-receipt', receipt || 'Not reported', receipt ? true : undefined);
    const guards = w2v2Guards(payload);
    fact('fact-guards', guards.length ? guards.map((g) => g.text || `${g.guard}${g.line ? `: ${g.line}` : ''}`).join('; ').slice(0, 200) : 'Not reported', guards.length ? true : undefined);
    const list = el('guard-list');
    if (list) {
      list.replaceChildren();
      guards.forEach((g) => {
        const item = document.createElement('li');
        const name = document.createElement('strong');
        name.textContent = g.text || g.guard;
        item.append(name);
        if (!g.text && (g.line || g.reason)) {
          const detail = document.createElement('span');
          detail.textContent = [g.line, g.reason].filter(Boolean).join(' — ');
          item.append(document.createTextNode(' '), detail);
        }
        list.append(item);
      });
      const wrap = el('guard-rationales');
      if (wrap) wrap.hidden = guards.length === 0;
    }
    const topping = w2v2Topping(payload);
    fact('fact-topping', topping.length ? `${topping[0].id} ${topping[0].queue || `reach ${topping[0].score}`}` : 'Not reported', topping.length ? true : undefined);
    const topList = el('topping-list');
    if (topList) {
      topList.replaceChildren();
      topping.forEach((t) => {
        const item = document.createElement('li');
        const name = document.createElement('strong');
        name.textContent = t.queue ? `${t.id} · ${t.queue}` : `${t.id} · reach ${t.score}`;
        item.append(name);
        const bits = [];
        if (t.fixed.length) bits.push(`fix ${t.fixed[0]}`);
        if (t.kev) bits.push('KEV-listed');
        if (t.epss !== null) bits.push(`EPSS ${t.epss.toFixed(2)}`);
        if (bits.length) {
          const detail = document.createElement('span');
          detail.textContent = ` ${bits.join(' · ')}`;
          item.append(detail);
        }
        if (t.evidence.length) {
          const sub = document.createElement('ul');
          t.evidence.forEach((line) => {
            const row = document.createElement('li');
            row.textContent = line;
            sub.append(row);
          });
          item.append(sub);
        }
        topList.append(item);
      });
      const wrap = el('fast-lane-topping');
      if (wrap) wrap.hidden = topping.length === 0;
    }
    const mutation = w2v2Mutation(payload);
    fact('fact-mutations', mutation ? mutation.text : 'Not reported', mutation ? true : undefined);
    const mWrap = el('mutation-evidence');
    if (mWrap) {
      mWrap.hidden = !mutation;
      const mText = el('mutation-text');
      if (mText && mutation) mText.textContent = mutation.text;
    }
    const receiptBtn = el('download-receipt-btn');
    if (receiptBtn) receiptBtn.hidden = !receipt;
  } catch { /* defensive render: facts keep prior values */ }
}

function summaryEvidence(payload) {
  if (Array.isArray(payload.pass_results) && payload.pass_results.length) {
    // Sweep payload: roll per-pass Docker exits into the shared summary shape.
    const passes = payload.pass_results;
    const held = passes.filter((p) => p.cleared || (p.receipt && p.post_exit_code === 1 && p.regression_passed)).length;
    const pres = passes.map((p) => p.pre_exit_code).filter((c) => c !== null && c !== undefined);
    const posts = passes.map((p) => p.post_exit_code).filter((c) => c !== null && c !== undefined);
    return {
      ...payload,
      baseline_passed: payload.baseline_passed,
      pre_exit_code: pres.length === 1 ? pres[0] : undefined,
      post_exit_code: posts.length === 1 ? posts[posts.length - 1] : undefined,
      regression_passed: passes.every((p) => p.cleared || p.regression_passed),
      pre_summary: pres.length > 1 ? `${pres.filter((c) => c === 0).length}/${pres.length} reachable` : undefined,
      post_summary: posts.length > 1 ? `${posts.filter((c) => c === 1).length}/${posts.length} blocked` : undefined,
      pre_good: pres.every((c) => c === 0),
      post_good: posts.every((c) => c === 1),
      sweep_summary: `${held}/${passes.length} passes hold`,
    };
  }
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

function renderResultMeta(payload, evidence, cycles) {
  let meta = el('result-meta');
  if (!meta) {
    meta = document.createElement('p');
    meta.id = 'result-meta';
    el('result-message').after(meta);
  }
  const parts = [];
  const before = evidence.pre_summary || probeLabel(evidence.pre_exit_code)[0];
  const after = evidence.post_summary || probeLabel(evidence.post_exit_code)[0];
  if (before !== 'Not run' || after !== 'Not run') parts.push(`${before} → ${after}`);
  if (Array.isArray(cycles) && cycles.length) {
    const kept = cycles.filter((cycle) => cycle && cycle.status === 'retained').length;
    parts.push(`${kept}/${cycles.length} cycles verified`);
  } else if (evidence.sweep_summary) {
    parts.push(evidence.sweep_summary);
  } else if (payload.status) {
    parts.push(payload.status === 'verified' ? '1/1 verified' : '0/1 verified');
  }
  if (startedAt) parts.push(`took ${formatElapsed(Date.now() - startedAt)}`);
  meta.textContent = parts.join(' · ');
  meta.hidden = parts.length === 0;
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
  renderResultMeta(payload, evidence, cycles);
  fact('fact-baseline', evidence.baseline_passed === undefined ? 'Not reported' : evidence.baseline_passed ? 'Passed' : 'Not passed', evidence.baseline_passed);
  const pre = evidence.pre_summary ? [evidence.pre_summary, evidence.pre_good ? undefined : false] : probeLabel(evidence.pre_exit_code);
  fact('fact-pre', pre[0], evidence.pre_exit_code === 0 ? undefined : pre[1]);
  fact('fact-regression', evidence.regression_passed === undefined ? 'Not reported' : evidence.regression_passed ? 'Passed' : 'Not passed', evidence.regression_passed);
  fact('fact-post', ...(evidence.post_summary ? [evidence.post_summary, evidence.post_good] : probeLabel(evidence.post_exit_code)));
  fact('fact-cleanup', cleanupOk ? 'Resources removed' : 'Inspect Docker', cleanupOk);
  renderW2v2(payload);
  renderUsage(displayPayload);
  renderCycles(cycles, payload.research_records);
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

/* ---------- shared socket query: profile + opt-in intel (off default) ---------- */

function socketQuery() {
  const params = [];
  if (profiles.length) params.push(`profile=${encodeURIComponent(selectedProfile)}`);
  const sweep = el('sweep-passes');
  if (sweep && sweep.value !== '1') params.push(`sweep_passes=${encodeURIComponent(sweep.value)}`);
  if (el('research-toggle') && el('research-toggle').checked) {
    params.push('research=on');
    if (el('research-scanners-toggle') && el('research-scanners-toggle').checked) {
      params.push(`research_scanners=${encodeURIComponent('trivy,grype,osv-scanner,dependency-check,dependency-track')}`);
    }
  }
  return params.length ? `?${params.join('&')}` : '';
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
    // Keep the technical detail but always end with the one action that fixes it.
    el('setup').textContent = `${error.message} Start the server with python main.py --serve --port 8000, then reload this page.`;
  }
}

function startScan() {
  if (socket || !configured) return;
  closeReason = null;
  userCancelled = false;
  const key = el('target-select').value;
  if (sourceMode === 'demo' && !targets[key]) { toast('Choose a target first, then run again'); return; }
  if (sourceMode === 'demo' && key === 'binary_argv_echo') {
    el('setup').hidden = false;
    el('setup').textContent = 'binary_argv_echo is a compiled ELF fixture — switch to Binary sweep mode to verify it through the binary harness, not the fixture socket.';
    toast('binary_argv_echo needs Binary sweep mode');
    return;
  }
  if (sourceMode === 'demo-build') { startDemoBuild(); return; }
  if (sourceMode === 'mcp') { submitMcpSnippet(); return; }
  if (sourceMode === 'binary') { submitBinary(); return; }
  const spec = sourceMode === 'project' ? projectSpec() : null;
  if (sourceMode === 'project' && !spec) {
    status('Fix the highlighted project fields below, then run again', 'warn');
    const firstInvalid = el('project-form').querySelector('[aria-invalid="true"]');
    if (firstInvalid) firstInvalid.focus();
    return;
  }
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
  // Opt-in intel: off by default, mirrors the --research/--research-scanners CLI flags.
  const query = socketQuery();
  const base = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`;
  socket = new WebSocket(sourceMode === 'project' ? `${base}/ws/project${query}` : `${base}/ws/combat/${encodeURIComponent(key)}${query}`);
  socket.onmessage = handleSocketMessage;
  socket.onerror = () => { writeLine('system', 'Connection hiccup during verification — the scan keeps running on the server. If it stalls, stop and run again.'); };
  socket.onclose = handleScanClose;
  if (spec) socket.onopen = () => {
    try {
      if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(spec));
      else return;
    } catch { return; }
    writeLine('system', `Project specification accepted · ${spec.scan_profile} intensity · ${spec.cycles} cycle${spec.cycles === 1 ? '' : 's'} · ${spec.red_agents} red / ${spec.blue_agents} blue agents.`);
  };
}

function handleSocketMessage(event) {
  try {
    const payload = JSON.parse(event.data);
    if (payload.type === 'result') {
      showResult(payload);
    } else if (payload.type === 'invalid' || payload.type === 'busy') {
      // Server refused the scan (bad spec/demo request, or lock held).
      // Remember which, so the close handler below keeps this specific
      // next step instead of overwriting it with the generic message.
      closeReason = payload.type;
      if (payload.type === 'busy') {
        status('Another scan is already running — wait for it to finish, then run again', 'error');
        writeLine(payload.team || 'system', 'Scan refused: another scan holds the server lock. Wait for it to finish, then run again.');
        toast('Server is busy — try again when the current scan finishes');
      } else {
        status(payload.msg || 'Server rejected the request — fix the highlighted fields, then run again', 'error');
        writeLine(payload.team || 'system', `${payload.msg || 'Invalid request.'} Fix the highlighted fields, then run again.`);
        toast('Request rejected — check the highlighted fields');
      }
    } else {
      writeLine(payload.team, payload.msg);
    }
  } catch {
    writeLine('system', 'Received an unreadable server event — the scan continues; check the server terminal if this repeats.');
  }
}

function handleScanClose() {
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
  if (latestResult) { closeReason = null; userCancelled = false; return; }
  if (userCancelled) {
    status('Scan stopped — no changes were applied', 'warn');
    writeLine('system', 'Scan stopped by user. The original fixture is untouched; run again whenever ready.');
    toast('Scan stopped');
  } else if (closeReason === 'busy' || closeReason === 'invalid') {
    // handleSocketMessage already showed the specific next step; the
    // socket close that follows a refusal must not overwrite it.
    document.querySelectorAll('#pipeline li[data-state="active"]').forEach((item) => { item.dataset.state = 'failed'; });
  } else {
    status('Lost connection to the server — start it, then run again', 'error');
    writeLine('system', 'Lost connection to the server before a result arrived. Start it with python main.py --serve --port 8000, then run again. Cleanup on the server finishes on its own.');
    toast('Disconnected — restart the server, then run again');
    document.querySelectorAll('#pipeline li[data-state="active"]').forEach((item) => { item.dataset.state = 'failed'; });
  }
  userCancelled = false;
}

function stopScan() {
  if (!socket) return;
  userCancelled = true;
  el('stop-btn').disabled = true;
  status('Stopping scan — finishing cleanup', 'running');
  try { socket.close(1000, 'User cancelled'); } catch { /* socket already gone */ }
}

async function submitMcpSnippet() {
  // MCP snippet path: POST JSON-RPC tools/call to /mcp, same red/blue
  // Docker loop as every other surface. No WebSocket involved.
  const errors = el('mcp-errors');
  const out = el('mcp-result');
  errors.hidden = true;
  out.hidden = true;
  const filename = el('mcp-filename').value.trim() || 'app.js';
  const source = el('mcp-source').value;
  const contractText = el('mcp-contract').value.trim();
  const problems = [];
  if (!source) problems.push('Paste the snippet source first.');
  if (source && new Blob([source]).size > 65536) problems.push('Snippet exceeds 64 KiB.');
  if (!contractText) problems.push('Describe the behavior contract first.');
  if (problems.length) {
    errors.textContent = problems.join(' ');
    errors.hidden = false;
    return;
  }
  status('Snippet verification running', 'running');
  setStage('sandbox');
  writeLine('system', `MCP submit_code_snippet → ${filename} (${el('mcp-language').value})`);
  el('run-btn').disabled = true;
  el('stop-btn').hidden = true;
  try {
    const resp = await fetch('/mcp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'tools/call',
        params: {
          name: 'submit_code_snippet',
          arguments: {
            filename,
            language: el('mcp-language').value,
            source,
            contract: contractText,
          },
        },
      }),
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error.message || 'MCP call failed.');
    const structured = data.result.structuredContent;
    out.textContent = `status=${structured.status} pre_probe_exit=${structured.pre_probe_exit} post_probe_exit=${structured.post_probe_exit} receipt=${structured.receipt ? structured.receipt.patch_sha256.slice(0, 12) : 'none'}`;
    out.hidden = false;
    setStage('cleanup');
    status(`Snippet ${structured.status}`, structured.status === 'verified' ? 'ready' : 'warn');
    writeLine('system', `MCP result: status=${structured.status} pre=${structured.pre_probe_exit} post=${structured.post_probe_exit}`);
  } catch (err) {
    errors.textContent = `Snippet verification failed: ${err.message}`;
    errors.hidden = false;
    status('Snippet verification failed', 'error');
  } finally {
    el('run-btn').disabled = false;
  }
}

function submitBinary() {
  // Binary sweep path: file bytes -> base64 first WS frame on /ws/binary,
  // same 3-pass Docker loop as every other surface over the shared socket flow.
  const errors = el('binary-errors');
  errors.hidden = true;
  const files = el('binary-file').files;
  const filename = (el('binary-filename').value.trim() || (files.length && files[0].name)) || '';
  const contractText = el('binary-contract').value.trim();
  const problems = [];
  if (!files.length) problems.push('Choose a compiled binary file first.');
  else if (files[0].size > 8 * 1024 * 1024) problems.push('Binary exceeds 8 MiB.');
  if (!filename) problems.push('Enter the bare filename (no paths).');
  if (!contractText) problems.push('Describe the behavior contract first.');
  if (problems.length) {
    errors.textContent = problems.join(' ');
    errors.hidden = false;
    return;
  }
  status('Binary sweep running', 'running');
  setStage('sandbox');
  writeLine('system', `Binary sweep → ${filename} (${files[0].size} bytes)`);
  const reader = new FileReader();
  reader.onerror = () => {
    errors.textContent = 'Could not read the binary file.';
    errors.hidden = false;
    status('Binary sweep failed', 'error');
  };
  reader.onload = () => {
    const bytes = new Uint8Array(reader.result);
    let binary = '';
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    const payload = JSON.stringify({
      blob_b64: btoa(binary),
      filename,
      contract: contractText,
    });
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
    el('stop-btn').hidden = false;
    el('stop-btn').disabled = false;
    startedAt = Date.now();
    const base = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`;
    socket = new WebSocket(`${base}/ws/binary${socketQuery()}`);
    socket.onmessage = handleSocketMessage;
    socket.onerror = () => { writeLine('system', 'Connection hiccup during verification — the scan keeps running on the server. If it stalls, stop and run again.'); };
    socket.onclose = handleScanClose;
    socket.onopen = () => {
      try {
        if (socket && socket.readyState === WebSocket.OPEN) socket.send(payload);
      } catch { /* socket already gone */ }
      writeLine('system', `Binary specification accepted · harness stages ${filename}.`);
    };
  };
  reader.readAsArrayBuffer(files[0]);
}

function startDemoBuild() {
  // Green builder path: Greenhouse grows a novel demo, then red/blue run it.
  closeReason = null;
  userCancelled = false;
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
    buildRoster(el('red-roster'), RED_NAMES.slice(0, 5), 'Warlord');
    buildRoster(el('blue-roster'), BLUE_NAMES.slice(0, 5), 'Warden');
    buildRoster(el('green-roster'), ['Greenhouse'], null);
  } catch { /* decorative */ }
  el('stop-btn').hidden = false;
  el('stop-btn').disabled = false;
  status('Greenhouse is building', 'running');
  // Immediate progress affordance: the first green WS event may take a
  // while (intel lookups), so light the sandbox node at send time.
  setStage('sandbox');
  startedAt = Date.now();
  el('elapsed').textContent = '0s';
  timer = setInterval(() => { el('elapsed').textContent = formatElapsed(Date.now() - startedAt); }, 1000);
  const base = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`;
  // Reuse the shared teardown/message flow by swapping sourceMode temporarily.
  sourceMode = 'demo-build';
  socket = new WebSocket(`${base}/ws/demo${socketQuery()}`);
  socket.onmessage = handleSocketMessage;
  socket.onerror = () => { writeLine('system', 'Connection hiccup during verification — the scan keeps running on the server. If it stalls, stop and run again.'); };
  socket.onclose = handleDemoClose;
  socket.onopen = () => {
    try {
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      const offline = inferenceMode === 'local'
        || (el('demo-offline') && el('demo-offline').checked)
        || !(el('demo-allow-remote') && el('demo-allow-remote').checked);
      const flawRaw = (el('demo-flaw-count') && el('demo-flaw-count').value || '').trim();
      const seedRaw = (el('demo-seed') && el('demo-seed').value || '').trim();
      const demoSize = (el('demo-size') && el('demo-size').value) || 'standard';
      const payload = { theme: (el('demo-theme') && el('demo-theme').value || '').slice(0, 200), build_brief: (el('demo-build-brief') && el('demo-build-brief').value || '').slice(0, 500), vulns: (el('demo-vulns') && el('demo-vulns').value || '').slice(0, 500), intel_offline: offline, scan_profile: (el('demo-scan-profile') && el('demo-scan-profile').value) || 'extra_light', cycles: Number((el('demo-cycles') && el('demo-cycles').value) || 1), red_agents: Number((el('demo-red-agents') && el('demo-red-agents').value) || 5), blue_agents: Number((el('demo-blue-agents') && el('demo-blue-agents').value) || 5), context_budget: Number((el('demo-budget') && el('demo-budget').value) || 32768) };
      payload.demo_size = demoSize === 'small' ? 'small' : 'standard';
      if (flawRaw !== '' && Number.isFinite(Number(flawRaw))) payload.flaw_count = Math.max(1, Math.min(8, Math.trunc(Number(flawRaw))));
      if (seedRaw !== '' && Number.isFinite(Number(seedRaw))) payload.seed = Math.trunc(Number(seedRaw));
      socket.send(JSON.stringify(payload));
    } catch { return; }
    writeLine('green', 'Greenhouse is growing a fresh demo. Stand by for seedlings.');
  };
}

/* Facts that flip value between scans flash via fact(); see function fact. */

function handleDemoClose() {
  if (timer) { clearInterval(timer); timer = null; }
  document.body.classList.remove('scanning');
  socket = null;
  // Restore the Green build mode: startDemoBuild temporarily borrows
  // sourceMode as a teardown flag; leaving it 'demo-build' keeps the run
  // label and config visible for the next build.
  setSourceMode('demo-build');
  el('run-btn').disabled = !configured;
  el('stop-btn').hidden = true;
  lockTargets(false);
  lockProfiles(false);
  lockProjectForm(false);
  if (latestResult) { closeReason = null; userCancelled = false; return; }
  if (userCancelled) {
    status('Build stopped — no changes were applied', 'warn');
    writeLine('system', 'Demo build stopped by user. Run again whenever ready.');
  } else if (closeReason !== 'busy' && closeReason !== 'invalid') {
    status('Lost connection to the server — start it, then run again', 'error');
    writeLine('system', 'Lost connection to the server before a result arrived. Start it with python main.py --serve --port 8000, then run again.');
    toast('Disconnected — restart the server, then run again');
  }
  // Refusals already showed their specific next step via handleSocketMessage.
  userCancelled = false;
}

/* ---------- wiring ---------- */

el('run-btn').addEventListener('click', startScan);
el('stop-btn').addEventListener('click', stopScan);
el('project-scan-profile').addEventListener('change', updateScanProfile);
el('demo-scan-profile').addEventListener('change', updateDemoScanProfile);
el('allow-remote').addEventListener('change', (event) => {
  // Consent errors clear as soon as the box is ticked; everything else
  // re-validates on submit via projectSpec().
  if (event.target.checked) event.target.removeAttribute('aria-invalid');
});
document.querySelectorAll('.mode').forEach((button) => button.addEventListener('click', () => setSourceMode(button.dataset.mode)));
// APG radio-group navigation: one tab stop, arrows select and keep focus in the group.
// Explicit clicks still retain Green build's existing focus-to-brief affordance.
document.querySelector('.mode-switch').addEventListener('keydown', (event) => {
  if (socket || event.altKey || event.ctrlKey || event.metaKey) return;
  const directions = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
  if (!(event.key in directions) && event.key !== 'Home' && event.key !== 'End') return;
  const buttons = [...document.querySelectorAll('.mode:not(:disabled)')];
  const index = buttons.indexOf(event.target);
  if (index < 0) return;
  event.preventDefault();
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
    : (index + directions[event.key] + buttons.length) % buttons.length;
  setSourceMode(buttons[next].dataset.mode);
  buttons[next].focus({ preventScroll: true });
});


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
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast('Report downloaded');
});

el('download-receipt-btn').addEventListener('click', () => {
  // LAW 8: live state only — exports the real receipt (VerdictReceipt at
  // result.receipt, CycleReceipt at first cycle.receipt); legacy
  // verdict_receipt fallback; never synthesizes evidence.
  const live = latestResult && (latestResult.receipt
    || ((latestResult.cycle_reports || latestResult.cycles || []).find((c) => c && c.receipt) || {}).receipt
    || latestResult.verdict_receipt);
  if (!live) { toast('No verdict receipt in this result'); return; }
  const receipt = {
    notice: 'Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.',
    license_url: 'https://polyformproject.org/licenses/noncommercial/1.0.0',
    receipt: live
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(receipt, null, 2)], { type: 'application/json' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `verdict-receipt-${latestResult.target || latestResult.project || 'scan'}.json`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast('Verdict receipt downloaded');
});

el('download-patch-btn').addEventListener('click', () => {
  const diff = latestResult && (latestResult.diff || latestResult.cumulative_diff);
  if (!diff) return;
  const url = URL.createObjectURL(new Blob([diff], { type: 'text/x-diff;charset=utf-8' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `candidate-${latestResult.target || latestResult.project || 'project'}.patch`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast('Candidate patch downloaded');
});

document.querySelectorAll('[data-copy]').forEach((button) => {
  button.addEventListener('click', () => {
    const team = button.dataset.copy;
    copyText(logText(team === 'red' || team === 'blue' || team === 'system' ? team : 'system'), team === 'system' ? 'Activity' : `${team[0].toUpperCase()}${team.slice(1)} trace`);
  });
});

el('copy-diff').addEventListener('click', (event) => {
  event.preventDefault();
  const diff = latestResult && (latestResult.diff || latestResult.cumulative_diff);
  copyText(diff, 'Candidate patch');
});

document.querySelectorAll('.filter').forEach((button) => {
  button.addEventListener('click', () => {
    activeFilter = button.dataset.filter;
    document.querySelectorAll('.filter').forEach((other) => {
      const on = other === button;
      other.classList.toggle('active', on);
      other.setAttribute('aria-pressed', String(on));
    });
    // Untagged red/blue panel entries bypass the filter; timeline entries carry tags.
    document.querySelectorAll('#sys-log .entry, #comms-log .entry').forEach((entry) => {
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

/* ---------- teardown guards (disconnect + rejected promises only) ---------- */

window.addEventListener('pagehide', () => {
  try {
    if (socket && socket.readyState !== WebSocket.CLOSED && socket.readyState !== WebSocket.CLOSING) socket.close(1000, 'Page hidden');
  } catch { /* socket already gone */ }
});

window.addEventListener('unhandledrejection', (event) => {
  event.preventDefault();
});

updateScanProfile();
initialize();
