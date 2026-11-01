// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · demo visual page — cinematic presenter mode. The run is chosen on
// demo-setup.html (js/core/handoff.js) and starts on arrival. Live runs are real time.
'use strict';
(() => {
  const SMS = window.SMS;
  const { h, CommsFeed, Legend, StageBar, Terminal, HexStream, HoverCard, StreamMeter, ExplainToggle, Explainer, MapKey, lensBadge, counter, toast, elapsed, scramble } = SMS.hud;
  const N = SMS.narrator;
  const L = SMS.launch;
  const P = SMS.palette;
  const $ = (id) => document.getElementById(id);

  const graph = new SMS.SpiderGraph($('graph'), { mode: 'demo' });
  const interp = new SMS.Interpreter(graph);
  const comms = new CommsFeed($('comms'), { emptyText: 'Messages between agents land here, and fly across the map as bubbles.' });
  const legend = new Legend($('legend'), graph, { onFilter: (set) => comms.setFilter(set) });
  const stagebar = new StageBar($('stagebar'));
  const term = new Terminal($('term'));
  const hex = new HexStream($('hex'));
  new HoverCard($('hovercard'), graph, $('stage'));
  const meter = new StreamMeter($('meter'), { label: 'stream' });
  // Two reading levels: plain words for anyone, precise terms for security people (E cycles).
  const explainer = new Explainer($('explain'));
  const mapkey = new MapKey($('mapkey'));
  new ExplainToggle($('ex-toggle'), { page: 'demo', def: 'both' });

  const state = { launch: null, source: 'fake', session: null, replay: null, started: 0, timer: 0, result: null, running: false, msgs: 0, lens: 'file', story: {}, stage: '' };
  SMS.explain.on((lv) => { graph.setExplain(lv); if (state.stage) caption(state.stage, state.override); requestAnimationFrame(syncInsets); });

  /* ---------- fit the map into the space the HUD leaves free ---------- */
  function syncInsets() {
    const vis = (el) => el && el.offsetParent !== null && getComputedStyle(el).display !== 'none';
    const W = window.innerWidth;
    const H = window.innerHeight;
    const L = document.querySelector('.d-left');
    const R = document.querySelector('.d-right');
    const top = document.querySelector('.d-top');
    const bot = document.querySelector('.d-caption');
    graph.setInsets({
      l: vis(L) ? L.getBoundingClientRect().right + 6 : 0,
      r: vis(R) ? W - R.getBoundingClientRect().left + 6 : 0,
      t: top ? top.getBoundingClientRect().bottom + 4 : 0,
      b: vis(bot) && document.body.dataset.phase !== 'idle' ? H - bot.getBoundingClientRect().top + 4 : 0
    });
  }
  window.addEventListener('resize', syncInsets);

  function chipSource() {
    const chip = $('src-chip');
    chip.dataset.state = state.source === 'live' ? 'live' : 'replay';
    chip.lastChild.textContent = state.source === 'live' ? 'Live · real time' : 'Fake run · scripted';
  }

  /* ---------- run ---------- */
  function resetHud() {
    comms.clear('Opening channels…');
    term.clear();
    hex.clear();
    legend.reset();
    stagebar.reset();
    state.msgs = 0;
    ['st-nodes', 'st-msgs', 'st-find', 'st-patch', 'st-ver'].forEach((id) => { $(id).dataset.v = '0'; $(id).textContent = '0'; });
    $('msg-count').textContent = '0 msgs';
    $('verdict').hidden = true;
  }

  async function run() {
    const launch = state.launch;
    if (state.running || !launch) return;
    const grow = !!launch.grow;
    const { topo } = await L.topology(launch);
    resetHud();
    interp.load(topo, { grow });
    state.lens = graph.lens;
    state.story = N.context(topo, graph);
    lensBadge($('d-lens'), state.lens);
    mapkey.setLens(state.lens);
    explainer.set(N.intro(state.lens, state.story));
    graph.setDirector($('btn-director').getAttribute('aria-pressed') === 'true');
    state.running = true;
    state.result = null;
    document.body.dataset.phase = 'running';
    requestAnimationFrame(syncInsets);
    caption('sandbox', grow ? 'Greenhouse is growing a fresh target.' : `Isolating ${launch.filename || launch.title}.`);
    state.started = Date.now();
    clearInterval(state.timer);
    state.timer = setInterval(() => { $('clock').textContent = elapsed(Date.now() - state.started); idleCaption(); }, 250);
    counter($('st-nodes'), graph.nodes.size);
    const handlers = {
      onOpen: () => meter.open(state.source === 'live' ? 'stream' : 'fake run'),
      onLine: (team, msg, payload) => onLine(team, msg, payload),
      onResult: (payload) => onResult(payload),
      onRefuse: (type, msg) => { onLine('system', type === 'busy' ? 'Scan refused: another scan holds the server lock.' : (msg || 'Request rejected.')); toast(type === 'busy' ? 'Orchestrator busy — wait for the current run' : 'Request rejected'); },
      onClose: (info) => onClose(info),
      onError: () => onLine('system', 'Connection hiccup — the scan keeps running on the server.')
    };
    const live = state.source === 'live';
    $('speed-group').hidden = live;
    $('btn-pause').hidden = live;
    chipSource();
    if (live) {
      try {
        meter.open('stream');
        state.session = new SMS.link.Session(launch.request.path, launch.request.body, handlers);
      } catch (e) {
        toast(`Live run unavailable: ${e.message}`);
        onClose({});
      }
    } else {
      const key = launch.fixture || 'node_query_sink';
      meter.open('fake run');
      state.replay = new SMS.scenario.Replay(SMS.scenario.script(key, topo, { grow }), Object.assign(SMS.scenario.result(key, topo), { replay: true }), handlers).start();
      state.replay.setSpeed(Number(document.querySelector('[data-speed][aria-pressed="true"]').dataset.speed));
    }
  }

  function onLine(team, msg, payload) {
    const ev = interp.line(team, msg, payload);
    meter.tick();
    state.lastLine = ev;
    comms.add(ev);
    term.push(team, msg);
    hex.push(team, msg);
    state.msgs += 1;
    $('msg-count').textContent = `${state.msgs} msgs`;
    counter($('st-msgs'), state.msgs);
    counter($('st-nodes'), graph.nodes.size);
    counter($('st-find'), interp.stats.findings);
    counter($('st-patch'), interp.stats.patches);
    // The narrative follows the swarm: the raw message for experts, the story in plain words.
    const a = P.agent(ev.speaker);
    explainer.set({ expert: `${ev.speaker}${ev.toLabel ? ` → ${ev.toLabel}` : ''}: ${ev.body || msg}` });
    const said = N.event(state.lens, ev, state.story, interp);
    if (said) { explainer.set({ simple: said.simple }); $('cap-tech').textContent = said.expert; }
    $('cap-team').textContent = a ? P.TEAMS[a.team].short : '';
    $('cap-team').style.color = a ? a.color : '';
  }

  // Real-time runs have long quiet stretches (model calls, Docker builds). Say who is busy.
  function idleCaption() {
    if (!state.running || !graph.working) return;
    const q = meter.quietFor();
    if (q < 6000) return;
    const w = graph.working;
    const n = w.node && graph.node(w.node);
    const sec = Math.floor(q / 1000);
    const ago = `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
    explainer.set({
      expert: `${w.agent} is working${n ? ` on ${n.label}` : ''} · ${ago} since the last event${state.lastLine ? ` (“${(state.lastLine.body || state.lastLine.text).slice(0, 90)}”)` : ''}`,
      simple: `${w.agent} is busy thinking${n ? ` about ${n.label}` : ''}. Real computers take real time — ${ago} so far.`
    });
  }

  // Phase title: plain words unless the viewer chose Expert; the expert detail sits under it.
  function caption(stage, override) {
    const m = P.STAGE_META[stage];
    if (!m) return;
    state.stage = stage;
    state.override = override;
    const said = N.stage(state.lens, stage, state.story) || { simple: m.caption, expert: m.caption };
    const expert = SMS.explain.level === 'expert';
    $('cap-phase').textContent = `PHASE ${m.n} // ${m.label.toUpperCase()}`;
    scramble($('cap-title'), override || (expert ? m.caption : said.simple), 650);
    $('cap-tech').textContent = said.expert;
    document.body.dataset.stage = stage;
  }

  interp.on('stage', (stage) => { stagebar.set(stage); caption(stage); });

  function onResult(payload) {
    state.result = payload;
    interp.result(payload);
    const ok = SMS.OK_STATUSES.includes(payload.status);
    stagebar.finish(ok);
    counter($('st-ver'), interp.stats.verified);
    setTimeout(() => showVerdict(payload), 900);
  }

  function onClose(info) {
    clearInterval(state.timer);
    meter.close();
    graph.setWorking(null);
    state.running = false;
    state.session = null;
    state.replay = null;
    document.body.dataset.phase = 'done';
    if (!state.result) {
      const stopped = info && info.cancelled;
      caption('cleanup', stopped ? 'Stopped. Nothing was applied to the original.' : 'Connection closed before a verdict arrived.');
      setTimeout(() => { if (!state.running) showVerdict({ status: stopped ? 'stopped' : 'error', message: stopped ? 'The run was stopped. Nothing was applied to the original target.' : 'The stream closed before a verdict arrived. Server-side cleanup finishes on its own.', replay: state.source !== 'live' }); }, 900);
    }
  }

  const RESULT_TITLES = { verified: 'Boundary verified · purple lock', not_confirmed: 'Boundary not confirmed', no_finding: 'No finding this cycle', no_findings: 'No findings', inconclusive: 'Probe inconclusive', rolled_back: 'Change rolled back', rejected: 'Candidate patch rejected', failed: 'Boundary still reachable', partial: 'Partially verified', completed: 'Verification completed', error: 'Scan could not complete', stopped: 'Run stopped' };

  function showVerdict(p) {
    const v = $('verdict');
    v.dataset.status = p.status;
    $('v-kicker').textContent = p.replay ? 'Verdict · fake run (scripted, no backend)' : 'Verdict · live orchestrator';
    $('v-title').textContent = RESULT_TITLES[p.status] || 'Scan finished';
    $('v-msg').textContent = p.message || '';
    $('v-simple').textContent = N.verdict(state.lens, p, state.story).simple;
    const pre = p.pre_probe_exit ?? p.pre_exit_code;
    const post = p.post_probe_exit ?? p.post_exit_code;
    const fact = (id, text, good) => { $(id).textContent = text; if (good === undefined) delete $(id).dataset.good; else $(id).dataset.good = String(good); };
    fact('v-pre', pre === undefined || pre === null ? 'not run' : `exit ${pre} · ${pre === 0 ? 'reachable' : pre === 1 ? 'blocked' : 'inconclusive'}`, undefined);
    fact('v-post', post === undefined || post === null ? 'not run' : `exit ${post} · ${post === 1 ? 'blocked' : post === 0 ? 'reachable' : 'inconclusive'}`, post === undefined || post === null ? undefined : post === 1);
    fact('v-reg', p.regression_passed === undefined ? 'not reported' : p.regression_passed ? 'passed' : 'failed', p.regression_passed);
    const receipt = p.receipt || p.verdict_receipt;
    const sha = receipt && (receipt.patch_sha256 || receipt.patch_hash);
    fact('v-sha', sha ? `${String(sha).slice(0, 12)}… ${receipt.chain_ok === false ? '✕ chain' : '⛓ chained'}` : 'none', sha ? receipt.chain_ok !== false : undefined);
    const diff = p.diff || p.cumulative_diff || '';
    $('v-diff-wrap').hidden = !diff;
    if (diff) {
      const pre2 = $('v-diff');
      pre2.replaceChildren();
      let add = 0; let del = 0;
      diff.split('\n').forEach((line) => {
        const s = h('span', line.startsWith('+++') || line.startsWith('---') ? 'file' : line.startsWith('+') ? 'add' : line.startsWith('-') ? 'del' : line.startsWith('@@') ? 'hunk' : '', `${line}\n`);
        if (s.className === 'add') add += 1;
        if (s.className === 'del') del += 1;
        pre2.append(s);
      });
      $('v-diffstat').textContent = `+${add} −${del}`;
    }
    v.hidden = false;
    document.body.dataset.phase = 'verdict';
  }

  $('v-again').addEventListener('click', () => { $('verdict').hidden = true; document.body.dataset.phase = 'done'; run(); });
  $('v-json').addEventListener('click', () => {
    if (!state.result) return;
    SMS.link.download(`sms-${(state.launch && state.launch.key) || 'demo'}-report.json`, Object.assign({ notice: 'Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.', license_url: 'https://polyformproject.org/licenses/noncommercial/1.0.0' }, state.result));
  });

  function stop() {
    if (state.session) state.session.stop();
    if (state.replay) { state.replay.stop(); state.replay = null; onClose({ cancelled: true }); }
  }

  /* ---------- toolbar ---------- */
  $('btn-director').addEventListener('click', (e) => {
    const on = e.currentTarget.getAttribute('aria-pressed') !== 'true';
    e.currentTarget.setAttribute('aria-pressed', String(on));
    graph.setDirector(on);
    if (on) graph.fit();
  });
  $('btn-labels').addEventListener('click', (e) => {
    const on = e.currentTarget.getAttribute('aria-pressed') !== 'true';
    e.currentTarget.setAttribute('aria-pressed', String(on));
    graph.setLayer('labels', on ? 'all' : 'auto');
  });
  $('btn-full').addEventListener('click', () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen && document.documentElement.requestFullscreen().catch(() => {});
  });
  $('btn-pause').addEventListener('click', () => {
    if (!state.replay) return;
    const paused = state.replay.toggle();
    toast(paused ? 'Paused · → to step' : 'Resumed');
  });
  document.querySelectorAll('[data-speed]').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('[data-speed]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    if (state.replay) state.replay.setSpeed(Number(b.dataset.speed));
  }));

  document.addEventListener('keydown', (e) => {
    const tag = (e.target.tagName || '').toLowerCase();
    if (e.altKey || e.ctrlKey || e.metaKey || tag === 'input' || tag === 'textarea' || tag === 'select') return;
    const k = e.key.toLowerCase();
    if (k === 'escape') { if (state.running) stop(); else if (graph.selected) graph.select(null); else location.href = 'demo-setup.html'; return; }
    if (k === 'enter' && !state.running) { e.preventDefault(); $('verdict').hidden = true; run(); return; }
    if (k === ' ' && state.replay && state.running) { e.preventDefault(); $('btn-pause').click(); return; }
    if (k === 'arrowright' && state.replay && state.replay.paused) { state.replay.step(); return; }
    if (k === 'd') { $('btn-director').click(); return; }
    if (k === 'l') { $('btn-labels').click(); return; }
    if (k === 'f') { $('btn-full').click(); return; }
    if (k === 'p') { document.body.classList.toggle('presenting'); return; }
  });

  /* ---------- boot ---------- */
  state.launch = L.load();
  if (!state.launch || state.launch.page !== 'demo') { location.replace('demo-setup.html'); return; }
  state.source = state.launch.kind === 'live' ? 'live' : 'fake';
  $('d-target').textContent = state.launch.filename || state.launch.title;
  $('d-sub').textContent = state.launch.title || '';
  chipSource();
  syncInsets();
  run();
})();
