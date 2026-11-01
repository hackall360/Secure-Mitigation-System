// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · ui/legend.js — Legend: the six agent families and their personalities; click a family to filter.
// DOM-only, textContent everywhere (no innerHTML), CSP-safe.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const U = (SMS.hud = SMS.hud || {});
  const P = () => SMS.palette;
  const { h } = U;

  /* ---------------- agent legend ---------------- */
  class Legend {
    constructor(root, graph, o = {}) {
      this.root = root;
      this.g = graph;
      this.onFilter = o.onFilter || null;
      this.compact = !!o.compact;
      this.active = new Set();
      this.counts = new Map();
      this.render();
      graph.on('speak', (a) => this.pulse(a.id));
    }
    render() {
      this.root.replaceChildren();
      P().TEAM_ORDER.forEach((key) => {
        const T = P().TEAMS[key];
        const fam = h('section', 'fam');
        fam.dataset.team = key;
        fam.style.setProperty('--c', T.hue);
        const head = h('button', 'fam-head', null, { type: 'button', 'aria-pressed': 'false', title: `Filter ${T.label}` });
        head.append(h('i', 'fam-dot', null, { 'aria-hidden': 'true' }), h('strong', null, T.label), h('span', 'fam-count', '0'));
        head.addEventListener('click', () => this.toggle(key));
        fam.append(head);
        if (!this.compact) fam.append(h('p', 'fam-blurb x-expert-only', T.blurb), h('p', 'fam-blurb x-simple', T.kid || T.blurb));
        const list = h('div', 'fam-agents');
        P().teamAgents(key).forEach((a) => {
          const chip = h('button', 'ag', null, { type: 'button', title: `${a.id} · ${a.personality} — ${a.role}` });
          chip.dataset.id = a.id;
          chip.style.setProperty('--a', a.color);
          chip.append(h('i', 'ag-dot', null, { 'aria-hidden': 'true' }), h('b', null, a.id));
          if (!this.compact) chip.append(h('small', null, a.personality));
          chip.addEventListener('click', () => { this.g.select(a.id); });
          list.append(chip);
        });
        fam.append(list);
        this.root.append(fam);
      });
    }
    toggle(key) {
      if (this.active.has(key)) this.active.delete(key); else this.active.add(key);
      this.root.querySelectorAll('.fam').forEach((f) => {
        const on = this.active.has(f.dataset.team);
        f.classList.toggle('on', on);
        f.classList.toggle('off', this.active.size > 0 && !on);
        f.querySelector('.fam-head').setAttribute('aria-pressed', String(on));
      });
      this.g.setTeamFilter(this.active.size ? new Set(this.active) : null);
      if (this.onFilter) this.onFilter(this.active.size ? new Set(this.active) : null);
    }
    pulse(id) {
      const a = P().agent(id);
      if (!a) return;
      const chip = this.root.querySelector(`.ag[data-id="${id}"]`);
      if (chip) {
        chip.classList.add('awake');
        chip.classList.remove('talk');
        void chip.offsetWidth;
        chip.classList.add('talk');
      }
      const n = (this.counts.get(a.team) || 0) + 1;
      this.counts.set(a.team, n);
      const c = this.root.querySelector(`.fam[data-team="${a.team}"] .fam-count`);
      if (c) c.textContent = String(n);
    }
    reset() {
      this.counts.clear();
      this.root.querySelectorAll('.fam-count').forEach((c) => { c.textContent = '0'; });
      this.root.querySelectorAll('.ag').forEach((c) => c.classList.remove('awake', 'talk'));
    }
  }

  Object.assign(U, { Legend });
})();
