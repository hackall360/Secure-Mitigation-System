// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · ui/stage-bar.js — StageBar: the seven verification phases (sandbox … cleanup).
// DOM-only, textContent everywhere (no innerHTML), CSP-safe.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const U = (SMS.hud = SMS.hud || {});
  const P = () => SMS.palette;
  const { h } = U;

  /* ---------------- stage bar ---------------- */
  class StageBar {
    constructor(root, o = {}) {
      this.root = root;
      this.onPick = o.onPick || null;
      this.root.replaceChildren();
      P().STAGES.forEach((s) => {
        const m = P().STAGE_META[s];
        const li = h('li', 'stg');
        li.dataset.stage = s;
        li.style.setProperty('--c', P().TEAMS[m.team].hue);
        li.append(h('span', 'stg-n', m.n), h('span', 'stg-l', m.label), h('i', 'stg-bar', null, { 'aria-hidden': 'true' }));
        li.title = m.caption;
        if (this.onPick) { li.tabIndex = 0; li.addEventListener('click', () => this.onPick(s)); }
        this.root.append(li);
      });
    }
    reset() { this.root.querySelectorAll('.stg').forEach((n) => { delete n.dataset.state; }); }
    set(stage) {
      const idx = P().STAGES.indexOf(stage);
      this.root.querySelectorAll('.stg').forEach((n, i) => {
        if (i < idx) n.dataset.state = 'done';
        else if (i === idx) n.dataset.state = 'active';
        else delete n.dataset.state;
      });
    }
    finish(ok) {
      this.root.querySelectorAll('.stg').forEach((n) => {
        if (n.dataset.state === 'active') n.dataset.state = ok ? 'done' : 'failed';
        else if (!n.dataset.state) n.dataset.state = 'skipped';
      });
    }
    inspect(stage) { this.root.querySelectorAll('.stg').forEach((n) => n.classList.toggle('inspect', n.dataset.stage === stage)); }
  }

  Object.assign(U, { StageBar });
})();
