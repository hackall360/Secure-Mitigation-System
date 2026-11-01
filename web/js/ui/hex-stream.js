// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · ui/hex-stream.js — HexStream: hexdump of the real bytes of each message (decorative, but true).
// DOM-only, textContent everywhere (no innerHTML), CSP-safe.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const U = (SMS.hud = SMS.hud || {});
  const P = () => SMS.palette;
  const { h } = U;

  /* ---------------- hex stream (real bytes of the real message) ---------------- */
  class HexStream {
    constructor(root, o = {}) { this.root = root; this.max = o.max || 18; this.addr = 0; }
    push(team, text) {
      const bytes = new TextEncoder().encode(String(text)).slice(0, 16);
      const hex = [...bytes].map((b) => b.toString(16).padStart(2, '0')).join(' ');
      const ascii = [...bytes].map((b) => (b >= 32 && b < 127 ? String.fromCharCode(b) : '.')).join('');
      const row = h('div', 'hx');
      row.dataset.team = P().family(team);
      row.append(h('span', 'hx-a', this.addr.toString(16).padStart(8, '0')), h('span', 'hx-h', hex.padEnd(47, ' ')), h('span', 'hx-s', ascii));
      this.addr += Math.max(16, String(text).length);
      this.root.append(row);
      while (this.root.children.length > this.max) this.root.firstChild.remove();
    }
    clear() { this.root.replaceChildren(); this.addr = 0; }
  }

  Object.assign(U, { HexStream });
})();
