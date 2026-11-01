// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · engine/layout.js — Radial tree layout for target nodes + orbit placement for agents.
// Mixin: methods are added to SMS.SpiderGraph.prototype. Load after engine/graph.js.
'use strict';
(() => {
  const SMS = window.SMS;
  const { TAU, RING0, RING_STEP } = SMS.engine;
  const P = () => SMS.palette;

  Object.assign(SMS.SpiderGraph.prototype, {
    // Radial tree layout: every subtree gets an angular span proportional to its leaf count.
    _layout() {
      const root = this.nodes.get(this._rootId());
      if (!root) return;
      const leaves = new Map();
      const count = (n) => {
        const kids = n.children.map((id) => this.nodes.get(id)).filter(Boolean);
        const v = kids.length ? kids.reduce((s, k) => s + count(k), 0) : 1;
        leaves.set(n.id, v);
        return v;
      };
      count(root);
      const place = (n, a0, a1) => {
        const mid = (a0 + a1) / 2;
        const r = this.ringRadius(n.depth);
        n.hx = Math.cos(mid) * r;
        n.hy = Math.sin(mid) * r;
        n.angle = mid;
        n.a0 = a0; n.a1 = a1;          // angular span (used by lens backdrops: districts, rooms, bands)
        const kids = n.children.map((id) => this.nodes.get(id)).filter(Boolean);
        const total = kids.reduce((s, k) => s + leaves.get(k.id), 0) || 1;
        // Deeper rings get a slightly narrower span so branches read as spokes.
        const span = a1 - a0;
        const pad = n.depth === 0 ? 0 : span * 0.06;
        let cursor = a0 + pad;
        const usable = span - pad * 2;
        kids.forEach((k) => {
          const part = usable * (leaves.get(k.id) / total);
          place(k, cursor, cursor + part);
          cursor += part;
        });
      };
      // Offset so the first subsystem does not start exactly on a sector boundary.
      place(root, -Math.PI / 2 + 0.25, -Math.PI / 2 + 0.25 + TAU);
      root.hx = 0; root.hy = 0;
      this._layoutAgents();
    },

    ringRadius(d) { return d <= 0 ? 0 : RING0 + (d - 1) * RING_STEP; },

    orbitRadius() { return this.ringRadius(this.maxDepth) + 150; },

    _initAgents() {
      this.agents.clear();
      P().AGENTS.forEach((a) => {
        this.agents.set(a.id, Object.assign({}, a, { x: 0, y: 0, hx: 0, hy: 0, msgs: 0, speakAt: -1e9, awake: false, phase: Math.random() * TAU }));
      });
      this._layoutAgents(true);
    },

    _layoutAgents(snap) {
      const R = this.orbitRadius();
      P().TEAM_ORDER.forEach((team) => {
        const members = [...this.agents.values()].filter((a) => a.team === team);
        const leader = members.find((a) => a.leader);
        const rest = members.filter((a) => !a.leader);
        // Leader in the middle, members fan out alternately on both sides.
        const ordered = [];
        rest.forEach((a, i) => { if (i % 2) ordered.push(a); else ordered.unshift(a); });
        if (leader) ordered.splice(Math.floor(ordered.length / 2), 0, leader);
        const step = 0.115;
        const base = P().TEAMS[team].angle;
        ordered.forEach((a, i) => {
          const ang = base + (i - (ordered.length - 1) / 2) * step;
          const r = R + (a.leader ? -18 : (i % 2 ? 26 : 8));
          a.angle = ang;
          a.hx = Math.cos(ang) * r;
          a.hy = Math.sin(ang) * r;
          if (snap) { a.x = a.hx; a.y = a.hy; }
        });
      });
    }
  });
})();
