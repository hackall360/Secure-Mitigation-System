// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · engine/input.js — Pointer, wheel, resize and hit testing.
// Mixin: methods are added to SMS.SpiderGraph.prototype. Load after engine/graph.js.
'use strict';
(() => {
  const SMS = window.SMS;
  const { clamp } = SMS.engine;

  Object.assign(SMS.SpiderGraph.prototype, {
    _bind() {
      const c = this.canvas;
      this._ro = typeof ResizeObserver === 'function' ? new ResizeObserver(() => this._resize()) : null;
      if (this._ro) this._ro.observe(c);
      else window.addEventListener('resize', () => this._resize());
      const mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
      if (mq && mq.addEventListener) mq.addEventListener('change', () => { this.reduced = mq.matches; });
      document.addEventListener('visibilitychange', () => { if (!document.hidden) this.start(); });
      if (!this.opts.interactive) return;
      c.addEventListener('pointerdown', (e) => {
        this.drag = { x: e.clientX, y: e.clientY, cx: this.camT.x, cy: this.camT.y, moved: false };
        try { c.setPointerCapture(e.pointerId); } catch { /* noop */ }
      });
      c.addEventListener('pointermove', (e) => {
        const r = c.getBoundingClientRect();
        const sx = e.clientX - r.left;
        const sy = e.clientY - r.top;
        if (this.drag) {
          const dx = e.clientX - this.drag.x;
          const dy = e.clientY - this.drag.y;
          if (Math.abs(dx) + Math.abs(dy) > 4) this.drag.moved = true;
          if (this.drag.moved) {
            this.camT.x = this.drag.cx - dx / this.cam.s;
            this.camT.y = this.drag.cy - dy / this.cam.s;
            this.cam.x = this.camT.x; this.cam.y = this.camT.y;
            this.userCam = true;
            c.style.cursor = 'grabbing';
            return;
          }
        }
        const hit = this.hitTest(sx, sy);
        const id = hit ? hit.id : null;
        if (id !== (this.hover && this.hover.id)) {
          this.hover = hit;
          c.style.cursor = hit ? 'pointer' : 'grab';
          this.emit('hover', hit ? Object.assign(this.describe(hit.id) || {}, { sx, sy }) : null);
        } else if (hit) {
          this.emit('hovermove', { sx, sy });
        }
      });
      c.addEventListener('pointerup', (e) => {
        const r = c.getBoundingClientRect();
        const wasDrag = this.drag && this.drag.moved;
        this.drag = null;
        c.style.cursor = this.hover ? 'pointer' : 'grab';
        if (wasDrag) return;
        const hit = this.hitTest(e.clientX - r.left, e.clientY - r.top);
        this.select(hit && (!this.selected || this.selected !== hit.id) ? hit.id : null);
      });
      c.addEventListener('pointerleave', () => {
        this.drag = null;
        if (this.hover) { this.hover = null; this.emit('hover', null); }
      });
      c.addEventListener('wheel', (e) => {
        e.preventDefault();
        const r = c.getBoundingClientRect();
        this.zoomBy(Math.exp(-e.deltaY * 0.0012), e.clientX - r.left, e.clientY - r.top);
      }, { passive: false });
      c.addEventListener('dblclick', (e) => {
        const r = c.getBoundingClientRect();
        const hit = this.hitTest(e.clientX - r.left, e.clientY - r.top);
        if (!hit) { this.fit(); return; }
        const p = this._pos(hit.id);
        if (p) { this.camT.x = p.x; this.camT.y = p.y; this.camT.s = clamp(this.camT.s * 1.6, 0.3, 3.2); this.userCam = true; }
      });
    },

    hitTest(sx, sy) {
      let best = null;
      let bestD = 1e9;
      const test = (id, x, y, r) => {
        const d = Math.hypot(sx - x, sy - y);
        if (d < Math.max(r + 6, 11) && d < bestD) { bestD = d; best = { id }; }
      };
      this.agents.forEach((a) => { if (a._sx !== undefined && this._teamVisible(a.team)) test(a.id, a._sx, a._sy, a._sr); });
      this.nodes.forEach((n) => { if (n._sx !== undefined) test(n.id, n._sx, n._sy, n._sr); });
      return best;
    },

    _resize() {
      const r = this.canvas.getBoundingClientRect();
      const dpr = clamp(window.devicePixelRatio || 1, 1, 2);
      const w = Math.max(10, Math.round(r.width));
      const h = Math.max(10, Math.round(r.height));
      if (w === this.w && h === this.h && dpr === this.dpr) return;
      const first = !this.w;
      this.w = w; this.h = h; this.dpr = dpr;
      this.canvas.width = Math.round(w * dpr);
      this.canvas.height = Math.round(h * dpr);
      this._viewCenter();
      if (first || !this.userCam) this.fit(first);
    }
  });
})();
