// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · ui/terminal.js — Terminal: typed "stdout" stream of raw orchestrator lines.
// DOM-only, textContent everywhere (no innerHTML), CSP-safe.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const U = (SMS.hud = SMS.hud || {});
  const P = () => SMS.palette;
  const { h, reduced } = U;

  /* ---------------- typed terminal ---------------- */
  class Terminal {
    constructor(root, o = {}) {
      this.root = root;
      this.max = o.max || 60;
      this.queue = [];
      this.busy = false;
      this.prompt = o.prompt || 'sms@sandbox:~$';
      this.root.replaceChildren();
    }
    clear() { this.queue = []; this.root.replaceChildren(); }
    push(team, text) {
      this.queue.push([team, String(text)]);
      if (this.queue.length > 12) this.queue.splice(0, this.queue.length - 12);
      if (!this.busy) this._next();
    }
    _next() {
      const item = this.queue.shift();
      if (!item) { this.busy = false; return; }
      this.busy = true;
      const [team, text] = item;
      const line = h('div', 'tl');
      line.dataset.team = P().family(team);
      line.append(h('span', 'tl-p', `${this.prompt.replace('sandbox', P().family(team))}`), h('span', 'tl-t'));
      const t = line.lastChild;
      const cur = h('span', 'tl-cur', '█');
      line.append(cur);
      this.root.append(line);
      while (this.root.children.length > this.max) this.root.firstChild.remove();
      this.root.scrollTop = this.root.scrollHeight;
      if (reduced()) { t.textContent = text; cur.remove(); this._next(); return; }
      let i = 0;
      const per = Math.max(1, Math.ceil(text.length / (this.queue.length > 3 ? 8 : 26)));
      const tick = () => {
        i = Math.min(text.length, i + per);
        t.textContent = text.slice(0, i);
        this.root.scrollTop = this.root.scrollHeight;
        if (i < text.length) requestAnimationFrame(tick);
        else { cur.remove(); setTimeout(() => this._next(), 40); }
      };
      requestAnimationFrame(tick);
    }
  }

  Object.assign(U, { Terminal });
})();
