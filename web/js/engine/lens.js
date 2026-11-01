// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · engine/lens.js — lens-specific drawing: what makes a single file, a repository,
// a binary and a system snapshot LOOK different on the same spider map.
//
//   file    ruled notebook page clipped to the web + a slow "reading line"; page-shaped core
//   repo    folder districts (one wedge per top-level dir) with names on the rim; hub core
//   binary  rotating address ruler + section bands (a memory map); chip core with pins
//   system  rooms (one wedge per host) + a brick perimeter wall with a DOOR per public port; house core
//
// Mixin: methods are added to SMS.SpiderGraph.prototype. Load after engine/graph.js.
// Called from render-scene.js (_drawLensBackdrop, _ringLabel) and render-nodes.js (_drawCoreShape, _drawLensKind).
'use strict';
(() => {
  const SMS = window.SMS;
  const { TAU, MONO, RING0, clamp } = SMS.engine;
  const P = () => SMS.palette;
  const Ls = () => SMS.lenses;

  Object.assign(SMS.SpiderGraph.prototype, {
    setLens(key) { this.lens = Ls().LENSES[key] ? key : 'file'; },
    setExplain(level) { this.explain = level; },
    _lensAccent() { return Ls().get(this.lens || 'file').accent; },

    _ringLabel(d) {
      const r = Ls().ring(this.lens || 'file', d);
      const lv = this.explain || 'expert';
      if (lv === 'simple') return r.simple.toUpperCase();
      if (lv === 'both') return `R${d} · ${r.expert} — ${r.simple.toLowerCase()}`;
      return `R${d} · ${r.expert}`;
    },

    _familyLabel(T) {
      const lv = this.explain || 'expert';
      if (lv === 'simple') return T.kidShort || T.short;
      if (lv === 'both' && T.kidShort) return `${T.short} · ${T.kidShort}`;
      return T.short;
    },

    /* ---------------- backdrops ---------------- */
    _drawLensBackdrop(ctx, ox, oy, s, t) {
      const fn = { file: this._bgPage, repo: this._bgDistricts, binary: this._bgMemory, system: this._bgHouse }[this.lens || 'file'];
      if (fn) { ctx.save(); fn.call(this, ctx, ox, oy, s, t); ctx.restore(); }
    },

    // A ruled page: notebook lines, a margin rule with line numbers, a slow reading cursor.
    _bgPage(ctx, ox, oy, s, t) {
      const acc = this._lensAccent();
      const R = (this.ringRadius(this.maxDepth) + 40) * s;
      ctx.beginPath();
      ctx.arc(ox, oy, R, 0, TAU);
      ctx.clip();
      const gap = Math.max(9, 24 * s);
      const top = oy - R;
      const n = Math.ceil((2 * R) / gap);
      ctx.strokeStyle = P().rgba(acc, 0.05);
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i <= n; i += 1) { const y = top + i * gap; ctx.moveTo(ox - R, y); ctx.lineTo(ox + R, y); }
      ctx.stroke();
      const mx = ox - R * 0.64;
      ctx.strokeStyle = P().rgba(acc, 0.16);
      ctx.beginPath(); ctx.moveTo(mx, top); ctx.lineTo(mx, oy + R); ctx.stroke();
      if (s > 0.38) {
        ctx.fillStyle = P().rgba(acc, 0.22);
        ctx.font = `500 ${clamp(8.5 * s * 1.3, 7, 10)}px ${MONO}`;
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        for (let i = 0; i < n; i += 1) ctx.fillText(String(i + 1).padStart(3, '0'), mx - 6, top + (i + 0.5) * gap);
      }
      if (!this.reduced) {
        const y = top + ((t / 55) % (2 * R));
        const g = ctx.createLinearGradient(0, y - gap, 0, y + gap);
        g.addColorStop(0, P().rgba(acc, 0));
        g.addColorStop(0.5, P().rgba(acc, 0.07));
        g.addColorStop(1, P().rgba(acc, 0));
        ctx.fillStyle = g;
        ctx.fillRect(ox - R, y - gap, 2 * R, 2 * gap);
      }
    },

    // Wedges behind each top-level child of the root (folders in a repo, rooms in a house).
    _wedges(ctx, ox, oy, s, o) {
      const acc = this._lensAccent();
      const root = this.nodes.get(this._rootId());
      if (!root) return;
      const kids = root.children.map((id) => this.nodes.get(id)).filter((n) => n && n.a0 !== undefined && n.born <= o.t);
      const r0 = RING0 * o.inner * s;
      const r1 = (this.ringRadius(this.maxDepth) + o.outer) * s;
      kids.forEach((n, i) => {
        const pad = Math.min(0.03, (n.a1 - n.a0) * 0.1);
        const a0 = n.a0 + pad;
        const a1 = n.a1 - pad;
        if (a1 <= a0) return;
        const hot = n.state === 'compromised' || (this.focusId && this._ancestor(this.focusId) === n.id);
        ctx.beginPath();
        ctx.arc(ox, oy, r1, a0, a1);
        ctx.arc(ox, oy, r0, a1, a0, true);
        ctx.closePath();
        ctx.fillStyle = P().rgba(n.kind === 'infra' || n.id === 'sandbox' ? '#fb923c' : acc, (i % 2 ? 0.028 : 0.045) + (hot ? 0.035 : 0));
        ctx.fill();
        ctx.strokeStyle = P().rgba(acc, hot ? 0.3 : 0.13);
        ctx.lineWidth = 1;
        if (o.dash) ctx.setLineDash(o.dash);
        ctx.stroke();
        ctx.setLineDash([]);
        if (s > 0.3) {
          const mid = (a0 + a1) / 2;
          // Inside the rim, reading inward, so names never collide with the agent orbit.
          const lr = r1 - 9;
          const c = Math.cos(mid);
          ctx.font = `700 ${clamp(9 * s * 1.4, 8, 11)}px ${MONO}`;
          ctx.textAlign = c > 0.25 ? 'right' : c < -0.25 ? 'left' : 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = P().rgba(acc, hot ? 0.9 : 0.5);
          ctx.fillText(`${o.prefix}${n.label}`.toUpperCase().slice(0, 26), ox + c * lr, oy + Math.sin(mid) * lr);
        }
      });
    },

    _ancestor(id) {
      let n = this.nodes.get(id);
      while (n && n.depth > 1) n = this.nodes.get(n.parent);
      return n ? n.id : null;
    },

    _bgDistricts(ctx, ox, oy, s, t) {
      this._wedges(ctx, ox, oy, s, { t, inner: 0.55, outer: 30, prefix: '▣ ' });
    },

    // Memory map: a slowly turning address ruler + a band per section.
    _bgMemory(ctx, ox, oy, s, t) {
      const acc = this._lensAccent();
      const rr = (this.ringRadius(this.maxDepth) + 34) * s;
      const rot = this.reduced ? 0 : t / 90000;
      ctx.strokeStyle = P().rgba(acc, 0.2);
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i < 180; i += 1) {
        const a = rot + (i / 180) * TAU;
        const len = (i % 15 === 0 ? 8 : i % 5 === 0 ? 5 : 2.5) * clamp(s * 1.4, 0.6, 1.4);
        ctx.moveTo(ox + Math.cos(a) * rr, oy + Math.sin(a) * rr);
        ctx.lineTo(ox + Math.cos(a) * (rr + len), oy + Math.sin(a) * (rr + len));
      }
      ctx.stroke();
      ctx.beginPath(); ctx.arc(ox, oy, rr, 0, TAU); ctx.strokeStyle = P().rgba(acc, 0.08); ctx.stroke();
      if (s > 0.35) {
        ctx.fillStyle = P().rgba(acc, 0.32);
        ctx.font = `500 ${clamp(8 * s * 1.3, 7, 9.5)}px ${MONO}`;
        ctx.textBaseline = 'middle';
        for (let i = 0; i < 12; i += 1) {
          const a = rot + (i / 12) * TAU;
          const c = Math.cos(a);
          ctx.textAlign = c > 0.25 ? 'left' : c < -0.25 ? 'right' : 'center';
          ctx.fillText(`0x${(0x401000 + i * 0x2a0).toString(16)}`, ox + c * (rr + 16), oy + Math.sin(a) * (rr + 16));
        }
      }
      const root = this.nodes.get(this._rootId());
      if (!root) return;
      const band = Math.max(2, 7 * s);
      root.children.map((id) => this.nodes.get(id)).forEach((n) => {
        if (!n || n.a0 === undefined) return;
        ctx.beginPath();
        ctx.arc(ox, oy, (RING0 - 34) * s, n.a0 + 0.025, n.a1 - 0.025);
        ctx.lineWidth = band;
        ctx.strokeStyle = P().rgba(n.kind === 'section' ? acc : n.kind === 'infra' || n.id === 'sandbox' ? '#fb923c' : '#8fe9ff', n.kind === 'section' ? 0.2 : 0.1);
        ctx.stroke();
      });
    },

    // A house: rooms per host and a brick perimeter wall with a door per public port.
    _bgHouse(ctx, ox, oy, s, t) {
      const acc = this._lensAccent();
      this._wedges(ctx, ox, oy, s, { t, inner: 0.5, outer: 18, prefix: '⌂ ', dash: [4, 4] });
      const rw = (this.ringRadius(this.maxDepth) + 52) * s;
      const doors = [...this.nodes.values()].filter((n) => (n.kind === 'port' || n.kind === 'endpoint') && n.meta && n.meta.public && n.born <= t)
        .map((n) => ({ n, a: Math.atan2(n.y, n.x) })).sort((a, b) => a.a - b.a);
      const half = 0.075;
      // wall segments between doors
      ctx.lineWidth = Math.max(2, 5 * s);
      ctx.strokeStyle = P().rgba(acc, 0.2);
      ctx.setLineDash([Math.max(4, 13 * s), Math.max(2, 4 * s)]);
      if (!doors.length) { ctx.beginPath(); ctx.arc(ox, oy, rw, 0, TAU); ctx.stroke(); }
      doors.forEach((d, i) => {
        const nx = doors[(i + 1) % doors.length];
        let end = nx.a - half;
        if (end <= d.a + half) end += TAU;
        ctx.beginPath();
        ctx.arc(ox, oy, rw, d.a + half, end);
        ctx.stroke();
      });
      ctx.setLineDash([]);
      // doors: an arch in the gap + a dashed path to the port it leads to
      doors.forEach(({ n, a }) => {
        const col = this._nodeColor(n);
        const x = ox + Math.cos(a) * rw;
        const y = oy + Math.sin(a) * rw;
        const sz = Math.max(5, 9 * s);
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(a + Math.PI / 2);
        ctx.strokeStyle = col;
        ctx.fillStyle = '#04080f';
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.moveTo(-sz * 0.7, sz * 0.8);
        ctx.lineTo(-sz * 0.7, -sz * 0.1);
        ctx.arc(0, -sz * 0.1, sz * 0.7, Math.PI, 0);
        ctx.lineTo(sz * 0.7, sz * 0.8);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.restore();
        const sx = n._sx;
        const sy = n._sy;
        if (sx !== undefined) {
          ctx.strokeStyle = P().rgba(col, 0.35);
          ctx.lineWidth = 1;
          ctx.setLineDash([2, 4]);
          ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(sx, sy); ctx.stroke();
          ctx.setLineDash([]);
        }
      });
      if (s > 0.3) {
        ctx.font = `700 ${clamp(9 * s * 1.4, 8, 11)}px ${MONO}`;
        ctx.textAlign = 'center';
        ctx.fillStyle = P().rgba(acc, 0.45);
        const lv = this.explain || 'expert';
        ctx.fillText(lv === 'simple' ? 'OUTSIDE THE WALL' : lv === 'both' ? 'INTERNET — outside the wall' : 'INTERNET · UNTRUSTED', ox, oy + rw + 18);
        ctx.fillStyle = P().rgba(acc, 0.3);
        ctx.fillText(lv === 'simple' ? 'INSIDE THE HOUSE' : 'PERIMETER', ox, oy + rw - 14);
      }
    },

    /* ---------------- core + lens kinds ---------------- */
    // Outline + inner detail of the center node. ctx is translated to the node; returns nothing.
    _drawCoreShape(ctx, R, col, rot) {
      const lens = this.lens || 'file';
      ctx.beginPath();
      if (lens === 'file') {
        ctx.moveTo(-R * 0.78, -R); ctx.lineTo(R * 0.38, -R); ctx.lineTo(R * 0.78, -R * 0.6); ctx.lineTo(R * 0.78, R); ctx.lineTo(-R * 0.78, R); ctx.closePath();
      } else if (lens === 'binary') {
        ctx.rect(-R * 0.8, -R * 0.8, R * 1.6, R * 1.6);
      } else if (lens === 'system') {
        ctx.moveTo(0, -R * 1.05); ctx.lineTo(R * 0.95, -R * 0.15); ctx.lineTo(R * 0.78, -R * 0.15); ctx.lineTo(R * 0.78, R * 0.9); ctx.lineTo(-R * 0.78, R * 0.9); ctx.lineTo(-R * 0.78, -R * 0.15); ctx.lineTo(-R * 0.95, -R * 0.15); ctx.closePath();
      } else {
        for (let i = 0; i < 6; i += 1) { const a = rot + (i / 6) * TAU; ctx[i ? 'lineTo' : 'moveTo'](Math.cos(a) * R, Math.sin(a) * R); }
        ctx.closePath();
      }
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      if (lens === 'file') {
        ctx.moveTo(R * 0.38, -R); ctx.lineTo(R * 0.38, -R * 0.6); ctx.lineTo(R * 0.78, -R * 0.6);
        [-0.25, 0.05, 0.35, 0.65].forEach((y, i) => { ctx.moveTo(-R * 0.5, R * y); ctx.lineTo(R * (i === 3 ? 0.1 : 0.5), R * y); });
      } else if (lens === 'binary') {
        [-0.45, 0, 0.45].forEach((k) => {
          ctx.moveTo(R * k, -R * 0.8); ctx.lineTo(R * k, -R * 1.1); ctx.moveTo(R * k, R * 0.8); ctx.lineTo(R * k, R * 1.1);
          ctx.moveTo(-R * 0.8, R * k); ctx.lineTo(-R * 1.1, R * k); ctx.moveTo(R * 0.8, R * k); ctx.lineTo(R * 1.1, R * k);
        });
        ctx.rect(-R * 0.4, -R * 0.4, R * 0.8, R * 0.8);
      } else if (lens === 'system') {
        ctx.rect(-R * 0.2, R * 0.3, R * 0.4, R * 0.6);
        ctx.rect(-R * 0.6, -R * 0.05, R * 0.28, R * 0.28);
        ctx.rect(R * 0.32, -R * 0.05, R * 0.28, R * 0.28);
      } else {
        ctx.rect(-R * 0.45, -R * 0.05, R * 0.22, R * 0.45);
        ctx.rect(-R * 0.12, -R * 0.4, R * 0.24, R * 0.8);
        ctx.rect(R * 0.23, -R * 0.2, R * 0.22, R * 0.6);
      }
      ctx.stroke();
    },

    _lensKindRadius(kind) {
      return { dir: 8.5, host: 9, service: 6, port: 6, config: 5.5, secret: 5 }[kind];
    },

    // Shapes for kinds only some lenses use. ctx is translated to the node, path already begun.
    _drawLensKind(ctx, n, R, col) {
      switch (n.kind) {
        case 'dir':
          ctx.moveTo(-R, -R * 0.55); ctx.lineTo(-R * 0.25, -R * 0.55); ctx.lineTo(0, -R * 0.25); ctx.lineTo(R, -R * 0.25); ctx.lineTo(R, R * 0.7); ctx.lineTo(-R, R * 0.7); ctx.closePath();
          ctx.fill(); ctx.stroke();
          return true;
        case 'host':
          ctx.rect(-R, -R * 0.8, R * 2, R * 1.6); ctx.fill(); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(-R * 0.6, -R * 0.25); ctx.lineTo(R * 0.6, -R * 0.25); ctx.moveTo(-R * 0.6, R * 0.25); ctx.lineTo(R * 0.6, R * 0.25); ctx.stroke();
          ctx.fillStyle = col; ctx.beginPath(); ctx.arc(R * 0.62, -R * 0.52, R * 0.12, 0, TAU); ctx.fill();
          return true;
        case 'service': {
          for (let i = 0; i < 12; i += 1) { const a = (i / 12) * TAU; const rr = i % 2 ? R * 0.82 : R * 1.08; ctx[i ? 'lineTo' : 'moveTo'](Math.cos(a) * rr, Math.sin(a) * rr); }
          ctx.closePath(); ctx.fill(); ctx.stroke();
          ctx.fillStyle = col; ctx.beginPath(); ctx.arc(0, 0, R * 0.3, 0, TAU); ctx.fill();
          return true;
        }
        case 'port':
          ctx.moveTo(-R * 0.7, R); ctx.lineTo(-R * 0.7, -R * 0.2); ctx.arc(0, -R * 0.2, R * 0.7, Math.PI, 0); ctx.lineTo(R * 0.7, R); ctx.closePath();
          ctx.fill(); ctx.stroke();
          ctx.fillStyle = col; ctx.beginPath(); ctx.arc(R * 0.35, R * 0.3, R * 0.14, 0, TAU); ctx.fill();
          if (n.meta && n.meta.public) { ctx.beginPath(); ctx.arc(0, -R * 0.2, R * 1.25, Math.PI * 1.15, Math.PI * 1.85); ctx.stroke(); }
          return true;
        case 'config':
          ctx.moveTo(-R * 0.7, -R); ctx.lineTo(R * 0.3, -R); ctx.lineTo(R * 0.7, -R * 0.6); ctx.lineTo(R * 0.7, R); ctx.lineTo(-R * 0.7, R); ctx.closePath();
          ctx.fill(); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(-R * 0.35, -R * 0.1); ctx.lineTo(R * 0.35, -R * 0.1); ctx.moveTo(-R * 0.35, R * 0.35); ctx.lineTo(R * 0.35, R * 0.35); ctx.stroke();
          return true;
        case 'secret':
          ctx.arc(-R * 0.35, 0, R * 0.6, 0, TAU); ctx.fill(); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(R * 0.25, 0); ctx.lineTo(R * 1.1, 0); ctx.moveTo(R * 0.8, 0); ctx.lineTo(R * 0.8, R * 0.4); ctx.stroke();
          return true;
        default:
          return false;
      }
    }
  });
})();
