// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · production visual page. Reads the run compiled on prod-setup.html
// (js/core/handoff.js), starts it on arrival and renders the real-time stream:
// live map, comms, activity, inspector, results, history. No configuration here.
'use strict';
(() => {
  const SMS = window.SMS;
  const { h, CommsFeed, Legend, StageBar, HoverCard, StreamMeter, ExplainToggle, Explainer, MapKey, lensBadge, counter, toast, elapsed } = SMS.hud;
  const N = SMS.narrator;
  const P = SMS.palette;
  const L = SMS.launch;
  const $ = (id) => document.getElementById(id);

  const V = SMS.views;

  const graph = new SMS.SpiderGraph($('graph'), { mode: 'console' });
  const interp = new SMS.Interpreter(graph);
  const comms = new CommsFeed($('comms'), { emptyText: 'Messages between agents land here and fly across the map as bubbles.' });
  const legend = new Legend($('legend'), graph, { compact: true, onFilter: (set) => comms.setFilter(set) });
  const stagebar = new StageBar($('stagebar'), { onPick: (s) => setStageFilter(state.stageFilter === s ? '' : s) });
  const meter = new StreamMeter($('meter'), { label: 'stream' });
  const activity = new V.ActivityLog($('log'));
  const timeline = new V.Timeline($('timeline'), { onPick: (ev) => { showTab('log'); activity.reveal(ev.seq); } });
  new HoverCard($('hovercard'), graph, $('map'));
  // Production defaults to Expert; Simple / Both are one click (or E) away for stakeholders.
  const explainer = new Explainer($('explain'));
  const mapkey = new MapKey($('mapkey'), { compact: true });
  new ExplainToggle($('ex-toggle'), { page: 'console', def: 'expert' });
  SMS.explain.on((lv) => graph.setExplain(lv));

  const state = {
    link: null, ready: false, mode: 'fixture', fixture: null, targets: SMS.link.SAMPLE_TARGETS,
    session: null, replay: null, running: false, started: 0, timer: 0, result: null,
    events: [], stageFilter: '', topo: null, binary: null, launch: null, buf: null
  };

  /* ================= launch ================= */
  function setProvenance(topo) {
    const kind = (topo && topo.provenance) || 'modelled';
    $('prov').dataset.kind = kind;
    $('prov-kind').textContent = kind;
    $('prov-text').textContent = kind === 'parsed'
      ? (state.mode === 'binary' ? 'from ELF headers, sections and symbol tables · call edges inferred' : state.mode === 'system' ? 'from the services list · hosts, ports, doors, datastores' : 'from the pasted source · functions, routes, inputs, sinks')
      : state.mode === 'fixture' ? 'from the fixture profile · files and symbols named in the stream are added live' : 'skeleton · files and symbols named in the stream are added live';
    $('prov').title = `${kind}: ${$('prov-text').textContent}`;
  }

  function renderRail(launch) {
    $('r-target').textContent = launch.title || launch.fixture || launch.mode;
    const k = $('rail-kind');
    k.dataset.kind = launch.kind;
    k.textContent = launch.kind === 'fake' ? 'fake run · scripted' : 'live · real time';
    const dl = $('r-sum');
    dl.replaceChildren();
    (launch.summary || []).forEach(([a, b]) => dl.append(h('dt', null, a), h('dd', null, b)));
    if (launch.request) dl.append(h('dt', null, 'Endpoint'), h('dd', null, launch.request.mcp ? 'POST /mcp' : launch.request.path));
  }

  /* ================= run lifecycle ================= */
  function errors(list) {
    $('cfg-errors').hidden = !list.length;
    $('cfg-errors').textContent = list.join(' ');
    return list.length === 0;
  }

  function resetRun() {
    state.events = [];
    state.result = null;
    comms.clear();
    legend.reset();
    stagebar.reset();
    activity.reset();
    timeline.reset();
    ['sc-msgs', 'sc-find', 'sc-patch', 'sc-ver'].forEach((id) => { $(id).dataset.v = '0'; $(id).textContent = '0'; });
    $('b-comms').textContent = '0';
    $('b-log').textContent = '0';
    $('b-result').hidden = true;
    $('result').hidden = true;
    $('result-empty').hidden = false;
    setStageFilter('');
  }

  function lock(on) {
    state.running = on;
    $('stop').hidden = !on;
    $('stop').disabled = false;
    $('again').hidden = on;
    runChip(on ? 'Running' : 'Idle', on ? 'ok' : 'pending');
    clearInterval(state.timer);
    if (on) {
      state.started = Date.now();
      $('sc-time').textContent = '00:00';
      state.timer = setInterval(() => { $('sc-time').textContent = elapsed(Date.now() - state.started); }, 500);
    }
  }
  function runChip(text, st) { const c = $('chip-run'); c.dataset.state = st; c.lastChild.textContent = text; }

  function handlers(label) {
    return {
      onOpen: () => meter.open(label === 'fake' ? 'fake run' : 'stream'),
      onLine: (team, msg, payload) => onLine(team, msg, payload),
      onResult: (p) => onResult(p, label),
      onGraph: (p) => onGraph(p),
      onRefuse: (type, msg) => {
        const text = type === 'busy' ? 'Scan refused: another scan holds the server lock. Wait for it to finish, then run again.' : `${msg || 'Invalid request.'} Fix the highlighted fields, then run again.`;
        onLine('system', text);
        errors([text]);
        toast(type === 'busy' ? 'Server busy' : 'Request rejected');
      },
      onError: () => onLine('system', 'Connection hiccup during verification — the scan keeps running on the server.'),
      onClose: (info) => onClose(info)
    };
  }

  function begin(topo, o = {}) {
    resetRun();
    if (topo) {
      state.topo = topo;
      interp.load(topo, { grow: !!o.grow });
      setProvenance(topo);
      state.story = N.context(topo, graph);
      lensBadge($('c-lens'), graph.lens);
      mapkey.setLens(graph.lens);
      explainer.set(N.intro(graph.lens, state.story));
    }
    graph.setDirector($('t-dir').getAttribute('aria-pressed') === 'true');
    lock(true);
    counter($('sc-nodes'), graph.nodes.size);
  }

  // Start the launched run. Live: open the compiled request. Fake: scripted events.
  async function start() {
    const launch = state.launch;
    if (state.running || !launch) return;
    errors([]);
    const { topo, buf } = await L.topology(launch);
    state.buf = buf;
    begin(topo, { grow: !!launch.grow });
    if (launch.kind === 'fake') {
      runChip('Fake run', 'replay');
      meter.open('fake run');
      const key = launch.fixture || 'node_query_sink';
      state.replay = new SMS.scenario.Replay(SMS.scenario.script(key, topo, { grow: !!launch.grow }), SMS.scenario.result(key, topo), handlers('fake')).start();
      return;
    }
    const req = launch.request;
    if (req.mcp) { runSnippet(req.body); return; }
    let body = req.body;
    if (req.binary) {
      if (!buf) { errors(['The binary is no longer available in this browser — pick it again on the setup screen.']); lock(false); return; }
      body = Object.assign({}, body, { blob_b64: SMS.link.bytesToB64(buf) });
    }
    try {
      meter.open('stream');
      state.session = new SMS.link.Session(req.path, body, handlers('live'));
      const v = launch.values || {};
      if (launch.mode === 'project' || launch.mode === 'build') onLine('system', `Run accepted · ${v.scan_profile} · ${body.cycles} cycle${body.cycles === 1 ? '' : 's'} · ${body.red_agents} red / ${body.blue_agents} blue · ${Number(body.context_budget).toLocaleString()} token budget.`);
      if (launch.mode === 'build') onLine('green', 'Greenhouse is growing a fresh demo. Stand by for seedlings.');
      if (launch.mode === 'ingest') onLine('ingest', `Courier: repo ingest → ${body.ingest_repo} @ ${String(body.commit_hash).slice(0, 12)}`);
      if (launch.mode === 'binary') onLine('system', `Binary sweep → ${body.filename} (${buf.byteLength} bytes) · harness staging.`);
    } catch (e) {
      errors([e.message]);
      lock(false);
    }
  }

  async function runSnippet(args) {
    $('stop').hidden = true;
    meter.open('mcp');
    onLine('system', `MCP submit_code_snippet → ${args.filename} (${args.language}) · waiting for the verdict.`);
    try {
      const r = await SMS.link.mcpSnippet(args);
      onLine('red', `Boundary check exited ${r.pre_probe_exit} on the original snippet.`);
      if (r.post_probe_exit !== undefined && r.post_probe_exit !== null) onLine('system', `Verifying a fresh target with the original probe · boundary check exited ${r.post_probe_exit}.`);
      onResult(Object.assign({ type: 'result', target: args.filename, message: `MCP result: status=${r.status} pre=${r.pre_probe_exit} post=${r.post_probe_exit}` }, r), 'live');
    } catch (e) {
      onLine('system', `Snippet verification failed: ${e.message}`);
      errors([`Snippet verification failed: ${e.message}`]);
    } finally {
      onClose({});
    }
  }

  function stop() {
    if (state.session) { state.session.stop(); $('stop').disabled = true; runChip('Stopping', 'warn'); }
    if (state.replay) { state.replay.stop(); state.replay = null; onClose({ cancelled: true }); }
  }

  /* ================= stream handlers ================= */
  function onGraph(p) {
    // Optional server topology: { type: 'graph', nodes: [{id,label,kind,parent}], links: [...] }
    (p.nodes || []).forEach((n) => graph.addNode(n));
    (p.links || []).forEach((l) => graph.link(l.source, l.target, l.kind || 'call'));
    $('prov').dataset.kind = 'parsed';
    $('prov-kind').textContent = 'server';
    $('prov-text').textContent = 'topology streamed by the orchestrator';
  }

  function onLine(team, msg, payload) {
    const ev = interp.line(team, msg, payload);
    meter.tick();
    state.events.push(ev);
    if (state.events.length > 2000) state.events.shift();
    comms.add(ev);
    activity.add(ev);
    timeline.add(ev);
    $('b-comms').textContent = String(state.events.length);
    $('b-log').textContent = String(state.events.length);
    counter($('sc-msgs'), state.events.length);
    counter($('sc-nodes'), graph.nodes.size);
    counter($('sc-find'), interp.stats.findings);
    counter($('sc-patch'), interp.stats.patches);
    if (/rate limit|429/i.test(msg) || /docker daemon/i.test(msg)) errors([msg]);
    if (graph.selected) inspect(graph.describe(graph.selected));
    const said = N.event(graph.lens, ev, state.story || {}, interp);
    if (said) explainer.set(said);
  }
  interp.on('stage', (st) => { const said = N.stage(graph.lens, st, state.story || {}); if (said) explainer.set(said); });

  function setStageFilter(s) {
    state.stageFilter = s;
    stagebar.inspect(s);
    activity.setStage(s);
    $('stage-filter-note').hidden = !s;
    $('stage-filter-note').textContent = s ? `Showing ${P.STAGE_META[s].label} events only · click the phase again to clear` : '';
    if (s) showTab('log');
  }
  document.querySelectorAll('[data-f]').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('[data-f]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    activity.setTeam(b.dataset.f);
  }));
  $('copy-log').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(activity.visibleText()); toast('Activity copied'); } catch { toast('Clipboard unavailable'); }
  });

  function onResult(p, source) {
    state.result = Object.assign({}, p, source === 'fake' ? { replay: true } : {});
    interp.result(p);
    explainer.set(N.verdict(graph.lens, p, state.story || {}));
    stagebar.finish(SMS.OK_STATUSES.includes(p.status));
    counter($('sc-ver'), interp.stats.verified);
    V.renderResult(state.result, { source, started: state.started });
    history.save(state.result, { source, mode: state.mode, target: state.fixture });
    $('b-result').hidden = false;
    showTab('result');
  }

  function onClose(info) {
    lock(false);
    meter.close();
    graph.setWorking(null);
    state.session = null;
    state.replay = null;
    if (!state.result) {
      if (info && info.cancelled) { runChip('Stopped', 'warn'); toast('Scan stopped — nothing was applied'); }
      else if (info && (info.reason === 'busy' || info.reason === 'invalid')) runChip('Refused', 'error');
      else if (info && info.reason === undefined && state.mode !== 'snippet') { runChip('Disconnected', 'error'); onLine('system', 'Lost connection to the server before a result arrived. Cleanup on the server finishes on its own.'); }
    } else runChip(state.result.replay ? 'Fake run done' : 'Done', SMS.OK_STATUSES.includes(state.result.status) ? 'ok' : 'error');
  }

  /* ================= result downloads ================= */
  const NOTICE = { notice: 'Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.', license_url: 'https://polyformproject.org/licenses/noncommercial/1.0.0' };
  const tag = () => (state.result && (state.result.target || state.result.project)) || 'scan';
  const diffOf = () => state.result && (state.result.diff || state.result.cumulative_diff);
  $('dl-json').addEventListener('click', () => { if (state.result) SMS.link.download(`sms-${tag()}-report.json`, Object.assign({}, NOTICE, state.result)); });
  $('dl-receipt').addEventListener('click', () => { const r = state.result && V.summarize(state.result).receipt; if (r) SMS.link.download(`verdict-receipt-${tag()}.json`, Object.assign({}, NOTICE, { receipt: r })); });
  $('dl-patch').addEventListener('click', () => { const d = diffOf(); if (d) SMS.link.download(`candidate-${tag()}.patch`, d, 'text/x-diff;charset=utf-8'); });
  $('cp-diff').addEventListener('click', async () => { try { await navigator.clipboard.writeText(diffOf()); toast('Diff copied'); } catch { toast('Clipboard unavailable'); } });

  /* ================= inspector + history ================= */
  const inspect = (d) => V.renderInspect($('inspect'), d, { events: state.events, topo: state.topo });
  graph.on('select', (d) => { inspect(d); if (d) showTab('inspect'); });
  const history = new V.RunHistory($('history'), { onOpen: (payload, fake) => { state.result = payload; V.renderResult(payload, { source: fake ? 'fake' : 'live' }); showTab('result'); } });

  /* ================= tabs / tools ================= */
  function showTab(name) {
    ['inspect', 'comms', 'log', 'result'].forEach((t) => {
      $(`tab-${t}`).setAttribute('aria-selected', String(t === name));
      $(`pane-${t}`).hidden = t !== name;
    });
  }
  ['inspect', 'comms', 'log', 'result'].forEach((t) => $(`tab-${t}`).addEventListener('click', () => showTab(t)));

  const toggle = (id, fn) => $(id).addEventListener('click', (e) => { const on = e.currentTarget.getAttribute('aria-pressed') !== 'true'; e.currentTarget.setAttribute('aria-pressed', String(on)); fn(on); });
  $('t-fit').addEventListener('click', () => graph.fit());
  toggle('t-dir', (on) => graph.setDirector(on));
  toggle('t-labels', (on) => graph.setLayer('labels', on ? 'all' : 'auto'));
  toggle('t-flow', (on) => graph.setLayer('flow', on));
  toggle('t-comms', (on) => graph.setLayer('comms', on));
  toggle('t-sweep', (on) => graph.setLayer('sweep', on));
  $('t-png').addEventListener('click', () => {
    const c = $('graph');
    const out = document.createElement('canvas');
    out.width = c.width; out.height = c.height;
    const x = out.getContext('2d');
    x.fillStyle = '#02050a'; x.fillRect(0, 0, out.width, out.height);
    x.drawImage(c, 0, 0);
    const a = document.createElement('a');
    a.href = out.toDataURL('image/png');
    a.download = `sms-map-${Date.now()}.png`;
    a.click();
  });

  $('stop').addEventListener('click', stop);
  $('again').addEventListener('click', () => start());
  document.addEventListener('keydown', (e) => {
    const tagName = (e.target.tagName || '').toLowerCase();
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !state.running) { e.preventDefault(); start(); return; }
    if (tagName === 'input' || tagName === 'textarea' || tagName === 'select') return;
    if (e.key === 'Escape') { if (state.running) stop(); else { graph.select(null); setStageFilter(''); } }
    if (e.key === '0') graph.fit();
  });

  function chip(id, st, text) { const c = $(id); c.dataset.state = st; if (text) c.lastChild.textContent = text; }

  /* ================= boot ================= */
  inspect(null);
  state.launch = L.load();
  if (!state.launch || state.launch.page !== 'console') { location.replace('prod-setup.html'); return; }
  state.mode = state.launch.mode || 'fixture';
  state.fixture = state.launch.fixture;
  renderRail(state.launch);
  if (state.launch.kind === 'fake') {
    ['chip-server', 'chip-docker', 'chip-key'].forEach((id) => chip(id, 'pending', id === 'chip-server' ? 'No backend' : id === 'chip-docker' ? 'Docker —' : 'Muse —'));
    start();
  } else {
    SMS.link.probe().then((link) => {
      chip('chip-server', link.online ? 'ok' : 'error', link.online ? 'Orchestrator' : 'Offline');
      chip('chip-docker', !link.online ? 'pending' : link.docker === 'ready' ? 'ok' : 'error', !link.online ? 'Docker ?' : { ready: 'Docker', images_missing: 'Images missing', unavailable: 'Docker offline' }[link.docker] || 'Docker');
      chip('chip-key', !link.online ? 'pending' : link.keyOk ? 'ok' : 'warn', link.inferenceMode === 'local' ? 'Local inference' : link.keyOk ? 'Muse' : 'No API key');
      if (!link.ready) {
        $('setup').hidden = false;
        $('setup').textContent = `${link.notes.join(' ')} The run was not started. Fix the setup and press Run again, or go back to choose a fake run.`;
        $('again').hidden = false;
        return;
      }
      start();
    });
  }
})();
