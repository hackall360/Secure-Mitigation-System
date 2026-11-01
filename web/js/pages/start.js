// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · start page — mode selection, version info, ambient map.
'use strict';
(() => {
  const SMS = window.SMS;
  const P = SMS.palette;
  const V = SMS.launch.VERSION;
  const { h, scramble, lensIcon } = SMS.hud;
  const Ls = SMS.lenses;
  const $ = (id) => document.getElementById(id);

  const graph = new SMS.SpiderGraph($('graph'), { mode: 'demo', interactive: false });
  document.body.dataset.explain = 'both';
  // The background map cycles through all four lenses so the first screen shows the range.
  const CYCLE = [['php_command_sink', { filename: 'index.php' }], ['repo_notes_app', {}], ['binary_argv_echo', { filename: 'argv_echo' }], ['system_shop_stack', {}]];
  let cyc = 0;
  function showLens(i) {
    cyc = i % CYCLE.length;
    graph.setTopology(SMS.topology.profile(CYCLE[cyc][0], CYCLE[cyc][1]));
    document.querySelectorAll('.l-lens').forEach((c) => c.classList.toggle('on', c.dataset.lens === graph.lens));
    const L = Ls.get(graph.lens);
    $('lens-now').textContent = `now showing: ${L.label.toLowerCase()} — ${L.metaphor.toLowerCase()}`;
  }
  const sync = () => graph.setInsets({ l: window.innerWidth > 1000 ? window.innerWidth * 0.5 : 0, r: 0, t: 0, b: 0 });
  sync();
  window.addEventListener('resize', sync);
  // Decorative ambience only: unlabeled bubbles, no fake text.
  setInterval(() => {
    if (document.hidden) return;
    const a = P.AGENTS[(Math.random() * P.AGENTS.length) | 0];
    const n = [...graph.nodes.keys()];
    graph.send(a.id, Math.random() < 0.6 ? n[(Math.random() * n.length) | 0] : P.AGENTS[(Math.random() * P.AGENTS.length) | 0].id, { label: '', dur: 1700 });
    if (Math.random() < 0.12 && graph.attackPath.length) graph.flowPath(graph.attackPath, { color: P.TEAMS.red.hue, kind: 'taint', count: 2, size: 2 });
  }, 560);

  // name, version, description
  $('ver-short').textContent = `v${V.version}`;
  $('l-desc').textContent = V.description;
  const facts = $('ver-facts');
  [['System', V.name], ['Version', V.version], ['Interface', V.ui], ['Channel', V.channel], ['Build date', V.date]].forEach(([k, v]) => { const d = h('div'); d.append(h('dt', null, k), h('dd', null, v)); facts.append(d); });
  V.changes.forEach((c) => $('ver-changes').append(h('li', null, c)));
  V.contract.forEach((c) => $('ver-contract').append(h('li', null, c)));
  $('ver-btn').addEventListener('click', () => {
    const open = $('ver-panel').hidden;
    $('ver-panel').hidden = !open;
    $('ver-btn').setAttribute('aria-expanded', String(open));
  });

  // Lens cards: what each kind of target looks like, in plain words. Click → visualizer in that lens.
  Ls.ORDER.forEach((k, i) => {
    const L = Ls.get(k);
    const a = h('a', 'l-lens', null, { href: `visualizer.html?lens=${k}`, title: `${L.label}: ${L.expert}` });
    a.dataset.lens = k;
    a.style.setProperty('--lens', L.accent);
    const ic = h('span', 'l-lens-ic');
    ic.append(lensIcon(k, 20));
    a.append(ic, h('b', null, L.label), h('span', 'l-lens-m', L.metaphor), h('small', null, L.simple));
    a.addEventListener('mouseenter', () => showLens(i));
    a.addEventListener('focus', () => showLens(i));
    $('lenses').append(a);
  });
  showLens(0);
  setInterval(() => { if (!document.hidden && !document.querySelector('.l-lens:hover')) showLens(cyc + 1); }, 9000);

  const fams = $('fams');
  P.TEAM_ORDER.forEach((k) => {
    const T = P.TEAMS[k];
    const li = h('li');
    li.style.setProperty('--c', T.hue);
    const sw = h('span', 'sw', null, { 'aria-hidden': 'true' });
    P.teamAgents(k).forEach((a) => { const i = h('i'); i.style.setProperty('--s', a.color); i.title = `${a.id} · ${a.personality}`; sw.append(i); });
    li.append(sw, document.createTextNode(T.label));
    fams.append(li);
  });

  document.addEventListener('keydown', (e) => {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    const card = document.querySelector(`.l-card[data-key="${e.key}"]`);
    if (card) location.href = card.getAttribute('href');
    if (e.key.toLowerCase() === 'v') $('ver-btn').click();
  });

  scramble($('l-title'), V.name.toUpperCase(), 1100);

  SMS.link.probe().then((link) => {
    const c = $('orch');
    c.dataset.state = link.ready ? 'ok' : link.online ? 'warn' : 'error';
    c.lastChild.textContent = link.ready ? 'Orchestrator ready' : link.online ? 'Orchestrator not ready' : 'Orchestrator offline';
    c.title = link.notes.join(' ');
  });
})();
