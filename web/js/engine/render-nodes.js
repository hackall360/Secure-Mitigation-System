// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · engine/render-nodes.js — Rendering: target nodes and their labels.
// Mixin: methods are added to SMS.SpiderGraph.prototype. Load after engine/graph.js.
'use strict';
(() => {
  const SMS = window.SMS;
  const { TAU, MONO, clamp, easeOut, glowSprite } = SMS.engine;
  const P = () => SMS.palette;

  Object.assign(SMS.SpiderGraph.prototype, {
    _nodeColor(n) {
      if (n.depth === 0) return this.verdict === 'verified' ? P().TEAMS.purple.hue : this.verdict === 'failed' ? P().TEAMS.red.hue : '#2dd4bf';
      return (P().STATE[n.state] || P().STATE.idle).color;
    },

    _nodeRadius(n) {
      const base = { core: 26, subsystem: 9.5, module: 7, file: 7, function: 5, endpoint: 6.5, sink: 8, data: 7.5, infra: 7, cve: 6, guard: 6, section: 8, import: 4.5, string: 4 };
      return base[n.kind] || this._lensKindRadius(n.kind) || 6;
    },

    _drawNode(ctx, n, S, s, t) {
      if (t < n.born) { n._sx = undefined; return; }
      const age = clamp((t - n.born) / 700, 0, 1);
      const x0 = n.x + this._floatX(n);
      const y0 = n.y + this._floatY(n);
      let [x, y] = S(x0, y0);
      const col = this._nodeColor(n);
      const sel = this.selected === n.id;
      const hov = this.hover && this.hover.id === n.id;
      // compromised nodes glitch-jitter a little
      if (n.state === 'compromised' && !this.reduced && Math.random() < 0.08) { x += (Math.random() - 0.5) * 3; y += (Math.random() - 0.5) * 3; }
      const r = this._nodeRadius(n) * clamp(s, 0.45, 1.6) * (0.4 + 0.6 * easeOut(age));
      n._sx = x; n._sy = y; n._sr = r;

      // glow
      const glowAmt = 0.25 + n.ping * 0.5 + n.heat * 0.6 + (n.state !== 'idle' ? 0.35 : 0) + (sel || hov ? 0.4 : 0);
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      ctx.globalAlpha = clamp(glowAmt, 0, 1) * age;
      const gr = r * (n.depth === 0 ? 3.4 : 4.2);
      ctx.drawImage(glowSprite(col), x - gr, y - gr, gr * 2, gr * 2);
      ctx.restore();

      ctx.save();
      ctx.globalAlpha = age;
      ctx.translate(x, y);
      ctx.lineWidth = sel ? 2.2 : 1.4;
      ctx.strokeStyle = col;
      ctx.fillStyle = '#060b14';
      const pulse = n.state === 'compromised' && !this.reduced ? 1 + Math.sin(t / 140) * 0.08 : 1;
      const R = r * pulse;
      ctx.beginPath();
      switch (n.kind) {
        case 'core': {
          const rot = this.reduced ? 0 : t / 9000;
          this._drawCoreShape(ctx, R, col, rot);   // page / hub / chip / house — engine/lens.js
          // rotating rings around it
          ctx.lineWidth = 1;
          ctx.globalAlpha = age * 0.7;
          ctx.beginPath(); ctx.arc(0, 0, R * 1.35, rot * 2, rot * 2 + Math.PI * 0.6); ctx.stroke();
          ctx.beginPath(); ctx.arc(0, 0, R * 1.35, rot * 2 + Math.PI, rot * 2 + Math.PI * 1.6); ctx.stroke();
          ctx.globalAlpha = age;
          break;
        }
        case 'subsystem':
        case 'section':
          ctx.arc(0, 0, R, 0, TAU); ctx.fill(); ctx.stroke();
          ctx.fillStyle = col; ctx.beginPath(); ctx.arc(0, 0, R * 0.38, 0, TAU); ctx.fill();
          break;
        case 'module':
        case 'file':
          ctx.rect(-R * 0.85, -R * 0.85, R * 1.7, R * 1.7); ctx.fill(); ctx.stroke();
          ctx.fillStyle = col; ctx.fillRect(-R * 0.3, -R * 0.3, R * 0.6, R * 0.6);
          break;
        case 'endpoint': {
          const a = n.angle || 0;
          ctx.rotate(a);
          ctx.moveTo(R * 1.1, 0); ctx.lineTo(-R * 0.7, R * 0.85); ctx.lineTo(-R * 0.7, -R * 0.85); ctx.closePath();
          ctx.fill(); ctx.stroke();
          break;
        }
        case 'sink':
          ctx.moveTo(0, -R * 1.2); ctx.lineTo(R * 1.2, 0); ctx.lineTo(0, R * 1.2); ctx.lineTo(-R * 1.2, 0); ctx.closePath();
          ctx.fill(); ctx.stroke();
          ctx.fillStyle = col; ctx.beginPath(); ctx.arc(0, 0, R * 0.32, 0, TAU); ctx.fill();
          break;
        case 'data':
          ctx.arc(0, 0, R, 0, TAU); ctx.fill(); ctx.stroke();
          ctx.beginPath(); ctx.arc(0, 0, R * 0.6, 0, TAU); ctx.stroke();
          break;
        case 'infra':
          ctx.setLineDash([2, 2]);
          ctx.rect(-R, -R * 0.75, R * 2, R * 1.5); ctx.fill(); ctx.stroke();
          ctx.setLineDash([]);
          break;
        case 'cve': {
          for (let i = 0; i < 8; i += 1) { const a = (i / 8) * TAU; const rr = i % 2 ? R * 0.5 : R * 1.25; ctx[i ? 'lineTo' : 'moveTo'](Math.cos(a) * rr, Math.sin(a) * rr); }
          ctx.closePath(); ctx.fill(); ctx.stroke();
          break;
        }
        default:
          if (this._drawLensKind(ctx, n, R, col)) break;   // dir · host · service · port · config · secret
          ctx.arc(0, 0, R, 0, TAU); ctx.fill(); ctx.stroke();
          ctx.fillStyle = col; ctx.beginPath(); ctx.arc(0, 0, R * 0.42, 0, TAU); ctx.fill();
      }
      // state decorations
      if (n.state === 'compromised' && n.depth > 0) {
        const rot = this.reduced ? 0 : t / 500;
        ctx.strokeStyle = col; ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.arc(0, 0, R * 2.1, rot, rot + 1.1); ctx.stroke();
        ctx.beginPath(); ctx.arc(0, 0, R * 2.1, rot + Math.PI, rot + Math.PI + 1.1); ctx.stroke();
        // crosshair
        ctx.beginPath();
        ctx.moveTo(-R * 2.7, 0); ctx.lineTo(-R * 1.6, 0); ctx.moveTo(R * 1.6, 0); ctx.lineTo(R * 2.7, 0);
        ctx.moveTo(0, -R * 2.7); ctx.lineTo(0, -R * 1.6); ctx.moveTo(0, R * 1.6); ctx.lineTo(0, R * 2.7);
        ctx.stroke();
      } else if (n.state === 'patched' || n.state === 'blocked') {
        ctx.strokeStyle = col; ctx.lineWidth = 1.3;
        ctx.beginPath();
        for (let i = 0; i < 6; i += 1) { const a = (i / 6) * TAU + Math.PI / 6; ctx[i ? 'lineTo' : 'moveTo'](Math.cos(a) * R * 2, Math.sin(a) * R * 2); }
        ctx.closePath(); ctx.stroke();
      } else if (n.state === 'verified' && n.depth > 0) {
        const rot = this.reduced ? Math.PI / 4 : t / 1800;
        ctx.rotate(rot);
        ctx.strokeStyle = col; ctx.lineWidth = 1.3;
        ctx.strokeRect(-R * 1.9, -R * 1.9, R * 3.8, R * 3.8);
      }
      ctx.restore();

      if (sel || hov) {
        const b = r + 9;
        const arm = 5;
        ctx.save();
        ctx.strokeStyle = sel ? '#2dd4bf' : 'rgba(238,244,252,0.85)';
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(([sx, sy]) => {
          ctx.moveTo(x + sx * b, y + sy * (b - arm));
          ctx.lineTo(x + sx * b, y + sy * b);
          ctx.lineTo(x + sx * (b - arm), y + sy * b);
        });
        ctx.stroke();
        ctx.restore();
      }
    },

    _drawLabels(ctx, nodes, S, s, t) {
      const mode = this.layers.labels;
      if (mode === 'none') return;
      ctx.save();
      ctx.textBaseline = 'middle';
      nodes.forEach((n) => {
        if (n._sx === undefined) return;
        const notable = n.state !== 'idle' && n.state !== 'scanned';
        const show = mode === 'all' || n.depth <= 1 || this.selected === n.id || (this.hover && this.hover.id === n.id) || notable || n.heat > 0.3
          || (n.depth === 2 && s > 0.62) || (n.depth >= 3 && s > 1.05);
        if (!show) return;
        const age = t - n.born;
        const reveal = this.reduced ? 1 : clamp(age / 520, 0, 1);
        let text = n.label;
        if (reveal < 1) {
          const k = Math.floor(text.length * reveal);
          text = text.slice(0, k) + (k < text.length ? '█' : '');
        }
        const big = n.depth === 0;
        const fs = big ? clamp(13 * Math.sqrt(s), 11, 15) : clamp(10.5 * Math.sqrt(s), 9, 12);
        ctx.font = `${big || notable ? 700 : 500} ${fs}px ${MONO}`;
        const ang = n.depth === 0 ? Math.PI / 2 : Math.atan2(n.y, n.x);
        const off = n._sr + (big ? 22 : 8);
        const right = Math.cos(ang) >= -0.15;
        let lx = n._sx + Math.cos(ang) * off;
        let ly = n._sy + Math.sin(ang) * off;
        if (big) { lx = n._sx; ly = n._sy + n._sr * 1.6 + 16; }
        ctx.textAlign = big ? 'center' : right ? 'left' : 'right';
        const tw = ctx.measureText(text).width;
        const bx = big ? lx - tw / 2 : right ? lx : lx - tw;
        ctx.globalAlpha = 0.78;
        ctx.fillStyle = '#04080f';
        ctx.fillRect(bx - 4, ly - fs * 0.62, tw + 8, fs * 1.24);
        ctx.globalAlpha = 1;
        const col = this._nodeColor(n);
        ctx.fillStyle = notable || big ? col : n.state === 'idle' ? 'rgba(170,190,215,0.72)' : 'rgba(225,236,250,0.92)';
        ctx.fillText(text, lx, ly);
        if (n.sub && (big || this.selected === n.id || (this.hover && this.hover.id === n.id) || s > 0.9)) {
          ctx.font = `500 ${fs * 0.82}px ${MONO}`;
          ctx.fillStyle = 'rgba(148,168,196,0.6)';
          ctx.fillText(n.sub, lx, ly + fs * 1.15);
        }
      });
      ctx.restore();
    }
  });
})();
