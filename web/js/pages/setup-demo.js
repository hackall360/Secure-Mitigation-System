// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · demo selection screen — target, event source, lighter run settings.
// Start hands the run to demo.html, which begins on arrival.
'use strict';
(() => {
  const SMS = window.SMS;
  const { h, HoverCard, MapKey, lensBadge } = SMS.hud;
  const Ls = SMS.lenses;
  const O = SMS.options;
  const L = SMS.launch;
  const P = SMS.palette;
  const $ = (id) => document.getElementById(id);

  const TARGET_BADGE = { node_query_sink: ['JS', '#facc15'], php_command_sink: ['PHP', '#b06cff'], mysql_insecure_conf: ['SQL', '#38bdf8'], binary_argv_echo: ['ELF', '#ff3b5c'], greenhouse: ['GROW', '#34f5a2'], repo_notes_app: ['REPO', '#22d3ee'], system_shop_stack: ['SYS', '#f0abfc'] };
  const GREENHOUSE = { title: 'Greenhouse build', filename: 'grown on demand', description: 'Green grows a fresh vulnerable app node by node, then red and blue fight over it.' };
  // Lighter fixed sizing for demo runs; production tunes these on its own setup screen.
  const DEMO_FIXED = { cycles: 1, red_agents: 5, blue_agents: 5, context_budget: 32768, build_offline: true, allow_remote_build: false, theme: '' };

  $('ver').textContent = `v${L.VERSION.version}`;
  const graph = new SMS.SpiderGraph($('graph'), { mode: 'demo' });
  const interp = new SMS.Interpreter(graph);
  new HoverCard($('hovercard'), graph, $('map'));
  const pvKey = new MapKey($('pv-key'), { compact: true });
  document.body.dataset.explain = 'both';

  const state = { link: null, targets: SMS.link.SAMPLE_TARGETS, key: localStorage.getItem('sms.v3.demo.key') || null, source: 'fake' };
  const ctx = { page: 'demo', scanProfiles: [], models: [], defaultModel: '', source: 'fixture' };
  const runOpts = new O.OptionForm($('demo-opts'), { keys: ['scan_profile', 'sweep_passes', 'research', 'profile'], ctx, storageKey: 'sms.v3.demo.run', onChange: refresh });
  const buildOpts = new O.OptionForm($('demo-build-opts'), { keys: ['build_brief', 'vulns', 'demo_size', 'flaw_count'], ctx: { page: 'demo', source: 'build' }, storageKey: 'sms.v3.demo.build', onChange: refresh });

  const grow = () => state.key === 'greenhouse';
  const info = (key) => (key === 'greenhouse' ? GREENHOUSE : state.targets[key] || SMS.link.SAMPLE_TARGETS[key] || SMS.link.SHOWCASE_TARGETS[key] || { title: key, filename: key });
  // Showcase targets (one per lens) run as fake runs unless the orchestrator lists the same key.
  const showcase = () => Object.assign({ binary_argv_echo: Object.assign({}, SMS.link.SAMPLE_TARGETS.binary_argv_echo, { lens: 'binary', showcase: true }) }, SMS.link.SHOWCASE_TARGETS);
  const liveOk = (key) => key === 'greenhouse' || (!!state.targets[key] && key !== 'binary_argv_echo');
  const lensOf = (key) => (key === 'greenhouse' ? 'file' : (info(key).lens || Ls.of(SMS.topology.profile(key, info(key)))));

  function request() {
    const v = Object.assign({}, DEMO_FIXED, buildOpts.values(), runOpts.values());
    const cyc = (O.MODES.find((m) => m.v === v.scan_profile) || {}).cycles;
    if (cyc) v.cycles = Math.min(cyc, 3);
    if (grow() && !String(v.build_brief || '').trim()) v.build_brief = 'a tiny note-taking web app with login';
    if (grow() && !String(v.vulns || '').trim()) v.vulns = 'SQL injection';
    return { req: O.compile(grow() ? 'build' : 'fixture', v, { fixture: state.key, inferenceMode: state.link && state.link.inferenceMode }), v };
  }

  function summary() {
    const { v } = request();
    const t = info(state.key);
    const mode = O.MODES.find((m) => m.v === v.scan_profile);
    return [['Target', t.title], ['File', t.filename || '—'], ['Source', state.source === 'live' ? 'Live orchestrator · real time' : 'Fake run · scripted'], ['Mode', grow() ? `${mode ? mode.l : v.scan_profile} · ${v.cycles} cycle${v.cycles === 1 ? '' : 's'}` : 'server defaults'], ['Sweep', `${v.sweep_passes} pass${v.sweep_passes === 1 ? '' : 'es'}`], ['Intel', v.research ? 'on' : 'off']];
  }

  function refresh() {
    $('demo-build-opts').hidden = !grow();
    runOpts.setContext({ source: grow() ? 'build' : 'fixture' });
    const { req } = request();
    $('req').textContent = state.source === 'fake' ? 'Fake run — nothing is sent. The visual page plays scripted events.' : `WS ${req.path}\n${req.body ? JSON.stringify(req.body, null, 2) : '(no body — fixture runs use the server defaults for cycles and agents)'}`;
    const dl = $('summary');
    dl.replaceChildren();
    summary().forEach(([k, val]) => dl.append(h('dt', null, k), h('dd', null, val)));
    $('launch').textContent = state.source === 'live' ? 'Start live demo →' : 'Start fake run →';
  }

  function renderTargets() {
    const root = $('targets');
    root.replaceChildren();
    const extra = Object.entries(showcase()).filter(([k]) => !state.targets[k] || k === 'binary_argv_echo');
    const entries = Object.entries(state.targets).filter(([k]) => k !== 'binary_argv_echo').concat([['greenhouse', GREENHOUSE]], extra)
      .sort((a, b) => Ls.ORDER.indexOf(lensOf(a[0])) - Ls.ORDER.indexOf(lensOf(b[0])));
    entries.forEach(([key, t], i) => {
      const [badge, col] = TARGET_BADGE[key] || [String(i + 1), '#2dd4bf'];
      const card = h('button', 's-tcard', null, { type: 'button', role: 'radio', 'aria-checked': 'false' });
      card.dataset.key = key;
      card.dataset.lens = lensOf(key);
      card.style.setProperty('--tc', col);
      const lens = h('span', 'tl');
      lensBadge(lens, lensOf(key));
      card.append(h('span', 'tb', badge), h('kbd', null, String(i + 1)), h('strong', null, t.title || key), h('code', null, t.filename || ''), lens, h('small', null, t.description || ''));
      if (!liveOk(key)) { card.dataset.fakeOnly = 'true'; card.append(h('em', 'tfake', 'fake run only — no backend fixture yet')); }
      card.addEventListener('click', () => pick(key));
      card.addEventListener('dblclick', () => { pick(key); start(); });
      root.append(card);
    });
    if (!state.key || !entries.some(([k]) => k === state.key)) state.key = entries[0][0];
    pick(state.key);
  }

  function pick(key) {
    state.key = key;
    localStorage.setItem('sms.v3.demo.key', key);
    document.querySelectorAll('.s-tcard').forEach((c) => c.setAttribute('aria-checked', String(c.dataset.key === key)));
    const topo = SMS.topology.profile(grow() ? 'node_query_sink' : key, info(key));
    interp.load(topo, { grow: grow() });
    lensBadge($('pv-lens'), graph.lens);
    pvKey.setLens(graph.lens);
    $('pv-kind').textContent = info(key).title;
    $('pv-text').textContent = grow() ? 'skeleton — Greenhouse grows the rest live' : 'modelled profile — the live stream adds what it names';
    refresh();
  }

  function setSource(src) {
    if (src === 'live' && !(state.link && state.link.ready)) return;
    state.source = src;
    document.body.dataset.src = src;
    if (src === 'live' && !liveOk(state.key)) { const first = [...document.querySelectorAll('.s-tcard')].find((c) => liveOk(c.dataset.key)); if (first) pick(first.dataset.key); }
    ['live', 'fake'].forEach((s) => $(`src-${s}`).setAttribute('aria-checked', String(s === src)));
    refresh();
  }
  $('src-live').addEventListener('click', () => setSource('live'));
  $('src-fake').addEventListener('click', () => setSource('fake'));

  function start() {
    if (state.source === 'live' && !liveOk(state.key)) { SMS.hud.toast('This showcase target has no backend fixture yet — switch to Fake run'); return; }
    const { req, v } = request();
    const t = info(state.key);
    L.save({
      page: 'demo', kind: state.source, key: state.key, fixture: grow() ? 'node_query_sink' : state.key, mode: grow() ? 'build' : 'fixture',
      title: t.title, filename: grow() ? 'app.js' : t.filename,
      request: { path: req.path, body: req.body },
      topo: { type: 'profile', key: grow() ? 'node_query_sink' : state.key, target: grow() ? { filename: 'app.js' } : t },
      grow: grow(), values: v, summary: summary()
    });
    location.href = 'demo.html';
  }
  $('launch').addEventListener('click', start);

  document.addEventListener('keydown', (e) => {
    if (e.altKey || e.ctrlKey || e.metaKey || /input|textarea|select/i.test(e.target.tagName)) return;
    if (e.key === 'Enter') { e.preventDefault(); start(); return; }
    if (e.key === 'Escape') { location.href = 'index.html'; return; }
    const n = Number.parseInt(e.key, 10);
    const cards = [...document.querySelectorAll('.s-tcard')];
    if (n >= 1 && n <= cards.length) pick(cards[n - 1].dataset.key);
  });

  // ambient motion on the preview
  setInterval(() => {
    if (document.hidden) return;
    const a = P.AGENTS[(Math.random() * P.AGENTS.length) | 0];
    const ids = [...graph.nodes.keys()];
    graph.send(a.id, ids[(Math.random() * ids.length) | 0], { label: '', dur: 1700 });
  }, 900);

  renderTargets();
  SMS.link.probe().then((link) => {
    state.link = link;
    state.targets = link.targets || SMS.link.SAMPLE_TARGETS;
    if (link.health) {
      Object.assign(ctx, { scanProfiles: link.health.scan_profiles || [], models: link.health.profiles || [], defaultModel: link.health.default_profile || ((link.health.profiles || [])[0] || {}).key || '' });
      runOpts.setContext(ctx);
    }
    renderTargets();
    $('src-live').disabled = !link.ready;
    const c = $('orch');
    c.dataset.state = link.ready ? 'ok' : link.online ? 'warn' : 'error';
    c.lastChild.textContent = link.ready ? 'Orchestrator ready' : link.online ? 'Orchestrator not ready' : 'Orchestrator offline';
    setSource(link.ready ? 'live' : 'fake');
    $('launch-note').textContent = link.ready ? 'Orchestrator ready. Live demos stream in real time from real sandboxes.' : `${link.notes.join(' ')} Fake run previews the visuals.`;
  });
})();
