// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · engine/render-scene.js — Rendering: frame orchestration, spider web background, links, guards.
// Mixin: methods are added to SMS.SpiderGraph.prototype. Load after engine/graph.js.
'use strict';
(() => {
  const SMS = window.SMS;
  const { TAU, MONO, clamp, lerp, easeOut, glowSprite } = SMS.engine;
  const P = () => SMS.palette;

  Object.assign(SMS.SpiderGraph.prototype, {
    _linkPoint(pa, pb, t, bendSign = 1) {
      // Quadratic curve with the control point nudged perpendicular -> web strands, not sticks.
      const mx = (pa.x + pb.x) / 2;
      const my = (pa.y + pb.y) / 2;
      const dx = pb.x - pa.x;
      const dy = pb.y - pa.y;
      const cx = mx - dy * 0.12 * bendSign;
      const cy = my + dx * 0.12 * bendSign;
      const u = 1 - t;
      return { x: u * u * pa.x + 2 * u * t * cx + t * t * pb.x, y: u * u * pa.y + 2 * u * t * cy + t * t * pb.y, cx, cy };
    },

    _draw(t) {
      const ctx = this.ctx;
      const { w, h, dpr } = this;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const s = this.cam.s;
      const S = (x, y) => [(x - this.cam.x) * s + this.vx0, (y - this.cam.y) * s + this.vy0];
      const [ox, oy] = S(0, 0);

      if (this.layers.web) this._drawWeb(ctx, ox, oy, s, t);

      // ---- links
      ctx.lineCap = 'round';
      this.links.forEach((l) => {
        const a = this.nodes.get(l.a);
        const b = this.nodes.get(l.b);
        if (!a || !b || t < b.born) return;
        const pa = { x: a.x + this._floatX(a), y: a.y + this._floatY(a) };
        const pb = { x: b.x + this._floatX(b), y: b.y + this._floatY(b) };
        const age = clamp((t - b.born) / 900, 0, 1);
        const mid = this._linkPoint(pa, pb, 0.5);
        const [x1, y1] = S(pa.x, pa.y);
        const [x2, y2] = S(pb.x, pb.y);
        const [cx, cy] = S(mid.cx, mid.cy);
        const stateCol = (P().STATE[b.state] || P().STATE.idle).color;
        const hot = l.heat > 0.05;
        ctx.globalAlpha = (l.kind === 'tree' ? 0.22 : 0.3) * age + (hot ? 0.5 * l.heat : 0) + (b.state !== 'idle' ? 0.18 : 0);
        ctx.strokeStyle = hot ? l.color || stateCol : (b.state === 'idle' ? '#5f7896' : stateCol);
        ctx.lineWidth = (l.kind === 'tree' ? 1 : 1.2) + (hot ? 1.4 * l.heat : 0);
        if (l.kind === 'call') ctx.setLineDash([3, 5]); else ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        // Draw the line growing out from the parent while the child is being born.
        if (age < 1) {
          const end = this._linkPoint(pa, pb, easeOut(age));
          const [ex, ey] = S(end.x, end.y);
          ctx.quadraticCurveTo(lerp(x1, cx, age), lerp(y1, cy, age), ex, ey);
        } else ctx.quadraticCurveTo(cx, cy, x2, y2);
        ctx.stroke();
        ctx.setLineDash([]);
        if (l.guard) this._drawGuard(ctx, pa, pb, S, t, l);
      });
      ctx.globalAlpha = 1;

      // ---- tethers (agent focus lines)
      ctx.save();
      this.tethers.forEach((x) => {
        const a = this.agents.get(x.agent);
        if (!a || !this._teamVisible(a.team)) return;
        const pa = this._pos(x.agent);
        const pb = this._pos(x.node);
        if (!pa || !pb) return;
        const life = clamp((x.until - t) / 600, 0, 1) * clamp((t - x.born) / 300, 0, 1);
        const [x1, y1] = S(pa.x, pa.y);
        const [x2, y2] = S(pb.x, pb.y);
        ctx.globalAlpha = 0.55 * life;
        ctx.strokeStyle = x.color;
        ctx.lineWidth = 1.1;
        ctx.setLineDash([2, 6]);
        ctx.lineDashOffset = -(t / 40) % 8;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      });
      ctx.restore();

      // ---- additive layer: particles, glows
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      this.particles.forEach((p) => {
        if (p.t < 0) return;
        const a = this._pos(p.path[p.seg]);
        const b = this._pos(p.path[p.seg + 1]);
        if (!a || !b) return;
        const bend = this.getLink(p.path[p.seg], p.path[p.seg + 1]) && this.linkIndex.has(`${p.path[p.seg]}>${p.path[p.seg + 1]}`) ? 1 : -1;
        const pt = this._linkPoint(a, b, clamp(p.t, 0, 1), bend);
        const tail = this._linkPoint(a, b, clamp(p.t - 0.09, 0, 1), bend);
        const [px, py] = S(pt.x, pt.y);
        const [tx, ty] = S(tail.x, tail.y);
        ctx.globalAlpha = p.kind === 'flow' ? 0.5 : 0.9;
        ctx.strokeStyle = p.color;
        ctx.lineWidth = p.size;
        ctx.beginPath();
        ctx.moveTo(tx, ty);
        ctx.lineTo(px, py);
        ctx.stroke();
        const g = glowSprite(p.color);
        const r = (p.kind === 'flow' ? 7 : 12) * clamp(s, 0.6, 1.4);
        ctx.globalAlpha = p.kind === 'flow' ? 0.55 : 1;
        ctx.drawImage(g, px - r, py - r, r * 2, r * 2);
      });
      ctx.restore();

      // ---- waves
      this.waves.forEach((wv) => {
        const k = (t - wv.born) / wv.dur;
        if (k < 0) return;
        const e = easeOut(k);
        const [x, y] = S(wv.x, wv.y);
        ctx.globalAlpha = (1 - k) * 0.85;
        ctx.strokeStyle = wv.color;
        ctx.lineWidth = wv.width;
        ctx.beginPath();
        ctx.arc(x, y, (wv.r + (wv.max - wv.r) * e) * s, 0, TAU);
        ctx.stroke();
      });
      ctx.globalAlpha = 1;

      // ---- nodes
      const nodesSorted = [...this.nodes.values()].sort((a, b) => b.depth - a.depth);
      nodesSorted.forEach((n) => this._drawNode(ctx, n, S, s, t));

      // ---- agents
      if (this.opts.agents) this._drawAgents(ctx, S, s, t);

      if (this.working) this._drawWorking(ctx, S, s, t);

      // ---- packets (bubbles) on top
      this._drawPackets(ctx, S, s, t);

      // ---- labels last so they sit above everything
      this._drawLabels(ctx, nodesSorted, S, s, t);
    },

    _drawWeb(ctx, ox, oy, s, t) {
      const maxR = this.ringRadius(this.maxDepth) + 40;
      const orbit = this.orbitRadius();
      const spokes = 24;
      ctx.save();
      // Center halo
      const halo = ctx.createRadialGradient(ox, oy, 0, ox, oy, orbit * s);
      halo.addColorStop(0, 'rgba(45,212,191,0.07)');
      halo.addColorStop(0.5, 'rgba(56,120,200,0.03)');
      halo.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = halo;
      ctx.fillRect(0, 0, this.w, this.h);

      // What kind of target this is: page / city / machine / house (engine/lens.js)
      this._drawLensBackdrop(ctx, ox, oy, s, t);

      // Spokes
      ctx.strokeStyle = 'rgba(148,178,214,0.07)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i < spokes; i += 1) {
        const a = (i / spokes) * TAU;
        ctx.moveTo(ox + Math.cos(a) * 22 * s, oy + Math.sin(a) * 22 * s);
        ctx.lineTo(ox + Math.cos(a) * orbit * s, oy + Math.sin(a) * orbit * s);
      }
      ctx.stroke();

      // Web rings: straight-ish strands between spokes that sag toward the center.
      for (let d = 1; d <= this.maxDepth; d += 1) {
        const r = this.ringRadius(d);
        ctx.strokeStyle = `rgba(148,178,214,${0.1 - d * 0.012})`;
        ctx.setLineDash(d === this.maxDepth ? [2, 6] : []);
        ctx.beginPath();
        for (let i = 0; i <= spokes; i += 1) {
          const a = (i / spokes) * TAU;
          const x = ox + Math.cos(a) * r * s;
          const y = oy + Math.sin(a) * r * s;
          if (i === 0) ctx.moveTo(x, y);
          else {
            const am = ((i - 0.5) / spokes) * TAU;
            const sag = r * 0.955;
            ctx.quadraticCurveTo(ox + Math.cos(am) * sag * s, oy + Math.sin(am) * sag * s, x, y);
          }
        }
        ctx.stroke();
        // ring tick label
        ctx.setLineDash([]);
        if (s > 0.32) {
          ctx.fillStyle = 'rgba(148,178,214,0.32)';
          ctx.font = `600 9px ${MONO}`;
          ctx.textAlign = 'left';
          ctx.fillText(this._ringLabel(d), ox + 6, oy - r * s - 4);
        }
      }
      ctx.setLineDash([]);

      // Orbit for agents
      if (this.opts.agents) {
        ctx.strokeStyle = 'rgba(148,178,214,0.06)';
        ctx.setLineDash([1, 7]);
        ctx.beginPath();
        ctx.arc(ox, oy, orbit * s, 0, TAU);
        ctx.stroke();
        ctx.setLineDash([]);
        // family arcs
        P().TEAM_ORDER.forEach((team) => {
          if (!this._teamVisible(team)) return;
          const T = P().TEAMS[team];
          const members = [...this.agents.values()].filter((a) => a.team === team);
          const n = members.length;
          const half = ((n - 1) / 2) * 0.115 + 0.08;
          const awake = members.some((a) => a.awake);
          ctx.strokeStyle = P().rgba(T.hue, awake ? 0.38 : 0.14);
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(ox, oy, (orbit - 46) * s, T.angle - half, T.angle + half);
          ctx.stroke();
          // family label outside the arc
          if (s > 0.25) {
            const lr = (orbit + 118) * s;
            const lx = ox + Math.cos(T.angle) * lr;
            const ly = oy + Math.sin(T.angle) * lr;
            ctx.font = `700 ${clamp(10 * s * 1.4, 8, 11)}px ${MONO}`;
            ctx.textAlign = Math.cos(T.angle) > 0.3 ? 'left' : Math.cos(T.angle) < -0.3 ? 'right' : 'center';
            ctx.fillStyle = P().rgba(T.hue, awake ? 0.85 : 0.4);
            ctx.fillText(this._familyLabel(T), lx, ly + 3);
          }
        });
      }

      // Radar sweep
      if (!this.reduced && this.layers.sweep && typeof ctx.createConicGradient === 'function') {
        const a = this.sweepA;
        const g = ctx.createConicGradient(a - 0.9, ox, oy);
        g.addColorStop(0, 'rgba(45,212,191,0)');
        g.addColorStop(0.142, 'rgba(45,212,191,0.085)');
        g.addColorStop(0.1433, 'rgba(45,212,191,0)');
        g.addColorStop(1, 'rgba(45,212,191,0)');
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.moveTo(ox, oy);
        ctx.arc(ox, oy, maxR * s, a - 0.9, a);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = 'rgba(45,212,191,0.28)';
        ctx.beginPath();
        ctx.moveTo(ox, oy);
        ctx.lineTo(ox + Math.cos(a) * maxR * s, oy + Math.sin(a) * maxR * s);
        ctx.stroke();
      }
      ctx.restore();
    },

    _drawGuard(ctx, pa, pb, S, t, l) {
      const p = this._linkPoint(pa, pb, 0.62);
      const [x, y] = S(p.x, p.y);
      const age = clamp((t - (l.guardBorn || 0)) / 700, 0, 1);
      const r = (6 + 4 * (1 - age)) * clamp(this.cam.s, 0.7, 1.4);
      const blue = P().TEAMS.blue.hue;
      const col = this.verdict === 'verified' ? P().TEAMS.purple.hue : blue;
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      ctx.drawImage(glowSprite(col), x - r * 2.4, y - r * 2.4, r * 4.8, r * 4.8);
      ctx.restore();
      ctx.save();
      ctx.translate(x, y);
      ctx.fillStyle = '#04101c';
      ctx.strokeStyle = col;
      ctx.lineWidth = 1.6;
      // shield hexagon
      ctx.beginPath();
      for (let i = 0; i < 6; i += 1) {
        const a = (i / 6) * TAU + Math.PI / 6;
        ctx[i ? 'lineTo' : 'moveTo'](Math.cos(a) * r, Math.sin(a) * r);
      }
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(-r * 0.4, 0);
      ctx.lineTo(-r * 0.05, r * 0.35);
      ctx.lineTo(r * 0.45, -r * 0.35);
      ctx.stroke();
      ctx.restore();
    }
  });
})();
