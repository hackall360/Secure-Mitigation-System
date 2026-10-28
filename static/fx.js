// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS motion layer: cursor glow + parallax vars, stage data-flow pulses.
// CSP-safe (external file, WAAPI only, no <style> injection), inserts no text
// (textContent-only LAW 4), honors prefers-reduced-motion, rAF-throttled with
// eased trailing (self-terminating), event dedupe, distance-based durations,
// transform/opacity only (zero layout thrash). Companion CSS lives at the
// tail of static/app.css under the "fx motion layer" banner.
'use strict';
(() => {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const root = document.documentElement;
  const MAX_PULSES = 6;
  const PULSE_MS = 1100;
  const LERP = 0.22; // glow trails the pointer: buttery, then settles
  const SETTLE_PX = 0.4; // stop the rAF chain once visually settled
  const DEDUPE_MS = 300; // coalesce identical pulses from log+stage bursts

  let mx = window.innerWidth / 2; // pointer target (client coords)
  let my = window.innerHeight * 0.2;
  let cx = mx; // eased current position, painted to CSS vars
  let cy = my;
  let queued = false;
  let active = 0;
  let lastStage = '';
  let lastSig = '';
  let lastAt = 0;
  const dots = new Set();
  const cache = new Map(); // skip redundant CSS var writes (no style churn)

  const $ = (sel) => document.querySelector(sel);
  const RED = '.panel.red';
  const BLUE = '.panel.blue';
  const SYS = '.telemetry';
  const layer = () => document.getElementById('fx-layer') || document.body;

  /* ---------- (1) reactive background: cursor glow + parallax ---------- */

  function setVar(name, value) {
    if (cache.get(name) !== value) {
      cache.set(name, value);
      root.style.setProperty(name, value);
    }
  }

  // Eased trailing: cx/cy chase the pointer, rAF keeps chaining only while
  // visibly moving, then stops itself. Client coords (no scrollY jitter).
  function paint() {
    const dx = mx - cx;
    const dy = my - cy;
    const moving = Math.abs(dx) > SETTLE_PX || Math.abs(dy) > SETTLE_PX;
    if (moving) {
      cx += dx * LERP;
      cy += dy * LERP;
    } else {
      cx = mx;
      cy = my;
    }
    if (!reduced.matches && !document.hidden) {
      const vw = window.innerWidth || 1;
      const vh = window.innerHeight || 1;
      const nx = Math.max(-0.5, Math.min(0.5, cx / vw - 0.5));
      const ny = Math.max(-0.5, Math.min(0.5, cy / vh - 0.5));
      setVar('--fx-mx', `${cx.toFixed(1)}px`);
      setVar('--fx-my', `${cy.toFixed(1)}px`);
      setVar('--fx-px', nx.toFixed(3));
      setVar('--fx-py', ny.toFixed(3));
    }
    if (moving && !reduced.matches) requestAnimationFrame(paint);
    else queued = false;
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
  // Dedupe: log-line and stage callbacks often fire the same vocabulary
  // within one frame; identical signatures coalesce instead of stacking.
  // Duration scales gently with distance so short hops feel snappy.
  function fire(kind, fromSel, toSel) {
    if (reduced.matches || document.hidden || active >= MAX_PULSES) return;
    const now = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    const sig = `${kind}|${fromSel}|${toSel || fromSel}`;
    if (sig === lastSig && now - lastAt < DEDUPE_MS) return;
    lastSig = sig;
    lastAt = now;
    const a = center($(fromSel));
    const b = center($(toSel || fromSel));
    if (!a || !b || !onscreen(a) || !onscreen(b)) return;
    const dot = document.createElement('span');
    dot.className = `flow-pulse flow-${kind}`;
    dot.setAttribute('aria-hidden', 'true');
    const host = layer();
    if (!host || typeof host.append !== 'function') return;
    host.append(dot);
    active += 1;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dist = Math.hypot(dx, dy);
    const dur = Math.round(Math.max(650, Math.min(PULSE_MS, PULSE_MS * (0.55 + dist / 1400))));
    const hop = dist < 8 ? 0 : Math.min(60, dist * 0.18);
    const at = (x, y, s, o) => ({ transform: `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) scale(${s})`, opacity: o });
    const frames = dist < 8
      ? [at(a.x, a.y, 0.5, 0), { ...at(a.x, a.y, 1.8, 0.9), offset: 0.5 }, at(a.x, a.y, 0.6, 0)]
      : [at(a.x, a.y, 0.6, 0), { ...at(a.x + dx / 2, a.y + dy / 2 - hop, 1, 1), offset: 0.5 }, at(b.x, b.y, 0.6, 0)];
    let anim = null;
    try {
      anim = dot.animate(frames, { duration: dur, easing: 'cubic-bezier(.2,.8,.2,1)', composite: 'replace' });
    } catch {
      anim = null;
    }
    dots.add(dot);
    const done = () => {
      if (!dots.has(dot)) return;
      dots.delete(dot);
      active -= 1;
      dot.remove();
    };
    if (anim && anim.finished) anim.finished.then(done, done);
    else window.setTimeout(done, dur + 100);
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

  // Tear down in-flight dots so a mid-scan reduced-motion switch or a
  // background tab never leaves orphaned nodes or a stuck rAF chain.
  function teardown() {
    dots.forEach((dot) => {
      try {
        if (dot.getAnimations) dot.getAnimations().forEach((a) => { try { a.cancel(); } catch { /* noop */ } });
      } catch { /* noop */ }
      dot.remove();
    });
    dots.clear();
    active = 0;
    queued = false;
  }

  function init() {
    if (reduced.matches) return;
    window.addEventListener('pointermove', (e) => {
      mx = e.clientX;
      my = e.clientY;
      schedule();
    }, { passive: true });
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', () => {
      cx = Math.min(cx, window.innerWidth || cx);
      cy = Math.min(cy, window.innerHeight || cy);
      schedule();
    }, { passive: true });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) teardown();
      else schedule();
    });
    try {
      reduced.addEventListener('change', () => {
        if (reduced.matches) teardown();
      });
    } catch {
      /* older browsers: static matchMedia is enough */
    }
    schedule();
  }

  function dispose() {
    active = 0;
    document.querySelectorAll('.flow-pulse').forEach((node) => node.remove());
  }

  /* ---------- (5) teardown guards: no leaked pulses, no loud rejections ---------- */

  window.addEventListener('pagehide', dispose);
  window.addEventListener('unhandledrejection', (event) => {
    event.preventDefault();
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  window.SMSFx = { onEvent, onStage, onFinish, fire };
})();
