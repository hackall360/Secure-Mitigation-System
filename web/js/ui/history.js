// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · ui/history.js — last 12 run results kept in localStorage ('sms.v3.history').
// const hist = new SMS.views.RunHistory(listEl, { onOpen(payload, isFake) {} });
// hist.save(payload, { source:'live'|'fake', mode, target });  hist.render();
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const { h, toast } = SMS.hud;
  const KEY = 'sms.v3.history';

  class RunHistory {
    constructor(root, o = {}) { this.root = root; this.onOpen = o.onOpen || null; this.render(); }
    load() { try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; } }
    save(p, o = {}) {
      const { pre, post, receipt } = SMS.views.summarize(p);
      const list = this.load();
      list.unshift({ at: Date.now(), mode: o.mode, target: p.target || p.project || o.target || o.mode, status: p.status, pre, post, sha: (receipt && (receipt.patch_sha256 || receipt.patch_hash)) || null, replay: o.source === 'fake' || !!p.replay, payload: JSON.stringify(p).length < 120000 ? p : null });
      try { localStorage.setItem(KEY, JSON.stringify(list.slice(0, 12))); } catch { /* quota */ }
      this.render();
    }
    render() {
      const root = this.root;
      const list = this.load();
      root.replaceChildren();
      if (!list.length) { root.append(h('li', 'empty', 'No runs yet on this browser.')); return; }
      list.forEach((r) => {
        const li = h('li', null, null, { tabindex: '0', title: r.sha ? `receipt ${r.sha}` : '' });
        li.style.setProperty('--c', r.status === 'verified' ? '#b06cff' : SMS.OK_STATUSES.includes(r.status) ? '#2dd4bf' : '#ff3b5c');
        li.append(h('i'), h('span', null, `${r.target} · ${r.status}${r.replay ? ' · fake' : ''}`), h('small', null, new Date(r.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })));
        const open = () => { if (r.payload) { if (this.onOpen) this.onOpen(r.payload, r.replay); } else toast('Result too large to keep in history'); };
        li.addEventListener('click', open);
        li.addEventListener('keydown', (e) => { if (e.key === 'Enter') open(); });
        root.append(li);
      });
    }
  }

  SMS.views = Object.assign(SMS.views || {}, { RunHistory });
})();
