// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · engine/kit.js — shared constants, math helpers and the cached glow sprites
// used by every engine module. Exposed as SMS.engine.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const P = () => SMS.palette;

  const TAU = Math.PI * 2;
  const MONO = '"JetBrains Mono","Cascadia Code",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace';
  const RING0 = 150;   // radius of ring 1
  const RING_STEP = 112;
  const MAX_PACKETS = 40;
  const MAX_PARTICLES = 420;

  const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const easeOut = (t) => 1 - Math.pow(1 - t, 3);
  const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

  function reducedMotion() {
    try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return false; }
  }

  // ---------- sprite cache: pre-rendered additive glows (cheap vs shadowBlur) ----------
  const spriteCache = new Map();
  function glowSprite(color) {
    let s = spriteCache.get(color);
    if (s) return s;
    const size = 128;
    s = document.createElement('canvas');
    s.width = size;
    s.height = size;
    const g = s.getContext('2d');
    const grad = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    const rgba = P().rgba;
    grad.addColorStop(0, rgba(color, 0.95));
    grad.addColorStop(0.18, rgba(color, 0.55));
    grad.addColorStop(0.45, rgba(color, 0.14));
    grad.addColorStop(1, rgba(color, 0));
    g.fillStyle = grad;
    g.fillRect(0, 0, size, size);
    spriteCache.set(color, s);
    return s;
  }

  SMS.engine = { TAU, MONO, RING0, RING_STEP, MAX_PACKETS, MAX_PARTICLES, now, clamp, lerp, easeOut, easeInOut, reducedMotion, glowSprite };
})();
