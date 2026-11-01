// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · visualizer test bench — the visual system alone, driven by simulated
// events. Nothing here talks to a backend. Use it to tune visuals and to check
// how the map handles bursts, long silences, probes, patches and verdicts.
'use strict';
(() => {
  const SMS = window.SMS;
  const { h, CommsFeed, StageBar, Terminal, HoverCard, StreamMeter, ExplainToggle, Explainer, MapKey, lensBadge, counter, elapsed, scramble } = SMS.hud;
  const N = SMS.narrator;
  const Ls = SMS.lenses;
  const P = SMS.palette;
  const $ = (id) => document.getElementById(id);

  const graph = new SMS.SpiderGraph($('graph'), { mode: 'demo' });
  const interp = new SMS.Interpreter(graph);
  const comms = new CommsFeed($('comms'), { emptyText: 'Simulated messages appear here.' });
  const stagebar = new StageBar($('stagebar'));
  const term = new Terminal($('term'), { prompt: 'sim@sandbox:~$' });
  const meter = new StreamMeter($('meter'), { label: 'sim', stallMs: 15000 });
  new HoverCard($('hovercard'), graph, $('stage'));
  const explainer = new Explainer($('explain'));
  const mapkey = new MapKey($('mapkey'));
  new ExplainToggle($('ex-toggle'), { page: 'visualizer', def: 'both' });

  // One or more scenarios per lens (core/lenses.js). ?lens=repo or ?scenario=<key> preselects.
  const SCENARIOS = [
    { key: 'node_query_sink', label: 'JS · SQLi', lens: 'file' },
    { key: 'php_command_sink', label: 'PHP · cmd', lens: 'file' },
    { key: 'mysql_insecure_conf', label: 'my.cnf', lens: 'file' },
    { key: 'greenhouse', label: 'Grow', lens: 'file' },
    { key: 'repo_notes_app', label: 'Notes app', lens: 'repo' },
    { key: 'binary_argv_echo', label: 'ELF · fmt', lens: 'binary' },
    { key: 'system_shop_stack', label: 'Shop stack', lens: 'system' }
  ];
  const lensOf = (key) => (SCENARIOS.find((x) => x.key === key) || SCENARIOS[0]).lens;
  const SPEEDS = [0.5, 1, 2, 4];
  const qs = new URLSearchParams(location.search);
  const want = SCENARIOS.find((x) => x.key === qs.get('scenario')) || SCENARIOS.find((x) => x.lens === qs.get('lens'));
  const state = { key: want ? want.key : 'node_query_sink', story: {}, stage: '', speed: 1, replay: null, playing: false, msgs: 0, started: 0, topo: null, silentUntil: 0, loopTimer: 0 };

  function insets() {
    const L = document.querySelector('.d-left');
    const R = document.querySelector('.d-right');
    const vis = (el) => el && getComputedStyle(el).display !== 'none';
    graph.setInsets({
      l: vis(L) ? L.getBoundingClientRect().right + 6 : 0,
      r: vis(R) ? window.innerWidth - R.getBoundingClientRect().left + 6 : 0,
      t: document.querySelector('.d-top').getBoundingClientRect().bottom + 4,
      b: window.innerHeight - document.querySelector('.d-caption').getBoundingClientRect().top + 4
    });
  }
  window.addEventListener('resize', insets);

  function seg(root, items, current, onPick) {
    root.replaceChildren();
    items.forEach((it) => {
      const b = h('button', null, it.label, { type: 'button', role: 'radio', 'aria-checked': String(it.v === current) });
      b.addEventListener('click', () => { root.querySelectorAll('button').forEach((x) => x.setAttribute('aria-checked', String(x === b))); onPick(it.v); });
      root.append(b);
    });
  }

  function status(text, s) { $('v-status').textContent = text; $('v-status').dataset.s = s; }

  /* ---------- scenario ---------- */
  function load() {
    clearTimeout(state.loopTimer);
    if (state.replay) state.replay.stop();
    const grow = state.key === 'greenhouse';
    const key = grow ? 'node_query_sink' : state.key;
    state.topo = SMS.topology.profile(key, SMS.link.SAMPLE_TARGETS[key] || SMS.link.SHOWCASE_TARGETS[key] || {});
    interp.load(state.topo, { grow });
    state.story = N.context(state.topo, graph);
    lensBadge($('d-lens'), graph.lens);
    mapkey.setLens(graph.lens);
    explainer.set(N.intro(graph.lens, state.story));
    state.stage = '';
    comms.clear('Simulated messages appear here.');
    term.clear();
    stagebar.reset();
    state.msgs = 0;
    ['st-msgs'].forEach((id) => { $(id).dataset.v = '0'; $(id).textContent = '0'; });
    $('d-target').textContent = `${SCENARIOS.find((s) => s.key === state.key).label} scenario`;
    $('cap-tech').textContent = Ls.get(graph.lens).expert;
    const lines = SMS.scenario.script(key, state.topo, { grow });
    state.replay = new SMS.scenario.Replay(lines, Object.assign(SMS.scenario.result(key, state.topo), { replay: true }), {
      onLine: (team, msg) => line(team, msg),
      onResult: (p) => { interp.result(p); stagebar.finish(true); verdictCaption(p); },
      onClose: () => {
        state.playing = false;
        meter.close();
        status('done', 'done');
        $('v-play').textContent = '▶ Play';
        if ($('v-loop').checked) state.loopTimer = setTimeout(() => { load(); play(); }, 4000);
      }
    });
    state.replay.paused = true;
    state.replay.setSpeed(state.speed);
    state.started = Date.now();
    status('ready', 'paused');
    caption('Simulation', 'The visual system on its own.');
  }

  function play() {
    if (!state.replay || state.replay.done) load();
    state.playing = true;
    meter.open('sim');
    state.replay.resume();
    status('playing', 'playing');
    $('v-play').textContent = '❚❚ Pause';
  }
  function pause() {
    if (!state.replay) return;
    state.replay.pause();
    state.playing = false;
    status('paused', 'paused');
    $('v-play').textContent = '▶ Play';
  }

  function line(team, msg) {
    const ev = interp.line(team, msg, { ts: Date.now() });
    meter.tick();
    comms.add(ev);
    term.push(team, msg);
    state.msgs += 1;
    $('msg-count').textContent = `${state.msgs} msgs`;
    counter($('st-msgs'), state.msgs);
    explainer.set({ expert: `${ev.speaker}${ev.toLabel ? ` → ${ev.toLabel}` : ''}: ${ev.body || msg}` });
    const said = N.event(graph.lens, ev, state.story, interp);
    if (said) { explainer.set({ simple: said.simple }); $('cap-tech').textContent = said.expert; }
    return ev;
  }

  function caption(kicker, title) {
    $('cap-phase').textContent = kicker.toUpperCase();
    scramble($('cap-title'), title, 500);
  }
  function stageCaption(stage) {
    const m = P.STAGE_META[stage];
    if (!m) return;
    state.stage = stage;
    const said = N.stage(graph.lens, stage, state.story) || { simple: m.caption, expert: m.caption };
    caption(`Phase ${m.n} // ${m.label}`, SMS.explain.level === 'expert' ? m.caption : said.simple);
    $('cap-tech').textContent = said.expert;
  }
  function verdictCaption(p) {
    const v = N.verdict(graph.lens, p, state.story);
    caption('Verdict', p.status === 'verified' ? 'Boundary verified · purple lock' : 'Boundary still reachable');
    explainer.set(v);
  }
  interp.on('stage', (stage) => { stagebar.set(stage); stageCaption(stage); });
  SMS.explain.on((lv) => { graph.setExplain(lv); if (state.stage) stageCaption(state.stage); requestAnimationFrame(insets); });

  /* ---------- injections (simulated events through the real interpreter) ---------- */
  const sinkLabel = () => { const n = state.topo && state.topo.sinkId && graph.node(state.topo.sinkId); return n ? n.label : 'the sink'; };
  const rand = (a) => a[(Math.random() * a.length) | 0];
  const INJECT = [
    { label: 'Probe · exit 0', c: '#ff3b5c', run: () => { line('red', 'Proving the finding with a boundary probe.'); setTimeout(() => line('red', 'Breakwater: boundary check exited 0 — boundary reachable.'), 500); } },
    { label: 'Patch applied', c: '#38bdf8', run: () => { line('blue', `Requesting a sanitization patch for ${sinkLabel()}.`); setTimeout(() => line('blue', 'Stitch: bounded sanitation-only replacements applied (+3 −1).'), 600); } },
    { label: 'Re-probe · exit 1', c: '#b06cff', run: () => { line('system', 'Verifying a fresh target with the original probe.'); setTimeout(() => line('system', 'Arbiter: boundary check exited 1 — probe blocked.'), 600); } },
    { label: 'Intel CVE', c: '#facc15', run: () => line('research', `Almanac: advisory CVE-2026-${1000 + ((Math.random() * 8999) | 0)} matches this pattern (simulated).`) },
    { label: 'Discover file', c: '#cfe3ff', run: () => line('red', `Cartographer: found lib/${rand(['auth', 'upload', 'session', 'export', 'search'])}_${(Math.random() * 99) | 0}.js and ${rand(['parseToken', 'saveFile', 'buildQuery', 'render'])}().`) },
    { label: 'Discover port', c: '#f0abfc', run: () => line('red', `Cartographer: found ${rand(['8080', '9200', '2375', '11211'])}/tcp listening inside the snapshot.`) },
    { label: 'Green plants', c: '#34f5a2', run: () => line('green', 'Seedling: planted another route and its handler.') },
    { label: 'Burst ×20', c: '#fb923c', run: () => { for (let i = 0; i < 20; i += 1) setTimeout(() => { const a = rand(P.AGENTS); line(a.team === 'yellow' ? 'research' : a.team === 'orange' || a.team === 'purple' ? 'system' : a.team, `${a.id}: ${rand(['checking', 'tracing', 'reviewing', 'hashing', 'mapping', 'testing'])} ${rand(['input path', 'handler', 'guard', 'receipt', 'snapshot', 'route'])} #${i + 1}.`); }, i * 40); } },
    { label: 'Silence 20s', c: '#fb923c', run: () => { const was = state.playing; pause(); status('silent', 'silent'); state.silentUntil = Date.now() + 20000; setTimeout(() => { state.silentUntil = 0; if (was) play(); else status('paused', 'paused'); }, 20000); } },
    { label: 'Verdict · pass', c: '#b06cff', run: () => { const p = { status: 'verified', regression_passed: true, receipt: { patch_sha256: 'f'.repeat(64) } }; interp.result(p); stagebar.finish(true); verdictCaption(p); } },
    { label: 'Verdict · fail', c: '#ff3b5c', run: () => { const p = { status: 'failed', post_probe_exit: 0 }; interp.result(p); stagebar.finish(false); verdictCaption(p); } }
  ];
  INJECT.forEach((it) => {
    const b = h('button', 'btn sm', null, { type: 'button' });
    b.style.setProperty('--c', it.c);
    b.append(h('i', null, null, { 'aria-hidden': 'true' }), document.createTextNode(it.label));
    b.addEventListener('click', () => { if (!state.started) state.started = Date.now(); meter.state === 'closed' && meter.open('sim'); it.run(); });
    $('v-inject').append(b);
  });

  const LAYERS = [
    { label: 'Web', fn: (on) => graph.setLayer('web', on), on: true },
    { label: 'Flow', fn: (on) => graph.setLayer('flow', on), on: true },
    { label: 'Comms', fn: (on) => graph.setLayer('comms', on), on: true },
    { label: 'Sweep', fn: (on) => graph.setLayer('sweep', on), on: true },
    { label: 'All labels', fn: (on) => graph.setLayer('labels', on ? 'all' : 'auto'), on: false },
    { label: 'Director', fn: (on) => { graph.setDirector(on); if (on) graph.fit(); }, on: true }
  ];
  LAYERS.forEach((it) => {
    const b = h('button', 'btn sm', it.label, { type: 'button', 'aria-pressed': String(it.on) });
    b.addEventListener('click', () => { const on = b.getAttribute('aria-pressed') !== 'true'; b.setAttribute('aria-pressed', String(on)); it.fn(on); });
    $('v-layers').append(b);
  });

  function pickScenario(k) { state.key = k; const was = state.playing; load(); if (was) play(); }
  function renderScenarios() {
    const lens = lensOf(state.key);
    seg($('v-lens'), Ls.ORDER.map((l) => ({ v: l, label: Ls.get(l).label })), lens, (l) => { const first = SCENARIOS.find((x) => x.lens === l); renderScenarios.lens = l; pickScenario(first.key); renderScenarios(); });
    seg($('v-target'), SCENARIOS.filter((x) => x.lens === lens).map((x) => ({ v: x.key, label: x.label })), state.key, pickScenario);
  }
  renderScenarios();
  seg($('v-speed'), SPEEDS.map((s) => ({ v: s, label: `${s}×` })), state.speed, (s) => { state.speed = s; if (state.replay) state.replay.setSpeed(s); });

  $('v-play').addEventListener('click', () => (state.playing ? pause() : play()));
  $('v-step').addEventListener('click', () => { if (!state.replay || state.replay.done) load(); pause(); state.replay.step(); });
  $('v-restart').addEventListener('click', () => { load(); play(); });

  document.addEventListener('keydown', (e) => {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    const k = e.key.toLowerCase();
    if (k === ' ') { e.preventDefault(); $('v-play').click(); }
    if (k === 'arrowright') $('v-step').click();
    if (k === 'r') $('v-restart').click();
    if (k === 'escape') location.href = 'index.html';
  });

  // live engine stats
  let frames = 0;
  let last = performance.now();
  (function fps(t) { frames += 1; if (t - last > 1000) { $('st-fps').textContent = String(frames); frames = 0; last = t; } requestAnimationFrame(fps); })(last);
  setInterval(() => {
    const now = performance.now();
    $('st-nodes').textContent = String(graph.nodes.size);
    $('st-fly').textContent = String(graph.packets.filter((p) => now >= p.born && now - p.born < p.dur).length);
    $('st-part').textContent = String(graph.particles.length);
    if (state.started) $('clock').textContent = elapsed(Date.now() - state.started);
    if (state.silentUntil) status(`silent ${Math.ceil((state.silentUntil - Date.now()) / 1000)}s`, 'silent');
  }, 250);

  insets();
  load();
  play();
})();
