// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · ui/activity.js — the console's Activity log and real-time Timeline strip.
//   const log = new SMS.views.ActivityLog(logEl);  log.add(ev); log.setTeam('red'|'all'); log.setStage('probe'|'');
//   const tl  = new SMS.views.Timeline(stripEl, { onPick(ev) {} });  tl.add(ev); tl.reset();
// Timeline gap spacers are sized by the REAL time between events (log scale, labelled > 15 s).
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const { h, stamp, elapsed } = SMS.hud;
  const P = SMS.palette;
  const color = (ev) => { const a = P.agent(ev.speaker); return a ? a.color : '#94a8c4'; };

  class ActivityLog {
    constructor(root, o = {}) { this.root = root; this.max = o.max || 1500; this.team = 'all'; this.stage = ''; }
    reset(text) { this.root.replaceChildren(h('p', 'empty', text || 'Waiting for the first event…')); }
    matches(row) { return (this.team === 'all' || row.dataset.team === this.team) && (!this.stage || row.dataset.stage === this.stage); }
    refilter() { this.root.querySelectorAll('.le').forEach((r) => { r.hidden = !this.matches(r); }); }
    setTeam(t) { this.team = t || 'all'; this.refilter(); }
    setStage(s) { this.stage = s || ''; this.refilter(); }
    add(ev) {
      const empty = this.root.querySelector('.empty');
      if (empty) empty.remove();
      const row = h('div', 'le');
      row.dataset.team = ev.team;
      row.dataset.stage = ev.stage || '';
      row.dataset.seq = String(ev.seq);
      row.style.setProperty('--c', color(ev));
      row.append(h('time', null, stamp(ev.at)), h('span', 'tg', ev.speaker), h('span', 'tx', ev.text));
      row.hidden = !this.matches(row);
      const pinned = this.root.scrollHeight - this.root.scrollTop - this.root.clientHeight < 50;
      this.root.append(row);
      while (this.root.children.length > this.max) this.root.firstChild.remove();
      if (pinned) this.root.scrollTop = this.root.scrollHeight;
    }
    reveal(seq) {
      const row = this.root.querySelector(`.le[data-seq="${seq}"]`);
      if (!row) return;
      row.hidden = false;
      row.scrollIntoView({ block: 'center' });
      row.animate([{ background: 'rgba(45,212,191,0.25)' }, { background: 'transparent' }], { duration: 1200 });
    }
    visibleText() { return [...this.root.querySelectorAll('.le:not([hidden])')].map((r) => r.innerText.replace(/\n/g, ' ')).join('\n'); }
  }

  class Timeline {
    constructor(root, o = {}) { this.root = root; this.onPick = o.onPick || null; this.max = o.max || 900; this.reset(); }
    reset() { this.root.replaceChildren(); this.lastAt = 0; this.lastStage = ''; }
    add(ev) {
      const tl = this.root;
      const e = tl.querySelector('.empty');
      if (e) e.remove();
      if (this.lastAt) {
        const gap = ev.at - this.lastAt;
        if (gap > 2500) {
          const g = h('span', 'gap', null, { 'aria-hidden': 'true' });
          g.style.width = `${Math.min(70, 8 + Math.log2(gap / 1000) * 9)}px`;
          if (gap > 15000) g.append(h('span', null, `+${elapsed(gap)}`));
          tl.append(g);
        }
      }
      this.lastAt = ev.at;
      const m = h('button', 'mk', null, { type: 'button', title: `${stamp(ev.at)} · ${ev.speaker}${ev.toLabel ? ` → ${ev.toLabel}` : ''}: ${ev.text.slice(0, 200)}`, 'aria-label': `${ev.speaker}: ${ev.text.slice(0, 80)}` });
      m.style.setProperty('--c', color(ev));
      if (ev.exit === 0 || ev.exit === 1) m.dataset.exit = String(ev.exit);
      if (ev.stage && ev.stage !== this.lastStage) {
        m.classList.add('stage-start');
        const meta = P.STAGE_META[ev.stage];
        m.dataset.stage = meta ? `${meta.n} ${meta.label}` : ev.stage;
        if (meta && Number(meta.n) % 2 === 0) m.classList.add('alt');
        this.lastStage = ev.stage;
      }
      if (this.onPick) m.addEventListener('click', () => this.onPick(ev));
      const pinned = tl.scrollWidth - tl.scrollLeft - tl.clientWidth < 60;
      tl.append(m);
      while (tl.children.length > this.max) tl.firstChild.remove();
      if (pinned) tl.scrollLeft = tl.scrollWidth;
    }
  }

  SMS.views = Object.assign(SMS.views || {}, { ActivityLog, Timeline });
})();
