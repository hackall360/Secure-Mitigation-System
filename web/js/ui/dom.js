// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · ui/dom.js — DOM + formatting helpers shared by every widget and page: h(), stamp, toast,
// animated counters, mm:ss elapsed, glitch-scramble text.
// DOM-only, textContent everywhere (no innerHTML), CSP-safe.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const U = (SMS.hud = SMS.hud || {});

  function h(tag, cls, text, attrs) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    if (attrs) Object.entries(attrs).forEach(([k, v]) => { if (v !== undefined && v !== null) n.setAttribute(k, v); });
    return n;
  }
  const stamp = (t) => new Date(t || Date.now()).toLocaleTimeString([], { hour12: false });
  const reduced = () => { try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return false; } };

  /* ---------------- counters ---------------- */
  function counter(node, value) {
    if (!node) return;
    const prev = Number(node.dataset.v || 0);
    node.dataset.v = String(value);
    if (reduced() || value <= prev) { node.textContent = String(value); return; }
    const start = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - start) / 450);
      node.textContent = String(Math.round(prev + (value - prev) * k));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
    node.classList.remove('bump');
    void node.offsetWidth;
    node.classList.add('bump');
  }

  function toast(text, ms = 2400) {
    let n = document.getElementById('toast');
    if (!n) { n = h('div', 'toast', null, { id: 'toast', role: 'status', 'aria-live': 'polite' }); document.body.append(n); }
    n.textContent = text;
    n.hidden = false;
    n.classList.remove('show');
    void n.offsetWidth;
    n.classList.add('show');
    clearTimeout(toast.t);
    toast.t = setTimeout(() => { n.hidden = true; }, ms);
  }

  function elapsed(ms) {
    const s = Math.floor(ms / 1000);
    const m = Math.floor(s / 60);
    return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
  }

  // Glitch-scramble a heading's text into place (Mr. Robot title card feel).
  // Always lands on the real text: a timer (not rAF, which stalls in hidden/background tabs and
  // during screen capture) drives the effect, and a hard deadline writes the final string even if
  // ticks are throttled. Only letters/digits scramble; punctuation and spaces stay put so the line
  // keeps its shape and never wraps differently mid-animation. Screen readers get the final text.
  const SCR_GLYPHS = 'ABCDEFGHJKLMNPRSTUVWXYZ0123456789';
  function scramble(node, text, ms = 700) {
    if (!node) return;
    text = String(text == null ? '' : text);
    const token = String((scramble.seq = (scramble.seq || 0) + 1));
    node.dataset.scr = token;
    node.setAttribute('aria-label', text);
    if (reduced() || document.hidden || !text) { node.textContent = text; return; }
    const start = performance.now();
    const finish = () => { if (node.dataset.scr === token) node.textContent = text; };
    const tick = () => {
      if (node.dataset.scr !== token) return;
      const k = Math.min(1, (performance.now() - start) / ms);
      if (k >= 1) { finish(); return; }
      const fixed = Math.floor(text.length * k);
      let out = text.slice(0, fixed);
      for (let i = fixed; i < text.length; i += 1) {
        const c = text[i];
        if (!/[A-Za-z0-9]/.test(c)) { out += c; continue; }
        const g = SCR_GLYPHS[(Math.random() * SCR_GLYPHS.length) | 0];
        out += c >= 'a' && c <= 'z' ? g.toLowerCase() : g;
      }
      node.textContent = out;
      setTimeout(tick, 33);
    };
    tick();
    setTimeout(finish, ms + 120);
  }

  Object.assign(U, { h, stamp, reduced, counter, toast, elapsed, scramble });
})();
