// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · ui/stream-meter.js — StreamMeter: real-time connection state, events/min, time since last event.
// DOM-only, textContent everywhere (no innerHTML), CSP-safe.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const U = (SMS.hud = SMS.hud || {});
  const { h } = U;

  /* ---------------- real-time stream meter ---------------- */
  // Shows connection state, events/min over the last minute, and time since the last event.
  class StreamMeter {
    constructor(root, o = {}) {
      this.root = root;
      this.stallMs = o.stallMs || 45000;
      this.times = [];
      this.last = 0;
      this.state = 'closed';
      this.label = o.label || 'stream';
      this.root.classList.add('meter');
      this.root.replaceChildren(h('i'), h('span', 'm-l', this.label), h('b', 'm-r', '—'), h('span', 'm-a', ''));
      this.timer = setInterval(() => this.render(), 1000);
      this.render();
    }
    open(label) { this.state = 'waiting'; this.times = []; this.last = Date.now(); if (label) this.label = label; this.render(); }
    tick() { const t = Date.now(); this.last = t; this.times.push(t); if (this.times.length > 600) this.times.shift(); this.state = 'streaming'; this.render(); }
    close() { this.state = 'closed'; this.render(); }
    render() {
      const t = Date.now();
      this.times = this.times.filter((x) => t - x < 60000);
      if (this.state !== 'closed') {
        const quiet = t - this.last;
        this.state = !this.times.length && quiet < this.stallMs ? 'waiting' : quiet > this.stallMs ? 'stalled' : 'streaming';
      }
      this.root.dataset.state = this.state;
      this.root.querySelector('.m-l').textContent = this.state === 'closed' ? `${this.label} · idle` : this.state === 'stalled' ? `${this.label} · quiet` : this.label;
      this.root.querySelector('.m-r').textContent = this.state === 'closed' ? '—' : `${this.times.length}/min`;
      const age = Math.floor((t - this.last) / 1000);
      this.root.querySelector('.m-a').textContent = this.state === 'closed' || !this.last ? '' : `last ${age < 60 ? `${age}s` : `${Math.floor(age / 60)}m${String(age % 60).padStart(2, '0')}s`} ago`;
      this.root.title = 'Real-time stream: events in the last minute and time since the last event';
    }
    quietFor() { return this.state === 'closed' ? 0 : Date.now() - this.last; }
  }

  Object.assign(U, { StreamMeter });
})();
