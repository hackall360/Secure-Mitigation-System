// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · Link — orchestrator client (same endpoints as v1/v2).
//   GET  /api/health, /api/targets
//   WS   /ws/combat/:target  /ws/project  /ws/demo  /ws/binary
//   POST /mcp  (JSON-RPC tools/call submit_code_snippet)
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const SAMPLE_TARGETS = {
    node_query_sink: { title: 'Node query sink', filename: 'app.js', description: 'Express-style search route that builds SQL from the query string.' },
    php_command_sink: { title: 'PHP command sink', filename: 'index.php', description: 'Ping helper that concatenates a host parameter into a shell command.' },
    mysql_insecure_conf: { title: 'MySQL insecure config', filename: 'my.cnf', description: 'Server configuration with unsafe network and file defaults.' },
    binary_argv_echo: { title: 'Binary argv echo', filename: 'argv_echo', description: 'Compiled ELF that echoes argv through a format function.' }
  };
  // Showcase targets so every lens (file · repo · binary · system) can be shown. Fake-run only unless
  // the orchestrator's /api/targets lists the same key.
  const SHOWCASE_TARGETS = {
    repo_notes_app: { title: 'Notes app repository', filename: 'notes-app', lens: 'repo', showcase: true, description: 'Multi-folder Node app: a sort parameter travels through three files into a raw SQL ORDER BY.' },
    system_shop_stack: { title: 'Shop stack snapshot', filename: 'shop-stack@snap-0420', lens: 'system', showcase: true, description: 'Five-service compose snapshot. The Redis cache was left reachable from outside with no password.' }
  };

  function wsBase() {
    if (location.protocol === 'file:') return null;
    return `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`;
  }

  async function getJSON(url, ms = 3500) {
    const ctl = typeof AbortController === 'function' ? new AbortController() : null;
    const timer = setTimeout(() => ctl && ctl.abort(), ms);
    try {
      const r = await fetch(url, ctl ? { signal: ctl.signal } : {});
      if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`);
      return await r.json();
    } finally { clearTimeout(timer); }
  }

  // Probe the orchestrator. Never throws: returns { online, health, targets, notes, ready }.
  async function probe() {
    if (location.protocol === 'file:') return { online: false, ready: false, health: null, targets: SAMPLE_TARGETS, notes: ['Opened from disk — orchestrator unavailable. Fake runs only.'] };
    try {
      const [targets, health] = await Promise.all([getJSON('/api/targets'), getJSON('/api/health')]);
      const inferenceMode = health.inference_mode || 'hosted';
      const keyOk = health.inference_ready === true || (inferenceMode !== 'local' && health.api_key_configured === true);
      const docker = (health.docker && health.docker.state) || 'unavailable';
      const notes = [];
      if (!keyOk) notes.push('Set META_MUSE_API_KEY in .env, export it, and restart the server.');
      if (docker === 'unavailable') notes.push('Docker is not reachable. Start the Docker service and make sure your user can access it.');
      if (docker === 'images_missing') notes.push('Sandbox images are missing. Run python main.py --init-images.');
      return { online: true, ready: keyOk && docker === 'ready', keyOk, docker, inferenceMode, health, targets: targets && Object.keys(targets).length ? targets : SAMPLE_TARGETS, notes };
    } catch (e) {
      return { online: false, ready: false, health: null, targets: SAMPLE_TARGETS, notes: [`Orchestrator offline (${e.message || 'no response'}). Start it with python main.py --serve --port 8000.`] };
    }
  }

  function query(opts = {}) {
    const p = [];
    if (opts.profile) p.push(`profile=${encodeURIComponent(opts.profile)}`);
    if (opts.sweep && String(opts.sweep) !== '1') p.push(`sweep_passes=${encodeURIComponent(opts.sweep)}`);
    if (opts.timeout_s !== undefined && opts.timeout_s !== null && String(opts.timeout_s) !== '' && Number(opts.timeout_s) !== 300) p.push(`timeout_s=${encodeURIComponent(opts.timeout_s)}`);
    if (opts.research) {
      p.push('research=on');
      if (opts.scanners) p.push(`research_scanners=${encodeURIComponent('trivy,grype,osv-scanner,dependency-check,dependency-track')}`);
    }
    return p.length ? `?${p.join('&')}` : '';
  }

  // One live session. handlers: onOpen, onLine(team,msg), onResult(payload), onRefuse(type,msg), onClose({cancelled, reason}), onError()
  class Session {
    constructor(path, body, handlers) {
      this.h = handlers || {};
      this.result = null;
      this.reason = null;
      this.cancelled = false;
      const base = wsBase();
      if (!base) throw new Error('No orchestrator when opened from disk.');
      this.ws = new WebSocket(`${base}${path}`);
      this.ws.onopen = () => {
        try { if (body !== undefined && this.ws.readyState === WebSocket.OPEN) this.ws.send(typeof body === 'string' ? body : JSON.stringify(body)); } catch { /* socket gone */ }
        this.h.onOpen && this.h.onOpen();
      };
      this.ws.onmessage = (ev) => {
        let payload;
        try { payload = JSON.parse(ev.data); } catch { this.h.onLine && this.h.onLine('system', 'Received an unreadable server event — the scan continues.'); return; }
        if (payload.type === 'result') { this.result = payload; this.h.onResult && this.h.onResult(payload); }
        else if (payload.type === 'invalid' || payload.type === 'busy') { this.reason = payload.type; this.h.onRefuse && this.h.onRefuse(payload.type, payload.msg || '', payload); }
        else if (payload.type === 'graph' || payload.type === 'topology') { this.h.onGraph && this.h.onGraph(payload); }
        // Connect-time hydration frame (server telemetry_hub.build_snapshot): state, not a stream line.
        else if (payload.type === 'snapshot') { this.snapshot = payload; this.h.onSnapshot && this.h.onSnapshot(payload); }
        // Coalesced telemetry burst: replay each event as its own real line, in order.
        else if (payload.type === 'telemetry_batch') { (payload.events || []).forEach((e) => { if (e && e.msg) this.h.onLine && this.h.onLine(e.team || 'telemetry', e.msg, e); }); }
        else if (payload.msg !== undefined && payload.msg !== null) this.h.onLine && this.h.onLine(payload.team, payload.msg, payload);
      };
      this.ws.onerror = () => { this.h.onError && this.h.onError(); };
      this.ws.onclose = () => { this.h.onClose && this.h.onClose({ cancelled: this.cancelled, reason: this.reason, result: this.result }); };
    }
    stop() { this.cancelled = true; try { this.ws.close(1000, 'User cancelled'); } catch { /* already closed */ } }
    get open() { return this.ws && this.ws.readyState <= 1; }
  }

  const open = {
    fixture: (key, opts, h) => new Session(`/ws/combat/${encodeURIComponent(key)}${query(opts)}`, undefined, h),
    project: (spec, opts, h) => new Session(`/ws/project${query(opts)}`, spec, h),
    ingest: (repo, commit, opts, h) => new Session(`/ws/project${query(opts)}`, { ingest_repo: repo, commit_hash: commit }, h),
    demo: (payload, opts, h) => new Session(`/ws/demo${query(opts)}`, payload, h),
    binary: (payload, opts, h) => new Session(`/ws/binary${query(opts)}`, payload, h)
  };

  async function mcpSnippet(args) {
    const r = await fetch('/mcp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: Date.now(), method: 'tools/call', params: { name: 'submit_code_snippet', arguments: args } })
    });
    const data = await r.json();
    if (data.error) throw new Error(data.error.message || 'MCP call failed.');
    return data.result && data.result.structuredContent ? data.result.structuredContent : data.result;
  }

  function download(name, data, type = 'application/json') {
    const blob = new Blob([typeof data === 'string' ? data : JSON.stringify(data, null, 2)], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function bytesToB64(buf) {
    const bytes = new Uint8Array(buf);
    let bin = '';
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(bin);
  }

  SMS.link = { probe, open, mcpSnippet, download, bytesToB64, query, SAMPLE_TARGETS, SHOWCASE_TARGETS, Session };
})();
