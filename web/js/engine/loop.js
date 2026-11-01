// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · engine/loop.js — Animation loop and simulation step (physics, sweep, particles, packets).
// Mixin: methods are added to SMS.SpiderGraph.prototype. Load after engine/graph.js.
'use strict';
(() => {
  const SMS = window.SMS;
  const { TAU, now, clamp } = SMS.engine;
  const P = () => SMS.palette;

  Object.assign(SMS.SpiderGraph.prototype, {
    start() {
      if (this.running) return;
      this.running = true;
      const loop = () => {
        if (!this.running) return;
        if (document.hidden) { this.running = false; return; }
        this.frame();
        this.raf = requestAnimationFrame(loop);
      };
      this.raf = requestAnimationFrame(loop);
    },

    stop() { this.running = false; cancelAnimationFrame(this.raf); },

    destroy() { this.stop(); if (this._ro) this._ro.disconnect(); },

    _floatX(n, amp) { if (this.reduced) return 0; const a = amp !== undefined ? amp : 2 + n.depth * 2.2; return Math.sin(this.time * 0.00052 + n.phase) * a; },

    _floatY(n, amp) { if (this.reduced) return 0; const a = amp !== undefined ? amp : 2 + n.depth * 2.2; return Math.cos(this.time * 0.00043 + n.phase * 1.3) * a; },

    frame() {
      const t = now();
      const dt = clamp(t - this.last, 0, 64);
      this.last = t;
      this.time = t - this.t0;
      this._step(dt, t);
      this._camera();
      this._draw(t);
    },

    _step(dt, t) {
      const k = dt / 16.67;
      const arr = [...this.nodes.values()];
      // Spring toward radial home + short-range repulsion keeps the web organic.
      for (let i = 0; i < arr.length; i += 1) {
        const n = arr[i];
        if (n.depth === 0) { n.x = 0; n.y = 0; continue; }
        if (t < n.born) continue;
        const age = t - n.born;
        const stiff = age < 1800 ? 0.022 : 0.03;
        n.vx += (n.hx - n.x) * stiff * k;
        n.vy += (n.hy - n.y) * stiff * k;
        for (let j = i + 1; j < arr.length; j += 1) {
          const m = arr[j];
          if (m.depth === 0) continue;
          const dx = n.x - m.x;
          const dy = n.y - m.y;
          const d2 = dx * dx + dy * dy;
          if (d2 > 2600 || d2 < 0.01) continue;
          const d = Math.sqrt(d2);
          const f = ((51 - d) / d) * 0.04 * k;
          n.vx += dx * f; n.vy += dy * f;
          m.vx -= dx * f; m.vy -= dy * f;
        }
      }
      const damp = Math.pow(0.84, k);
      arr.forEach((n) => {
        if (n.depth === 0 || t < n.born) return;
        n.vx *= damp; n.vy *= damp;
        n.x += n.vx * k; n.y += n.vy * k;
        n.ping = Math.max(0, n.ping - 0.02 * k);
        n.heat = Math.max(0, n.heat - 0.008 * k);
      });
      this.agents.forEach((a) => {
        a.x += (a.hx - a.x) * 0.06 * k;
        a.y += (a.hy - a.y) * 0.06 * k;
      });
      this.links.forEach((l) => { l.heat = Math.max(0, l.heat - 0.006 * k); });

      // Radar sweep + node ping when the beam crosses them.
      if (!this.reduced && this.layers.sweep) {
        const prev = this.sweepA;
        this.sweepA += 0.0105 * k;
        const norm = (a) => ((a % TAU) + TAU) % TAU;
        const p0 = norm(prev);
        const p1 = norm(this.sweepA);
        arr.forEach((n) => {
          if (n.depth === 0) return;
          const a = norm(Math.atan2(n.y, n.x));
          const crossed = p0 <= p1 ? a > p0 && a <= p1 : a > p0 || a <= p1;
          if (crossed) n.ping = 1;
        });
      }

      // Ambient program data-flow: a particle down each flow path every ~1.1s.
      this.flowClock += dt;
      if (this.flowClock > 1100 && this.flows.length) {
        this.flowClock = 0;
        this.flows.forEach((f) => {
          if (f.some((id) => (this.nodes.get(id) || {}).born > t)) return;
          this.flowPath(f, { color: '#8fe9ff', speed: 0.014, size: 1.3 });
        });
      }

      // Particles
      this.particles.forEach((p) => {
        p.t += p.speed * k;
        if (p.t < 0) return;
        const a = p.path[p.seg];
        const b = p.path[p.seg + 1];
        const l = this.getLink(a, b);
        if (l && l.guard && p.kind !== 'verify' && p.t >= 0.62) {
          p.dead = true;
          p.blockedAt = { a, b };
          this._spark(a, b, 0.62, P().TEAMS.blue.hue);
          return;
        }
        if (l && p.kind === 'taint') { l.heat = Math.max(l.heat, 0.9); l.color = p.color; }
        if (p.t >= 1) {
          p.t = 0;
          p.seg += 1;
          const reached = this.nodes.get(p.path[p.seg]);
          if (reached) reached.ping = Math.max(reached.ping, p.kind === 'flow' ? 0.45 : 1);
          if (p.seg >= p.path.length - 1) {
            p.dead = true;
            if (p.kind !== 'flow') this.wave(p.path[p.path.length - 1], p.color, 22, 1.2);
          }
        }
      });
      this.particles = this.particles.filter((p) => !p.dead);

      this.packets.forEach((pk) => {
        const age = (t - pk.born) / pk.dur;
        if (age >= 1 && !pk.arrived) {
          pk.arrived = true;
          this.wave(pk.to, pk.color, 22, 1.3);
          const ag = this.agents.get(pk.to);
          if (ag) { ag.awake = true; ag.recvAt = t; }
          const nd = this.nodes.get(pk.to);
          if (nd) nd.ping = 1;
        }
      });
      this.packets = this.packets.filter((pk) => t - pk.born < pk.dur + 450);
      this.waves = this.waves.filter((w) => t - w.born < w.dur);
      this.tethers = this.tethers.filter((x) => t < x.until);
    }
  });
})();
