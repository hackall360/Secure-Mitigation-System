// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · engine/graph-model.js — Topology model: nodes, links, states, selection, description.
// Mixin: methods are added to SMS.SpiderGraph.prototype. Load after engine/graph.js.
'use strict';
(() => {
  const SMS = window.SMS;
  const { TAU, now } = SMS.engine;
  const P = () => SMS.palette;

  Object.assign(SMS.SpiderGraph.prototype, {
    reset() {
      this.nodes.clear();
      this.links = [];
      this.linkIndex.clear();
      this.packets = [];
      this.particles = [];
      this.waves = [];
      this.tethers = [];
      this.flows = [];
      this.attackPath = [];
      this.verdict = '';
      this.working = null;
      this.sendCursor = 0;
      this.selected = null;
      this.hover = null;
      this.focusId = null;
      this.agents.forEach((a) => { a.msgs = 0; a.speakAt = -1e9; a.awake = false; });
    },

    setTopology(topo) {
      this.reset();
      if (!topo || !topo.root) return;
      this.setLens(SMS.lenses ? SMS.lenses.of(topo) : 'file');
      this.addNode(Object.assign({ depth: 0, state: 'scanned' }, topo.root), { silent: true, instant: true });
      (topo.nodes || []).forEach((n) => this.addNode(n, { silent: true, instant: !!topo.instant, delay: n.delay }));
      (topo.links || []).forEach((l) => this.link(l.source, l.target, l.kind || 'call'));
      this.flows = (topo.flows || []).map((f) => f.filter((id) => this.nodes.has(id)));
      this.attackPath = (topo.attackPath || []).filter((id) => this.nodes.has(id));
      this._layout();
      this.fit(true);
    },

    addNode(spec, o = {}) {
      if (!spec || !spec.id) return null;
      const existing = this.nodes.get(spec.id);
      if (existing) {
        if (spec.state) existing.state = spec.state;
        if (spec.meta) existing.meta = Object.assign(existing.meta || {}, spec.meta);
        return existing;
      }
      const parent = spec.parent ? this.nodes.get(spec.parent) : null;
      const depth = spec.depth !== undefined ? spec.depth : parent ? parent.depth + 1 : 1;
      const t = now() + (o.delay || 0);
      const n = {
        id: spec.id,
        label: spec.label || spec.id,
        sub: spec.sub || '',
        kind: spec.kind || 'module',
        parent: parent ? parent.id : (depth === 0 ? null : (this._rootId() || null)),
        depth,
        state: spec.state || 'idle',
        meta: spec.meta || {},
        x: parent ? parent.x : 0,
        y: parent ? parent.y : 0,
        vx: 0, vy: 0, hx: 0, hy: 0,
        born: o.instant ? t - 2000 : t,
        phase: Math.random() * TAU,
        ping: 0,
        heat: 0,
        children: []
      };
      if (!parent && depth > 0 && n.parent) {
        const root = this.nodes.get(n.parent);
        if (root) { n.x = root.x; n.y = root.y; }
      }
      this.nodes.set(n.id, n);
      const p = n.parent ? this.nodes.get(n.parent) : null;
      if (p) { p.children.push(n.id); this.link(p.id, n.id, 'tree'); }
      this.maxDepth = Math.max(3, n.depth);
      if (!o.silent) {
        this._layout();
        this.wave(n.id, P().STATE[n.state] ? P().STATE[n.state].color : '#cfe3ff', 26);
        this.emit('discover', n);
      }
      return n;
    },

    _rootId() {
      for (const n of this.nodes.values()) if (n.depth === 0) return n.id;
      return null;
    },

    link(a, b, kind = 'call') {
      if (!this.nodes.has(a) || !this.nodes.has(b) || a === b) return null;
      const key = `${a}>${b}`;
      if (this.linkIndex.has(key)) return this.linkIndex.get(key);
      const l = { a, b, kind, guard: 0, heat: 0, color: '' };
      this.links.push(l);
      this.linkIndex.set(key, l);
      return l;
    },

    getLink(a, b) { return this.linkIndex.get(`${a}>${b}`) || this.linkIndex.get(`${b}>${a}`) || null; },

    node(id) { return this.nodes.get(id) || null; },

    find(pred) { for (const n of this.nodes.values()) if (pred(n)) return n; return null; },

    setFlows(flows) { this.flows = flows.map((f) => f.filter((id) => this.nodes.has(id))); },

    setAttackPath(path) { this.attackPath = path.filter((id) => this.nodes.has(id)); },

    setState(id, state, quiet) {
      const n = this.nodes.get(id);
      if (!n || n.state === state) return;
      n.state = state;
      n.heat = 1;
      if (!quiet) this.wave(id, (P().STATE[state] || P().STATE.idle).color, 40);
    },

    describe(id) {
      if (!id) return null;
      const a = this.agents.get(id);
      if (a) return { type: 'agent', id, agent: a, team: P().TEAMS[a.team] };
      const n = this.nodes.get(id);
      if (!n) return null;
      const path = [];
      let cur = n;
      while (cur) { path.unshift(cur.label); cur = cur.parent ? this.nodes.get(cur.parent) : null; }
      const neighbours = this.links.filter((l) => l.a === id || l.b === id).map((l) => (l.a === id ? l.b : l.a)).map((x) => this.nodes.get(x)).filter(Boolean);
      return { type: 'node', id, node: n, path, neighbours };
    },

    select(id, emit = true) {
      this.selected = id || null;
      if (emit) this.emit('select', this.describe(id));
    },

    focus(id) { this.focusId = id || null; },

    setLayer(name, value) { this.layers[name] = value; },

    setPhase(phase) { this.phase = phase || ''; }
  });
})();
