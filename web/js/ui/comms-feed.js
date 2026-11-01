// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · ui/comms-feed.js — CommsFeed: chat-style list of agent → target messages (one per stream event).
// DOM-only, textContent everywhere (no innerHTML), CSP-safe.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const U = (SMS.hud = SMS.hud || {});
  const P = () => SMS.palette;
  const { h, stamp } = U;

  /* ---------------- comms feed ---------------- */
  class CommsFeed {
    constructor(root, o = {}) {
      this.root = root;
      this.max = o.max || 120;
      this.filter = null;
      this.onPick = o.onPick || null;
      this.empty(o.emptyText || 'Agent communications appear here as bubbles fly across the web.');
    }
    empty(text) { this.root.replaceChildren(h('p', 'empty', text)); }
    clear(text) { this.empty(text || 'Waiting for the first message…'); }
    setFilter(set) {
      this.filter = set && set.size ? set : null;
      this.root.querySelectorAll('.cm').forEach((n) => { n.hidden = !!this.filter && !this.filter.has(n.dataset.team); });
    }
    add(ev) {
      const e = this.root.querySelector('.empty');
      if (e) e.remove();
      const a = P().agent(ev.speaker) || { color: '#94a8c4', glyph: '?', team: ev.team };
      const toA = ev.to ? P().agent(ev.to) : null;
      const row = h('article', 'cm');
      row.dataset.team = ev.team;
      row.dataset.stage = ev.stage || '';
      row.style.setProperty('--c', a.color);
      if (toA) row.style.setProperty('--c2', toA.color);
      const av = h('span', 'cm-av', a.glyph, { 'aria-hidden': 'true' });
      const body = h('div', 'cm-body');
      const head = h('header', 'cm-head');
      head.append(h('b', 'cm-from', ev.speaker));
      if (ev.toLabel) { head.append(h('i', 'cm-arrow', '→')); head.append(h('span', toA ? 'cm-to agent' : 'cm-to node', ev.toLabel)); }
      head.append(h('time', 'cm-time', stamp(ev.at)));
      body.append(head);
      if (ev.label) body.append(h('span', 'cm-chip', ev.label));
      body.append(h('p', 'cm-text', ev.body || ev.text));
      row.append(av, body);
      if (this.filter && !this.filter.has(ev.team)) row.hidden = true;
      if (this.onPick) row.addEventListener('click', () => this.onPick(ev));
      const pinned = this.root.scrollHeight - this.root.scrollTop - this.root.clientHeight < 60;
      this.root.append(row);
      while (this.root.children.length > this.max) this.root.firstChild.remove();
      if (pinned) this.root.scrollTop = this.root.scrollHeight;
    }
  }

  Object.assign(U, { CommsFeed });
})();
