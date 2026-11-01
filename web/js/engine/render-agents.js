// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · engine/render-agents.js — Rendering: agents, working indicator, message bubbles.
// Mixin: methods are added to SMS.SpiderGraph.prototype. Load after engine/graph.js.
'use strict';
(() => {
  const SMS = window.SMS;
  const { TAU, MONO, clamp, easeInOut, glowSprite } = SMS.engine;
  const P = () => SMS.palette;

  Object.assign(SMS.SpiderGraph.prototype, {
    _drawAgents(ctx, S, s, t) {
      const scale = clamp(s, 0.5, 1.3);
      // leader <-> member constellation lines
      ctx.save();
      P().TEAM_ORDER.forEach((team) => {
        if (!this._teamVisible(team)) return;
        const members = [...this.agents.values()].filter((a) => a.team === team);
        const leader = members.find((a) => a.leader);
        if (!leader) return;
        const [lx, ly] = S(leader.x + this._floatX(leader, 5), leader.y + this._floatY(leader, 5));
        members.forEach((m) => {
          if (m === leader) return;
          const [mx, my] = S(m.x + this._floatX(m, 5), m.y + this._floatY(m, 5));
          ctx.strokeStyle = P().rgba(m.color, m.awake ? 0.3 : 0.1);
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(lx, ly); ctx.lineTo(mx, my); ctx.stroke();
        });
      });
      ctx.restore();

      this.agents.forEach((a) => {
        if (!this._teamVisible(a.team)) { a._sx = undefined; return; }
        const [x, y] = S(a.x + this._floatX(a, 5), a.y + this._floatY(a, 5));
        const r = (a.leader ? 15 : 11) * scale;
        a._sx = x; a._sy = y; a._sr = r;
        const since = t - a.speakAt;
        const speaking = since < 1400;
        const sel = this.selected === a.id;
        const hov = this.hover && this.hover.id === a.id;
        const dim = !a.awake && !sel && !hov;

        ctx.save();
        ctx.globalCompositeOperation = 'lighter';
        ctx.globalAlpha = dim ? 0.12 : speaking ? 0.95 : 0.4;
        const gr = r * (speaking ? 4.2 : 3);
        ctx.drawImage(glowSprite(a.color), x - gr, y - gr, gr * 2, gr * 2);
        ctx.restore();

        if (speaking && !this.reduced) {
          const k = since / 1400;
          ctx.strokeStyle = a.color;
          ctx.globalAlpha = (1 - k) * 0.9;
          ctx.lineWidth = 1.5;
          ctx.beginPath(); ctx.arc(x, y, r + 4 + k * 22 * scale, 0, TAU); ctx.stroke();
          ctx.globalAlpha = 1;
        }

        ctx.save();
        ctx.globalAlpha = dim ? 0.45 : 1;
        ctx.fillStyle = '#060a12';
        ctx.strokeStyle = a.color;
        ctx.lineWidth = a.leader ? 2.2 : 1.6;
        ctx.beginPath();
        if (a.leader) {
          for (let i = 0; i < 6; i += 1) { const ang = (i / 6) * TAU; ctx[i ? 'lineTo' : 'moveTo'](x + Math.cos(ang) * r, y + Math.sin(ang) * r); }
          ctx.closePath();
        } else ctx.arc(x, y, r, 0, TAU);
        ctx.fill();
        ctx.stroke();
        // personality tick ring (dashes count = msg activity)
        if (a.msgs > 0) {
          ctx.globalAlpha = dim ? 0.3 : 0.7;
          ctx.lineWidth = 1;
          ctx.setLineDash([2, 3]);
          ctx.beginPath(); ctx.arc(x, y, r + 3.5, -Math.PI / 2, -Math.PI / 2 + TAU * Math.min(1, a.msgs / 12)); ctx.stroke();
          ctx.setLineDash([]);
        }
        ctx.globalAlpha = dim ? 0.55 : 1;
        ctx.fillStyle = a.color;
        ctx.font = `700 ${clamp((a.leader ? 11 : 9) * scale, 7, 13)}px ${MONO}`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(a.glyph, x, y + 0.5);
        // name
        if (s > 0.3) {
          ctx.font = `${a.leader ? 700 : 500} ${clamp(9.5 * scale, 8, 11)}px ${MONO}`;
          ctx.fillStyle = dim ? 'rgba(160,175,200,0.45)' : P().rgba(a.color, 0.95);
          const out = Math.atan2(a.y, a.x);
          const ny = y + r + 10;
          ctx.fillText(a.id.toUpperCase(), x, ny);
          if ((speaking || sel || hov) && s > 0.4) {
            ctx.font = `500 ${clamp(8.5 * scale, 7, 10)}px ${MONO}`;
            ctx.fillStyle = 'rgba(200,214,235,0.7)';
            ctx.fillText(a.personality.toLowerCase(), x, ny + 11);
          }
          void out;
        }
        ctx.restore();

        if (sel || hov) {
          ctx.strokeStyle = sel ? '#2dd4bf' : 'rgba(238,244,252,0.8)';
          ctx.lineWidth = 1.2;
          ctx.beginPath(); ctx.arc(x, y, r + 7, 0, TAU); ctx.stroke();
        }
      });
    },

    _drawWorking(ctx, S, s, t) {
      const w = this.working;
      const a = this.agents.get(w.agent);
      if (!a || a._sx === undefined || !this._teamVisible(a.team)) return;
      const idle = t - w.since;
      const x = a._sx;
      const y = a._sy;
      const r = a._sr + 7;
      const rot = this.reduced ? 0 : t / 380;
      ctx.save();
      ctx.strokeStyle = a.color;
      ctx.lineWidth = 2;
      ctx.globalAlpha = 0.9;
      ctx.beginPath(); ctx.arc(x, y, r, rot, rot + Math.PI * 0.6); ctx.stroke();
      ctx.beginPath(); ctx.arc(x, y, r, rot + Math.PI, rot + Math.PI * 1.6); ctx.stroke();
      if (idle > 2500) {
        const p = w.node ? this._pos(w.node) : null;
        if (p) {
          const [nx, ny] = S(p.x, p.y);
          ctx.globalAlpha = 0.35;
          ctx.lineWidth = 1;
          ctx.setLineDash([3, 5]);
          ctx.lineDashOffset = -(t / 30) % 8;
          ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(nx, ny); ctx.stroke();
          ctx.setLineDash([]);
          const k = this.reduced ? 0.5 : (t % 1600) / 1600;
          ctx.globalAlpha = 0.9;
          ctx.fillStyle = a.color;
          ctx.beginPath(); ctx.arc(x + (nx - x) * k, y + (ny - y) * k, 2.4, 0, TAU); ctx.fill();
          if (!this.reduced && Math.floor(t / 1600) !== this._wPulse) { this._wPulse = Math.floor(t / 1600); this.wave(w.node, a.color, 18, 1); }
        }
        const sec = Math.floor(idle / 1000);
        const label = `WORKING ${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
        ctx.font = `700 ${clamp(9.5 * Math.sqrt(s), 8.5, 11)}px ${MONO}`;
        const tw = ctx.measureText(label).width;
        ctx.globalAlpha = 0.92;
        ctx.fillStyle = 'rgba(4,8,15,0.9)';
        ctx.fillRect(x - tw / 2 - 5, y - r - 20, tw + 10, 15);
        ctx.strokeStyle = a.color;
        ctx.lineWidth = 1;
        ctx.strokeRect(x - tw / 2 - 5, y - r - 20, tw + 10, 15);
        ctx.fillStyle = a.color;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, x, y - r - 12.5);
      }
      ctx.restore();
    },

    _drawPackets(ctx, S, s, t) {
      ctx.save();
      this.packets.forEach((pk) => {
        const k = (t - pk.born) / pk.dur;
        if (k < 0) return;
        const pa = this._pos(pk.from);
        const pb = this._pos(pk.to);
        if (!pa || !pb) return;
        const e = easeInOut(clamp(k, 0, 1));
        // Bubbles arc *through* the web: control point pulled toward the center.
        const mx = (pa.x + pb.x) / 2;
        const my = (pa.y + pb.y) / 2;
        const dx = pb.x - pa.x;
        const dy = pb.y - pa.y;
        const cx = mx * 0.55 - dy * pk.bend;
        const cy = my * 0.55 + dx * pk.bend;
        const at = (u) => { const v = 1 - u; return [v * v * pa.x + 2 * v * u * cx + u * u * pb.x, v * v * pa.y + 2 * v * u * cy + u * u * pb.y]; };

        // faint full route
        ctx.globalAlpha = 0.16 * (1 - clamp(k - 1, 0, 1) * 2);
        ctx.strokeStyle = pk.color;
        ctx.lineWidth = 1;
        ctx.setLineDash([1, 4]);
        ctx.beginPath();
        const [sx0, sy0] = S(pa.x, pa.y);
        ctx.moveTo(sx0, sy0);
        for (let i = 1; i <= 24; i += 1) { const [wx, wy] = at(i / 24); const [qx, qy] = S(wx, wy); ctx.lineTo(qx, qy); }
        ctx.stroke();
        ctx.setLineDash([]);
        if (k > 1) return;

        // comet trail
        ctx.globalCompositeOperation = 'lighter';
        for (let i = 0; i < 10; i += 1) {
          const u = clamp(e - i * 0.018, 0, 1);
          const [wx, wy] = at(u);
          const [qx, qy] = S(wx, wy);
          ctx.globalAlpha = (1 - i / 10) * 0.55;
          const rr = (5 - i * 0.35) * clamp(s, 0.6, 1.3);
          ctx.drawImage(glowSprite(pk.color), qx - rr * 2, qy - rr * 2, rr * 4, rr * 4);
        }
        ctx.globalCompositeOperation = 'source-over';
        const [wx, wy] = at(e);
        const [qx, qy] = S(wx, wy);
        // bubble pill
        if (pk.label) {
          const fs = clamp(10 * Math.sqrt(s), 9, 11.5);
          ctx.font = `600 ${fs}px ${MONO}`;
          const tw = ctx.measureText(pk.label).width;
          const ph = fs + 8;
          const pw = tw + 22;
          const bx = qx - pw / 2;
          const by = qy - ph - 9;
          const fade = clamp(k * 6, 0, 1) * clamp((1 - k) * 8, 0, 1);
          ctx.globalAlpha = 0.92 * fade;
          ctx.fillStyle = 'rgba(4,8,15,0.92)';
          ctx.strokeStyle = pk.color;
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          if (ctx.roundRect) ctx.roundRect(bx, by, pw, ph, ph / 2); else ctx.rect(bx, by, pw, ph);
          ctx.fill(); ctx.stroke();
          // pointer
          ctx.beginPath(); ctx.moveTo(qx - 4, by + ph); ctx.lineTo(qx, by + ph + 5); ctx.lineTo(qx + 4, by + ph); ctx.fillStyle = pk.color; ctx.fill();
          ctx.fillStyle = pk.color;
          ctx.beginPath(); ctx.arc(bx + 9, by + ph / 2, 2.6, 0, TAU); ctx.fill();
          ctx.fillStyle = '#eef4fc';
          ctx.textAlign = 'left';
          ctx.textBaseline = 'middle';
          ctx.fillText(pk.label, bx + 16, by + ph / 2 + 0.5);
        }
        ctx.globalAlpha = 1;
        ctx.fillStyle = '#fff';
        ctx.beginPath(); ctx.arc(qx, qy, 2.2, 0, TAU); ctx.fill();
      });
      ctx.restore();
    }
  });
})();
