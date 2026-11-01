// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · engine/effects.js — Visual effects API: message bubbles, waves, particles, guards, verdicts.
// Mixin: methods are added to SMS.SpiderGraph.prototype. Load after engine/graph.js.
'use strict';
(() => {
  const SMS = window.SMS;
  const { MAX_PACKETS, MAX_PARTICLES, now } = SMS.engine;
  const P = () => SMS.palette;

  Object.assign(SMS.SpiderGraph.prototype, {
    _pos(ref) {
      if (!ref) return null;
      if (typeof ref === 'object' && 'x' in ref) return ref;
      const a = this.agents.get(ref);
      if (a) return { x: a.x + this._floatX(a, 5), y: a.y + this._floatY(a, 5), team: a.team, agent: true };
      const n = this.nodes.get(ref);
      if (n) return { x: n.x + this._floatX(n), y: n.y + this._floatY(n), node: true };
      return null;
    },

    // Communication bubble. from/to: agent id or node id.
    send(from, to, o = {}) {
      if (!this.layers.comms) return;
      const a = this.agents.get(from);
      const team = o.team || (a && a.team) || 'orange';
      if (!this._teamVisible(team)) return;
      const color = o.color || (a && a.color) || P().TEAMS[team].hue;
      if (this.packets.length >= MAX_PACKETS) this.packets.shift();
      // Real-time pacing: streams arrive in bursts and lulls. Bursts are staggered and
      // shortened so bubbles never pile up; a lone event in a quiet stream gets full time.
      const t = now();
      const inflight = this.packets.filter((p) => t >= p.born && t - p.born < p.dur).length;
      const gap = inflight > 10 ? 55 : inflight > 5 ? 100 : 150;
      this.sendCursor = Math.max(this.sendCursor, t);
      const stagger = Math.min(this.sendCursor - t, 1400);
      this.sendCursor += gap;
      const squeeze = inflight > 10 ? 0.55 : inflight > 5 ? 0.78 : 1;
      const dur = ((o.dur || 1500) * squeeze) / (this.reduced ? 3 : 1);
      this.packets.push({ from, to, label: String(o.label || '').slice(0, 30), color, team, born: t + (o.delay || 0) + stagger, dur, bend: o.bend !== undefined ? o.bend : (Math.random() < 0.5 ? -1 : 1) * (0.18 + Math.random() * 0.16), kind: o.kind || 'msg', arrived: false });
      if (a) this.speak(from);
    },

    wave(id, color, max = 46, width = 1.6) {
      const p = typeof id === 'string' ? this._pos(id) : id;
      if (!p) return;
      this.waves.push({ x: p.x, y: p.y, r: 4, max, color, born: now(), dur: 900, width });
      if (this.waves.length > 60) this.waves.shift();
    },

    // Global ping from the center: a ring that expands to the orbit.
    sweepWave(color = '#2dd4bf') {
      this.waves.push({ x: 0, y: 0, r: 10, max: this.orbitRadius() + 40, color, born: now(), dur: 2200, width: 2.2 });
    },

    // Particles along a node path. o.color, o.count, o.speed, o.kind ('flow'|'taint'|'verify')
    flowPath(path, o = {}) {
      if (!this.layers.flow) return;
      const ids = path.filter((id) => this.nodes.has(id));
      if (ids.length < 2) return;
      const count = o.count || 1;
      for (let i = 0; i < count; i += 1) {
        if (this.particles.length >= MAX_PARTICLES) this.particles.shift();
        this.particles.push({ path: ids, seg: 0, t: -i * 0.35, speed: (o.speed || 0.018) * (0.85 + Math.random() * 0.3), color: o.color || '#8fe9ff', kind: o.kind || 'flow', size: o.size || 1.6 });
      }
    },

    guard(a, b, on = true) {
      const l = this.getLink(a, b);
      if (l) { l.guard = on ? 1 : 0; l.guardBorn = now(); }
    },

    heatLink(a, b, color) {
      const l = this.getLink(a, b);
      if (l) { l.heat = 1; l.color = color; }
    },

    setVerdict(v) {
      this.verdict = v || '';
      if (v === 'verified') {
        this.sweepWave(P().TEAMS.purple.hue);
        this.nodes.forEach((n) => { if (n.state === 'compromised' || n.state === 'patched' || n.state === 'blocked') this.setState(n.id, 'verified'); });
        if (this.attackPath.length) this.flowPath(this.attackPath, { color: P().TEAMS.purple.hue, count: 6, speed: 0.02, kind: 'verify', size: 2 });
      } else if (v === 'failed') {
        this.sweepWave(P().TEAMS.red.hue);
      }
    },

    _spark(a, b, at, color) {
      const pa = this._pos(a);
      const pb = this._pos(b);
      if (!pa || !pb) return;
      const p = this._linkPoint(pa, pb, at);
      this.waves.push({ x: p.x, y: p.y, r: 2, max: 16, color, born: now(), dur: 500, width: 1.4 });
    }
  });
})();
