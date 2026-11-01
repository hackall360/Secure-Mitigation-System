// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · ui/inspector.js — detail panel for the selected node or agent, with the stream
// events that touch it. renderInspect(rootEl, graph.describe(id) | null, { events, topo }).
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const { h, stamp } = SMS.hud;
  const P = SMS.palette;

  function renderInspect(root, d, o = {}) {
    const events = o.events || [];
    const topo = o.topo || null;
    root.replaceChildren();
    if (!d) {
      root.append(h('p', 'ins-k', 'Inspector'), h('p', 'ins-hint', 'Click any node or agent on the map. Drag to pan, scroll to zoom, double-click to dive in.'));
      root.style.removeProperty('--ic');
      return;
    }
    const related = (pred) => events.filter(pred).slice(-8).reverse();
    const evList = (evs) => {
      const box = h('div', 'ins-ev');
      if (!evs.length) box.append(h('p', null, 'No events mention this yet.'));
      evs.forEach((ev) => { const a = P.agent(ev.speaker); const p = h('p', null, `${stamp(ev.at)} ${ev.speaker}: ${ev.text}`); p.style.setProperty('--c', a ? a.color : '#94a8c4'); box.append(p); });
      return box;
    };
    if (d.type === 'agent') {
      const a = d.agent;
      root.style.setProperty('--ic', a.color);
      root.append(h('p', 'ins-k', `${d.team.label} · ${a.leader ? 'family lead' : 'agent'}`), h('h3', null, a.id), h('p', 'ins-p', `${a.personality} — ${a.role}`));
      const dl = h('dl');
      [['messages', String(a.msgs)], ['family', d.team.blurb], ['shade', a.color]].forEach(([k, v]) => dl.append(h('dt', null, k), h('dd', null, v)));
      root.append(dl, h('p', 'ins-k', 'Recent traffic'), evList(related((e) => e.speaker === a.id || e.to === a.id)));
      return;
    }
    const n = d.node;
    const st = P.STATE[n.state] || P.STATE.idle;
    root.style.setProperty('--ic', st.color);
    root.append(h('p', 'ins-k', `${n.kind} · ring ${n.depth} · ${st.label}`), h('h3', null, n.label));
    if (n.sub) root.append(h('p', 'ins-p', n.sub));
    const dl = h('dl');
    const onPath = topo && (topo.attackPath || []).includes(n.id);
    [['path', d.path.join(' / ')], ['links', d.neighbours.map((x) => x.label).slice(0, 8).join(', ') || '—'], ['attack path', onPath ? 'yes — candidate tainted route' : 'no'], ['source', (topo && topo.provenance) || 'modelled']].forEach(([k, v]) => dl.append(h('dt', null, k), h('dd', null, v)));
    root.append(dl);
    const key = n.label.toLowerCase().replace(/\(\)$/, '');
    root.append(h('p', 'ins-k', 'Events touching this node'), evList(related((e) => e.text.toLowerCase().includes(key) || e.to === n.id)));
  }

  SMS.views = Object.assign(SMS.views || {}, { renderInspect });
})();
