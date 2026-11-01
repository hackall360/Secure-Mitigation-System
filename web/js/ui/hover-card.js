// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · ui/hover-card.js — HoverCard: floating detail card for the node / agent under the pointer.
// DOM-only, textContent everywhere (no innerHTML), CSP-safe.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const U = (SMS.hud = SMS.hud || {});
  const P = () => SMS.palette;
  const { h } = U;

  /* ---------------- hover card ---------------- */
  class HoverCard {
    constructor(root, graph, host) {
      this.root = root;
      this.host = host;
      this.g = graph;
      graph.on('hover', (d) => this.show(d));
      graph.on('hovermove', (p) => this.move(p.sx, p.sy));
    }
    show(d) {
      if (!d) { this.root.hidden = true; return; }
      this.root.replaceChildren();
      if (d.type === 'agent') {
        const a = d.agent;
        this.root.style.setProperty('--c', a.color);
        this.root.append(h('p', 'hc-k', `${d.team.label} · ${a.leader ? 'lead' : 'agent'}`), h('h4', null, a.id), h('p', 'hc-p', a.personality), h('p', 'hc-r', a.role), h('p', 'hc-m', `${a.msgs} message${a.msgs === 1 ? '' : 's'} this run`));
        if (d.team.kid) this.root.append(h('p', 'hc-x x-simple', d.team.kid));
      } else if (d.type === 'node') {
        const n = d.node;
        const st = P().STATE[n.state] || P().STATE.idle;
        this.root.style.setProperty('--c', st.color);
        const kind = SMS.lenses ? SMS.lenses.kind(this.g.lens || 'file', n.depth === 0 ? 'core' : n.kind) : { simple: n.kind, expert: n.kind };
        this.root.append(h('p', 'hc-k', `${kind.expert} · ring ${n.depth} · ${st.label}`), h('h4', null, n.label));
        this.root.append(h('p', 'hc-x x-simple', `${kind.simple}${st.kid ? ` — ${st.kid}` : ''}`));
        if (n.sub) this.root.append(h('p', 'hc-p', n.sub));
        this.root.append(h('p', 'hc-r', d.path.join(' / ')));
        if (d.neighbours.length) this.root.append(h('p', 'hc-m', `links: ${d.neighbours.slice(0, 5).map((x) => x.label).join(', ')}`));
      }
      this.root.hidden = false;
      this.move(d.sx, d.sy);
    }
    move(x, y) {
      if (this.root.hidden) return;
      const W = this.host.clientWidth;
      const left = x + 18 + 260 > W ? x - 278 : x + 18;
      this.root.style.transform = `translate(${Math.max(8, left)}px, ${Math.max(8, y - 20)}px)`;
    }
  }

  Object.assign(U, { HoverCard });
})();
