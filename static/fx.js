// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS motion layer: cursor glow + parallax vars, stage data-flow pulses.
// CSP-safe (external file, WAAPI only, no <style> injection), inserts no text
// (textContent-only LAW 4), honors prefers-reduced-motion, rAF-throttled,
// transform/opacity only (zero layout thrash). Companion CSS lives at the
// tail of static/app.css under the "fx motion layer" banner.
'use strict';
(() => {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const root = document.documentElement;
  const MAX_PULSES = 6;
  const PULSE_MS = 1100;

  let mx = window.innerWidth / 2;
  let my = window.innerHeight * 0.2;
  let queued = false;
  let active = 0;
  let lastStage = '';

  const $ = (sel) => document.querySelector(sel);
  const RED = '.panel.red';
  const BLUE = '.panel.blue';
  const SYS = '.telemetry';
  const layer = () => document.getElementById('fx-layer') || document.body;

  /* ---------- (1) reactive background: cursor glow + parallax ---------- */

  function paint() {
    queued = false;
    if (reduced.matches || document.hidden) return;
    const vw = window.innerWidth || 1;
    const vh = window.innerHeight || 1;
    const nx = Math.max(-0.5, Math.min(0.5, mx / vw - 0.5));
    const ny = Math.max(-0.5, Math.min(0.5, (my + (window.scrollY || 0) * 0.15) / vh - 0.5));
    root.style.setProperty('--fx-mx', `${mx.toFixed(1)}px`);
    root.style.setProperty('--fx-my', `${(my + (window.scrollY || 0) * 0.15).toFixed(1)}px`);
    root.style.setProperty('--fx-px', nx.toFixed(3));
    root.style.setProperty('--fx-py', ny.toFixed(3));
  }

  function schedule() {
    if (!queued && !reduced.matches) {
      queued = true;
      requestAnimationFrame(paint);
    }
  }

  /* ---------- (2) data-flow pulses on stage events ---------- */

  function center(elm) {
    if (!elm) return null;
    const r = elm.getBoundingClientRect();
    if (!r.width && !r.height) return null;
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }

  function onscreen(p) {
    return p.x > -60 && p.x < window.innerWidth + 60 && p.y > -60 && p.y < window.innerHeight + 60;
  }

  // A 10px dot travels from the middle of fromSel to the middle of toSel
  // along a slight arc (same element = in-place bloom). WAAPI only.
  function fire(kind, fromSel, toSel) {
    if (reduced.matches || active >= MAX_PULSES) return;
    const a = center($(fromSel));
    const b = center($(toSel || fromSel));
    if (!a || !b || !onscreen(a) || !onscreen(b)) return;
    const dot = document.createElement('span');
    dot.className = `flow-pulse flow-${kind}`;
    dot.setAttribute('aria-hidden', 'true');
    layer().append(dot);
    active += 1;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dist = Math.hypot(dx, dy);
    const hop = dist < 8 ? 0 : Math.min(60, dist * 0.18);
    const at = (x, y, s, o) => ({ transform: `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) scale(${s})`, opacity: o });
    const frames = dist < 8
      ? [at(a.x, a.y, 0.5, 0), { ...at(a.x, a.y, 1.8, 0.9), offset: 0.5 }, at(a.x, a.y, 0.6, 0)]
      : [at(a.x, a.y, 0.6, 0), { ...at(a.x + dx / 2, a.y + dy / 2 - hop, 1, 1), offset: 0.5 }, at(b.x, b.y, 0.6, 0)];
    let anim = null;
    try {
      anim = dot.animate(frames, { duration: PULSE_MS, easing: 'cubic-bezier(.2,.8,.2,1)' });
    } catch {
      anim = null;
    }
    const done = () => {
      active -= 1;
      dot.remove();
    };
    if (anim && anim.finished) anim.finished.then(done, done);
    else window.setTimeout(done, PULSE_MS + 100);
  }

  // Maps pipeline stage transitions to pulses. Called from setStage.
  // probe/patch fire once per activation; regression/build/research bloom.
  function onStage(name, state = 'active') {
    if (reduced.matches) return;
    if (name === 'sandbox' && state === 'active') lastStage = '';
    if (name === 'probe' || name === 'patch') {
      if (state !== 'active' || lastStage === name) return;
      lastStage = name; // matches setStage: repeats skipped while active
      fire(name === 'probe' ? 'probe' : 'patch', name === 'probe' ? RED : BLUE, SYS);
      return;
    }
    if (name === 'research' || name === 'analysis') {
      fire('research', SYS, SYS);
      return;
    }
    if (name === 'regression') {
      fire('sweep', SYS, RED);
      return;
    }
    if (name === 'cleanup' && state !== 'active') {
      fire('sweep', SYS, SYS);
    }
  }

  // Maps live log lines (same vocabulary advanceStage matches) to pulses.
  // Covers probe fired/blocked (exit code), patch applied, research
  // fetched, and build grown (green "Greenhouse grew ..." line).
  function onEvent(team, text) {
    if (reduced.matches) return;
    const t = String(text).toLowerCase();
    if (t.includes('greenhouse grew')) {
      fire('build', SYS, SYS);
      return;
    }
    if (team === 'research' && /fetching|intel|record|cve|advisory|epss/.test(t)) {
      fire('research', SYS, SYS);
      return;
    }
    const m = /boundary check exited (\d+)/.exec(t);
    if (m) {
      fire(Number(m[1]) === 0 ? 'probe' : 'blocked', RED, SYS);
      return;
    }
    if (t.includes('sanitization patch') || t.includes('bounded sanitation')) {
      fire('patch', BLUE, SYS);
      return;
    }
    if (t.includes('starting a fresh target') || t.includes('verifying a fresh target')) {
      fire('sweep', SYS, RED);
      return;
    }
    if (t.includes('containers, snapshots, and network removed')) {
      fire('sweep', SYS, SYS);
    }
  }

  function onFinish(result) {
    if (reduced.matches || !result) return;
    const ok = ['verified', 'not_confirmed', 'no_findings', 'completed'].includes(result.status);
    fire(ok ? 'blocked' : 'probe', '#result-panel', '#result-panel');
  }

  /* ---------- (4) perf guards: no listeners at all under reduced motion ---------- */

  function init() {
    if (reduced.matches) return;
    window.addEventListener('mousemove', (e) => {
      mx = e.clientX;
      my = e.clientY;
      schedule();
    }, { passive: true });
    window.addEventListener('scroll', schedule, { passive: true });
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) schedule();
    });
    try {
      reduced.addEventListener('change', () => {
        if (reduced.matches) active = 0;
      });
    } catch {
      /* older browsers: static matchMedia is enough */
    }
    schedule();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  window.SMSFx = { onEvent, onStage, onFinish, fire };
})();
