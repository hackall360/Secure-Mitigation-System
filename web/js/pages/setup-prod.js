// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · production selection screen — source, target, operational mode, run controls,
// live topology preview and the exact request. Launch hands the run to console.html.
'use strict';
(() => {
  const SMS = window.SMS;
  const { h, HoverCard, MapKey, lensBadge, toast } = SMS.hud;
  const O = SMS.options;
  const L = SMS.launch;
  const $ = (id) => document.getElementById(id);

  const BADGES = { node_query_sink: ['JS', '#facc15'], php_command_sink: ['PHP', '#b06cff'], mysql_insecure_conf: ['SQL', '#38bdf8'], binary_argv_echo: ['ELF', '#ff3b5c'], repo_notes_app: ['REPO', '#22d3ee'], system_shop_stack: ['SYS', '#f0abfc'] };
  const TARGET_TITLE = { fixture: 'Choose a fixture', build: 'Describe the demo to grow', project: 'Point at a local repository', snippet: 'Paste the code', binary: 'Choose a compiled binary', ingest: 'Repository, HEAD or pinned commit', system: 'Describe the snapshot to clone' };
  const LAUNCH_LABEL = { fixture: 'Launch fixture run →', build: 'Grow and verify →', project: 'Launch project run →', snippet: 'Verify snippet →', binary: 'Sweep binary →', ingest: 'Ingest and verify →', system: 'Clone and verify →' };

  $('ver').textContent = `v${L.VERSION.version}`;
  const graph = new SMS.SpiderGraph($('graph'), { mode: 'console' });
  const interp = new SMS.Interpreter(graph);
  new HoverCard($('hovercard'), graph, $('map'));
  const pvKey = new MapKey($('pv-key'), { compact: true });
  document.body.dataset.explain = 'both';

  const state = { ready: false, mode: localStorage.getItem('sms.v3.prod.mode') || 'fixture', fixture: localStorage.getItem('sms.v3.prod.fixture') || null, targets: SMS.link.SAMPLE_TARGETS, topo: null, binary: null, inferenceMode: 'hosted', ctx: { page: 'console', scanProfiles: [], models: [], defaultModel: '' } };

  /* ---------- forms ---------- */
  const srcForms = {};
  function srcForm(mode) {
    if (!srcForms[mode]) {
      const host = h('div', 'opts');
      srcForms[mode] = new O.OptionForm(host, { keys: O.SOURCES[mode].fields, ctx: Object.assign({}, state.ctx, { source: mode, inferenceMode: state.inferenceMode }), storageKey: `sms.v3.src.${mode}`, onChange: (k, v) => onSourceChange(mode, k, v) });
      srcForms[mode].host = host;
    }
    return srcForms[mode];
  }
  const runForm = new O.OptionForm($('run-opts'), { keys: O.RUN, ctx: Object.assign({}, state.ctx, { source: state.mode }), storageKey: 'sms.v3.run', onChange: () => refresh() });
  const propForm = new O.OptionForm($('prop-opts'), { keys: O.PROPOSED, ctx: { page: 'console' }, storageKey: 'sms.v3.prop', onChange: () => refresh() });
  $('send-prop').checked = localStorage.getItem('sms.v3.sendProposed') === '1';
  $('send-prop').addEventListener('change', () => { localStorage.setItem('sms.v3.sendProposed', $('send-prop').checked ? '1' : '0'); refresh(); });
  $('run-reset').addEventListener('click', () => { Object.entries(O.defaults(O.RUN, state.ctx)).forEach(([k, v]) => runForm.set(k, v, true)); refresh(); toast('Run controls reset'); });

  const values = () => Object.assign({}, srcForm(state.mode).values(), runForm.values(), propForm.values());
  const compile = () => O.compile(state.mode, values(), { fixture: state.fixture, sendProposed: $('send-prop').checked, inferenceMode: state.inferenceMode });

  function refresh() {
    const r = compile();
    const pre = $('req');
    pre.replaceChildren();
    const line = (k, v) => pre.append(h('span', 'rk', k), document.createTextNode(` ${v}\n`));
    line(r.endpoint.startsWith('POST') ? '' : 'WS', r.path);
    if (r.body !== undefined) {
      const shown = Object.assign({}, r.body);
      if (shown.source && shown.source.length > 160) shown.source = `${shown.source.slice(0, 160)}… (${shown.source.length} chars)`;
      line('body', JSON.stringify(shown, null, 2));
    } else line('body', '(none — this endpoint streams without a request body)');
    const v = values();
    const sum = $('summary');
    sum.replaceChildren();
    const mode = O.MODES.find((m) => m.v === v.scan_profile);
    const rows = [['Source', O.SOURCES[state.mode].label + (O.SOURCES[state.mode].proposed ? ' (proposed endpoint)' : '')], ['Lens', SMS.lenses.get(graph.lens).label], ['Target', targetName()], ['Mode', mode ? mode.l : v.scan_profile], ['Sizing', O.SOURCES[state.mode].run.length ? `${v.cycles} cycles · ${v.red_agents} red / ${v.blue_agents} blue · ${Number(v.context_budget).toLocaleString()} tok` : 'server defaults'], ['Sweep', `${v.sweep_passes} pass${v.sweep_passes === 1 ? '' : 'es'}`], ['Intel', v.research ? `on${v.research_scanners ? ' + scanners' : ''}` : 'off'], ['Map', (state.topo && state.topo.provenance) || 'modelled']];
    rows.forEach(([k, val]) => sum.append(h('dt', null, k), h('dd', null, val)));
  }

  function targetName() {
    const v = srcForm(state.mode).values();
    if (state.mode === 'fixture') return (state.targets[state.fixture] || {}).title || state.fixture || '—';
    if (state.mode === 'build') return (v.build_brief || '').trim() || 'Greenhouse default brief';
    if (state.mode === 'project') return (v.path || '').trim() || '—';
    if (state.mode === 'snippet') return (v.filename || '').trim() || `${v.language} snippet`;
    if (state.mode === 'binary') return state.binary ? state.binary.name : '—';
    if (state.mode === 'system') return (v.snapshot_ref || '').trim() || '—';
    if (state.mode === 'ingest') {
      const repo = (v.ingest_repo || '').trim();
      if (!repo) return '—';
      // LAW-4: host only in the Target summary row — never the full URL.
      let host = repo;
      try { host = new URL(repo).hostname || repo; } catch { host = repo.replace(/\.git$/, '').split('/').filter(Boolean).pop() || repo; }
      const sha = (v.commit_hash || '').trim();
      return sha ? `${host} @ ${sha.slice(0, 12)}` : `${host} · HEAD (default branch)`;
    }
  }

  function onSourceChange(mode, key, v) {
    if (mode === 'snippet' || mode === 'system') later(preview, 250);
    if (mode === 'project' || mode === 'ingest' || mode === 'build') later(preview, 500);
    if (mode === 'binary' && key === 'binary') loadBinary(v);
    refresh();
  }
  let debounce = 0;
  function later(fn, ms) { clearTimeout(debounce); debounce = setTimeout(fn, ms); }
  const safeArgv = (s) => { try { const a = JSON.parse(s); return Array.isArray(a) ? a : null; } catch { return null; } };

  /* ---------- preview ---------- */
  function topoSpec() {
    const v = srcForm(state.mode).values();
    if (state.mode === 'fixture') return { type: 'profile', key: state.fixture, target: state.targets[state.fixture] || {} };
    if (state.mode === 'build') return { type: 'profile', key: 'node_query_sink', target: { filename: 'app.js' } };
    if (state.mode === 'project') return { type: 'project', spec: { path: (v.path || '').trim() || 'project', image: v.image, command: safeArgv(v.command), test_command: safeArgv(v.test_command) } };
    if (state.mode === 'ingest') {
      const repo = (v.ingest_repo || '').trim() || 'repository';
      // LAW-4: display the host only — the full URL (which may carry
      // credentials) never lands in the summary rows or the map.
      let host = repo;
      try { host = new URL(repo).hostname || repo; } catch { host = repo.replace(/\.git$/, '').split('/').filter(Boolean).pop() || repo; }
      const sha = (v.commit_hash || '').trim();
      return { type: 'project', spec: { path: host, commit: sha ? `${host} @ ${sha.slice(0, 12)}` : 'HEAD (default branch)' } };
    }
    if (state.mode === 'system') return { type: 'system', services: v.services || '', ref: (v.snapshot_ref || '').trim() || 'snapshot', kindLabel: `${v.snapshot_kind || 'compose'} snapshot` };
    if (state.mode === 'snippet') return { type: 'source', source: v.source || '', language: v.language || 'javascript', filename: (v.filename || '').trim() || ({ javascript: 'app.js', python: 'app.py', php: 'index.php' }[v.language || 'javascript']) };
    return { type: 'binary', filename: (v.filename || '').trim() || (state.binary && state.binary.name) || 'binary' };
  }

  function preview() {
    const spec = topoSpec();
    let topo;
    if (spec.type === 'source') {
      const box = $('s-findings');
      if (!spec.source.trim()) { box.hidden = true; topo = SMS.topology.project({ path: spec.filename, image: 'paste source to map it' }); }
      else {
        topo = SMS.topology.fromSource(spec.source, spec.language, spec.filename);
        const f = topo.findings;
        box.replaceChildren(h('div', null, `parsed ${f.functions} functions · ${f.routes} routes · ${f.inputs} inputs · ${f.imports} imports`), h('div', f.sinks ? 'bad' : null, f.sinks ? `${f.sinks} dangerous call${f.sinks === 1 ? '' : 's'} — candidate attack path drawn on the map` : 'no dangerous sinks matched'));
        box.hidden = false;
      }
    } else if (spec.type === 'system') {
      const box = $('y-findings');
      if (!spec.services.trim()) { box.hidden = true; topo = SMS.topology.fromSystem(SMS.topology.SHOP_STACK, 'example-stack', { provenance: 'modelled', kindLabel: 'example — describe yours' }); }
      else {
        topo = SMS.topology.fromSystem(spec.services, spec.ref, { kindLabel: spec.kindLabel });
        const f = topo.findings;
        box.replaceChildren(h('div', null, `parsed ${f.services} services · ${f.ports} ports · ${f.public} public · ${f.datastores} datastores`), h('div', f.exposedStores.length ? 'bad' : null, f.exposedStores.length ? `datastore reachable from outside the wall: ${f.exposedStores.join(', ')}` : topo.attackPath.length ? `candidate path: ${topo.attackPath.length} hops from a public door` : 'no public door leads to a datastore'));
        box.hidden = false;
      }
    } else if (spec.type === 'binary') topo = state.binary ? state.binary.topo : SMS.topology.project({ path: 'binary', image: 'choose an ELF to map it' });
    else if (spec.type === 'project') topo = SMS.topology.project(spec.spec);
    else topo = SMS.topology.profile(spec.key, spec.target);
    state.topo = topo;
    interp.load(topo, { grow: state.mode === 'build' });
    lensBadge($('pv-lens'), graph.lens);
    pvKey.setLens(graph.lens);
    const kind = topo.provenance || 'modelled';
    $('prov').dataset.kind = kind;
    $('prov-kind').textContent = kind;
    $('prov-text').textContent = kind === 'parsed' ? (state.mode === 'binary' ? 'ELF headers, sections, symbols · call edges inferred' : state.mode === 'system' ? 'hosts, ports, doors and datastores from your services list' : 'functions, routes, inputs, sinks from your source') : state.mode === 'build' ? 'skeleton · Greenhouse grows the rest during the run' : 'profile skeleton · files and symbols named in the stream are added live';
    refresh();
  }

  function loadBinary(f) {
    const box = $('x-findings');
    state.binary = null;
    if (!f) { box.hidden = true; preview(); return; }
    const sf = srcForm('binary');
    if (!String(sf.values().filename || '').trim()) sf.set('filename', f.name.replace(/[^\w.-]/g, '_').slice(0, 128), true);
    if (f.size > 8 * 1024 * 1024) { box.hidden = false; box.replaceChildren(h('div', 'bad', 'Binary exceeds 8 MiB.')); return; }
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const topo = SMS.topology.fromBinary(reader.result, f.name);
        state.binary = { buf: reader.result, topo, name: f.name };
        const x = topo.findings;
        box.replaceChildren(h('div', null, `${x.format}${x.arch ? ` ${x.arch}` : ''} · ${x.functions} functions · ${x.imports} imports · ${x.strings} strings`), h('div', x.dangerous.length ? 'bad' : null, x.dangerous.length ? `dangerous imports: ${x.dangerous.join(', ')}` : 'no dangerous imports found'));
        box.hidden = false;
        preview();
      } catch (e) { box.hidden = false; box.replaceChildren(h('div', 'bad', `Could not parse: ${e.message}`)); }
    };
    reader.readAsArrayBuffer(f);
  }

  /* ---------- source + fixtures ---------- */
  function setMode(mode) {
    if (!O.SOURCES[mode]) mode = 'fixture';
    state.mode = mode;
    localStorage.setItem('sms.v3.prod.mode', mode);
    document.querySelectorAll('.c-mode').forEach((b) => { const on = b.dataset.mode === mode; b.setAttribute('aria-checked', String(on)); b.tabIndex = on ? 0 : -1; });
    document.querySelector('[data-form="fixture"]').hidden = mode !== 'fixture';
    $('src-opts').replaceChildren();
    if (mode !== 'fixture') $('src-opts').append(srcForm(mode).host);
    $('src-opts').hidden = mode === 'fixture';
    $('s-findings').hidden = mode !== 'snippet' || !$('s-findings').childNodes.length;
    $('x-findings').hidden = mode !== 'binary' || !state.binary;
    $('y-findings').hidden = mode !== 'system' || !$('y-findings').childNodes.length;
    $('target-title').textContent = TARGET_TITLE[mode];
    $('launch').textContent = LAUNCH_LABEL[mode];
    runForm.setContext({ source: mode });
    $('cfg-errors').hidden = true;
    preview();
  }
  document.querySelectorAll('.c-mode').forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));
  document.querySelector('.c-modes').addEventListener('keydown', (e) => {
    const d = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!d) return;
    const btns = [...document.querySelectorAll('.c-mode')];
    const i = btns.indexOf(document.activeElement);
    if (i < 0) return;
    e.preventDefault();
    const n = btns[(i + d + btns.length) % btns.length];
    setMode(n.dataset.mode); n.focus();
  });

  function renderFixtures() {
    const root = $('fixture-list');
    root.replaceChildren();
    Object.entries(state.targets).forEach(([key, t]) => {
      const [badge, col] = BADGES[key] || ['FX', '#2dd4bf'];
      const b = h('button', 'c-fx', null, { type: 'button', role: 'radio', 'aria-checked': String(key === state.fixture) });
      b.dataset.key = key;
      b.style.setProperty('--tc', col);
      b.title = t.description || '';
      b.append(h('span', 'tb', badge), h('strong', null, t.title || key), h('code', null, t.filename || ''));
      b.addEventListener('click', () => pickFixture(key));
      root.append(b);
    });
    if (!state.fixture || !state.targets[state.fixture]) state.fixture = Object.keys(state.targets)[0];
    pickFixture(state.fixture);
  }
  function pickFixture(key) {
    state.fixture = key;
    localStorage.setItem('sms.v3.prod.fixture', key);
    document.querySelectorAll('.c-fx').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.key === key)));
    if (state.mode === 'fixture') preview();
  }

  /* ---------- launch ---------- */
  function errors(list) {
    $('cfg-errors').hidden = !list.length;
    $('cfg-errors').textContent = list.join(' ');
    return list.length === 0;
  }

  function summaryRows() {
    return [...$('summary').children].reduce((acc, n, i, arr) => { if (n.tagName === 'DT') acc.push([n.textContent, arr[i + 1].textContent]); return acc; }, []);
  }

  async function launch() {
    if (!state.ready) { toast('Orchestrator not ready — see the note, or use Fake run'); return; }
    const mode = state.mode;
    const errs = [];
    if (mode === 'fixture' && state.fixture === 'binary_argv_echo') errs.push('binary_argv_echo is a compiled fixture — choose Binary to verify it through the binary harness.');
    if (mode !== 'fixture') errs.push(...srcForm(mode).validate(O.REQUIRED[mode]));
    if (mode === 'binary' && !state.binary) errs.push('Choose a compiled binary first.');
    errs.push(...runForm.validate());
    if ($('send-prop').checked) errs.push(...propForm.validate());
    if (!errors(errs)) { const bad = document.querySelector('.s-left [aria-invalid="true"]'); if (bad) bad.focus(); return; }
    const req = compile();
    const body = Object.assign({}, req.body || {});
    if (mode === 'binary') { delete body.blob_b64; await L.putBlob('binary', state.binary.buf); }
    L.save({
      page: 'console', kind: 'live', mode, fixture: state.fixture,
      title: targetName(),
      request: { path: req.path, body: req.body === undefined ? undefined : body, mcp: mode === 'snippet', binary: mode === 'binary' },
      topo: topoSpec(), grow: mode === 'build',
      values: values(), summary: summaryRows()
    });
    location.href = 'console.html';
  }

  // Fake run in the SAME lens as the chosen source. Parsed maps (snippet, binary, system) replay
  // over the user's own map; skeleton sources fall back to that lens's showcase target.
  function fake() {
    const mode = state.mode;
    const spec = topoSpec();
    const own = (mode === 'snippet' && spec.source.trim()) || (mode === 'binary' && state.binary) || (mode === 'system' && spec.services.trim());
    const SHOW = { project: 'repo_notes_app', ingest: 'repo_notes_app', binary: 'binary_argv_echo', system: 'system_shop_stack' };
    const key = own ? 'custom' : mode === 'fixture' && state.fixture ? state.fixture : SHOW[mode] || 'node_query_sink';
    const info = state.targets[key] || SMS.link.SAMPLE_TARGETS[key] || SMS.link.SHOWCASE_TARGETS[key] || {};
    const title = own ? (targetName() !== '—' ? targetName() : `your ${SMS.lenses.get(graph.lens).label.toLowerCase()}`) : info.title || key;
    L.save({
      page: 'console', kind: 'fake', mode: own ? mode : 'fixture', fixture: key, title,
      topo: own ? spec : { type: 'profile', key, target: info },
      grow: mode === 'build',
      summary: [['Source', 'Fake run'], ['Lens', SMS.lenses.get(graph.lens).label], ['Target', title], ['Backend', 'none — scripted events']]
    });
    if (own && mode === 'binary') L.putBlob('binary', state.binary.buf).then(() => { location.href = 'console.html'; });
    else location.href = 'console.html';
  }

  $('launch').addEventListener('click', launch);
  $('fake').addEventListener('click', fake);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); launch(); }
    if (e.key === 'Escape' && !/input|textarea|select/i.test(e.target.tagName)) location.href = 'index.html';
  });

  function chip(id, st, text) { const c = $(id); c.dataset.state = st; if (text) c.lastChild.textContent = text; }

  /* ---------- boot ---------- */
  renderFixtures();
  setMode(state.mode);
  SMS.link.probe().then((link) => {
    state.ready = link.ready;
    state.targets = link.targets || SMS.link.SAMPLE_TARGETS;
    if (link.health) {
      state.inferenceMode = link.inferenceMode;
      Object.assign(state.ctx, { scanProfiles: link.health.scan_profiles || [], models: link.health.profiles || [], defaultModel: link.health.default_profile || ((link.health.profiles || [])[0] || {}).key || '' });
      runForm.setContext(state.ctx);
      Object.values(srcForms).forEach((f) => f.setContext({ inferenceMode: state.inferenceMode }));
    }
    renderFixtures();
    chip('chip-server', link.online ? 'ok' : 'error', link.online ? 'Orchestrator' : 'Offline');
    chip('chip-docker', !link.online ? 'pending' : link.docker === 'ready' ? 'ok' : 'error', !link.online ? 'Docker ?' : { ready: 'Docker', images_missing: 'Images missing', unavailable: 'Docker offline' }[link.docker] || 'Docker');
    chip('chip-key', !link.online ? 'pending' : link.keyOk ? 'ok' : 'warn', link.inferenceMode === 'local' ? 'Local inference' : link.keyOk ? 'Muse' : 'No API key');
    $('launch').disabled = !link.ready;
    if (link.notes.length) { $('setup').hidden = false; $('setup').textContent = `${link.notes.join(' ')} You can still configure, preview the map and request, or use Fake run.`; }
    $('launch-note').textContent = link.ready ? 'Launching opens the console and streams the run in real time.' : 'Orchestrator not ready — Launch is disabled. Fake run previews the console.';
    refresh();
  });
})();
