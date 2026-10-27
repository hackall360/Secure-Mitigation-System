// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
'use strict';
const el = (id) => document.getElementById(id);
const logs = { red: el('red-log'), blue: el('blue-log'), system: el('sys-log') };
let targets = {};
let socket = null;
let latestResult = null;
let configured = false;
let startedAt = 0;
let timer = null;

function status(text, state = 'idle') {
  el('status').textContent = text;
  el('status').dataset.state = state;
}

function writeLine(team, text) {
  const area = logs[team] || logs.system;
  const empty = area.querySelector('.empty');
  if (empty) empty.remove();
  const line = document.createElement('div');
  line.className = 'entry';
  const stamp = document.createElement('time');
  stamp.textContent = new Date().toLocaleTimeString([], { hour12: false });
  line.append(stamp, document.createTextNode(String(text)));
  area.append(line);
  while (area.children.length > 300) area.firstChild.remove();
  area.scrollTop = area.scrollHeight;
}

async function initialize() {
  try {
    const responses = await Promise.all([fetch('/api/targets'), fetch('/api/health')]);
    if (!responses.every((response) => response.ok)) throw new Error('Configuration unavailable. Check the server terminal.');
    [targets, window.purpleboxHealth] = await Promise.all(responses.map((response) => response.json()));
    const health = window.purpleboxHealth;
    el('target-select').replaceChildren();
    Object.entries(targets).forEach(([key, target]) => {
      const option = document.createElement('option');
      option.value = key;
      option.textContent = target.title;
      el('target-select').append(option);
    });
    el('target-select').disabled = false;
    describeTarget();
    el('red-model').textContent = health.red_model;
    el('blue-model').textContent = health.blue_model;
    configured = health.api_key_configured;
    el('run-btn').disabled = !configured;
    status(configured ? 'Ready to verify' : 'Setup required');
    if (!configured) {
      el('setup').hidden = false;
      el('setup').textContent = 'Set META_MUSE_API_KEY in the server environment, initialize the Docker images with python main.py --init-images, then restart the server. The dashboard is available while you configure the scan runtime.';
    }
  } catch (error) {
    status('Unable to connect', 'error');
    el('setup').hidden = false;
    el('setup').textContent = error.message;
  }
}

function describeTarget() {
  const target = targets[el('target-select').value];
  el('target-description').textContent = target ? target.description : '';
}

el('target-select').addEventListener('change', describeTarget);
el('run-btn').addEventListener('click', () => {
  if (socket || !configured) return;
  latestResult = null;
  el('result-panel').hidden = true;
  Object.values(logs).forEach((area) => area.replaceChildren());
  el('run-btn').disabled = true;
  el('target-select').disabled = true;
  el('stop-btn').hidden = false;
  el('stop-btn').disabled = false;
  status('Verification running', 'running');
  startedAt = Date.now();
  timer = setInterval(() => { el('elapsed').textContent = `${Math.floor((Date.now() - startedAt) / 1000)}s ELAPSED`; }, 1000);
  socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/combat/${encodeURIComponent(el('target-select').value)}`);
  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.type === 'result') {
        latestResult = payload;
        const labels = { verified: 'Boundary check passed', not_confirmed: 'Boundary not confirmed', rejected: 'Candidate patch rejected', failed: 'Boundary still reachable', error: 'Scan could not complete' };
        el('result-title').textContent = labels[payload.status] || 'Scan finished';
        el('result-message').textContent = payload.message;
        el('result-panel').hidden = false;
        status(labels[payload.status] || 'Finished', payload.status);
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
    el('run-btn').disabled = !configured;
    el('target-select').disabled = false;
    el('stop-btn').hidden = true;
    el('elapsed').textContent = `${Math.floor((Date.now() - startedAt) / 1000)}s · SESSION CLOSED`;
    if (!latestResult) {
      status('Session ended without a result', 'error');
      writeLine('system', 'Connection closed. The server will finish cleanup before accepting another scan.');
    }
  };
});

el('stop-btn').addEventListener('click', () => {
  el('stop-btn').disabled = true;
  status('Stopping scan', 'running');
  if (socket) socket.close(1000, 'User cancelled');
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
  anchor.download = `purplebox-${latestResult.target}-report.json`;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

initialize();
