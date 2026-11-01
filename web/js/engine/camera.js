// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · engine/camera.js — Camera: fit, insets, director follow, zoom, coordinate transforms.
// Mixin: methods are added to SMS.SpiderGraph.prototype. Load after engine/graph.js.
'use strict';
(() => {
  const SMS = window.SMS;
  const { clamp, lerp } = SMS.engine;

  Object.assign(SMS.SpiderGraph.prototype, {
    fit(snap) {
      const R = this.opts.agents ? this.orbitRadius() + 128 : this.ringRadius(this.maxDepth) + 60;
      const s = this._fitScale(R);
      this.camT = { x: 0, y: 0, s };
      this.userCam = false;
      if (snap) this.cam = Object.assign({}, this.camT);
    },

    _fitScale(R) {
      const aw = Math.max(120, this.w - this.insets.l - this.insets.r);
      const ah = Math.max(120, this.h - this.insets.t - this.insets.b);
      return clamp(Math.min(aw, ah) / 2 / R, 0.16, 2.4);
    },

    _viewCenter() {
      const aw = Math.max(120, this.w - this.insets.l - this.insets.r);
      const ah = Math.max(120, this.h - this.insets.t - this.insets.b);
      this.vx0 = this.insets.l + aw / 2;
      this.vy0 = this.insets.t + ah / 2;
    },

    setInsets(ins) {
      this.insets = Object.assign({ l: 0, r: 0, t: 0, b: 0 }, ins);
      this._viewCenter();
      if (!this.userCam) this.fit();
    },

    setDirector(on) { this.director = !!on; if (on) this.userCam = false; },

    zoomBy(f, sx, sy) {
      const wx = (sx - this.vx0) / this.cam.s + this.cam.x;
      const wy = (sy - this.vy0) / this.cam.s + this.cam.y;
      const s = clamp(this.camT.s * f, 0.15, 4);
      this.camT.s = s;
      this.camT.x = wx - (sx - this.vx0) / s;
      this.camT.y = wy - (sy - this.vy0) / s;
      this.cam.s = s; this.cam.x = this.camT.x; this.cam.y = this.camT.y;
      this.userCam = true;
    },

    toScreen(x, y) { return [(x - this.cam.x) * this.cam.s + this.vx0, (y - this.cam.y) * this.cam.s + this.vy0]; },

    toWorld(sx, sy) { return [(sx - this.vx0) / this.cam.s + this.cam.x, (sy - this.vy0) / this.cam.s + this.cam.y]; },

    _camera() {
      if (this.director && !this.userCam) {
        const base = this.opts.agents ? this.orbitRadius() + 128 : this.ringRadius(this.maxDepth) + 60;
        const fitS = this._fitScale(base);
        const f = this.focusId ? this._pos(this.focusId) : null;
        if (f) {
          this.camT.x = f.x * 0.22;
          this.camT.y = f.y * 0.22;
          this.camT.s = fitS * 1.08;
        } else {
          this.camT.x = 0; this.camT.y = 0; this.camT.s = fitS;
        }
      }
      const e = this.reduced ? 1 : 0.045;
      this.cam.x = lerp(this.cam.x, this.camT.x, e);
      this.cam.y = lerp(this.cam.y, this.camT.y, e);
      this.cam.s = lerp(this.cam.s, this.camT.s, e);
    }
  });
})();
