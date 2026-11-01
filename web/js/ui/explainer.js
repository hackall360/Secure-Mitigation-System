// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · ui/explainer.js — the "explain it" layer shared by every visual page.
//
//   SMS.explain.level / set(level) / on(fn)      'simple' | 'both' | 'expert'  (body[data-explain])
//   new ExplainToggle(root, { page, def })       Simple · Both · Expert switch (key E cycles)
//   new Explainer(root)  .set({simple, expert})  two-line "in plain words" / "under the hood" box
//   new MapKey(root, { lens, compact })          lens-aware "how to read this map" key
//   lensIcon(key, size)                          small SVG icon for a lens (CSP-safe, no innerHTML)
//
// CSS helpers (css/core/explain.css): .x-simple (simple+both) · .x-expert (expert+both)
//                                     .x-simple-only · .x-expert-only
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const U = (SMS.hud = SMS.hud || {});
  const P = () => SMS.palette;
  const Ls = () => SMS.lenses;
  const { h } = U;
  const NS = 'http://www.w3.org/2000/svg';
  const LEVELS = ['simple', 'both', 'expert'];

  /* ---------------- level state ---------------- */
  const listeners = [];
  const explain = {
    level: 'both',
    set(level) {
      if (!LEVELS.includes(level)) return;
      explain.level = level;
      document.body.dataset.explain = level;
      listeners.forEach((fn) => { try { fn(level); } catch { /* ignore */ } });
    },
    on(fn) { listeners.push(fn); return explain; },
    cycle() { explain.set(LEVELS[(LEVELS.indexOf(explain.level) + 1) % LEVELS.length]); }
  };

  /* ---------------- svg helpers ---------------- */
  function svg(size, paths, o = {}) {
    const s = document.createElementNS(NS, 'svg');
    s.setAttribute('viewBox', '0 0 24 24');
    s.setAttribute('width', String(size));
    s.setAttribute('height', String(size));
    s.setAttribute('aria-hidden', 'true');
    paths.forEach((p) => {
      const el = document.createElementNS(NS, p.tag || 'path');
      Object.entries(p).forEach(([k, v]) => { if (k !== 'tag') el.setAttribute(k, String(v)); });
      if (!p.fill) el.setAttribute('fill', 'none');
      if (!p.stroke && !p.fill) el.setAttribute('stroke', o.color || 'currentColor');
      el.setAttribute('stroke-width', p['stroke-width'] || '1.7');
      el.setAttribute('stroke-linejoin', 'round');
      el.setAttribute('stroke-linecap', 'round');
      s.append(el);
    });
    return s;
  }

  const LENS_ICON = {
    file: [{ d: 'M6 2.5h8l4 4V21.5H6z' }, { d: 'M14 2.5v4h4' }, { d: 'M8.5 11h7M8.5 14h7M8.5 17h4.5' }],
    repo: [{ d: 'M3 7.5h6l2 2h10v10H3z' }, { d: 'M7 14.5h2.5v5M12 12.5h2.5v7M17 15.5h2v4' }],
    binary: [{ d: 'M7 7h10v10H7z' }, { d: 'M9.5 3v4M12 3v4M14.5 3v4M9.5 17v4M12 17v4M14.5 17v4M3 9.5h4M3 12h4M3 14.5h4M17 9.5h4M17 12h4M17 14.5h4' }],
    system: [{ d: 'M3 11.5L12 4l9 7.5' }, { d: 'M5.5 10v10.5h13V10' }, { d: 'M10 20.5v-5.5h4v5.5' }]
  };
  function lensIcon(key, size = 16) { return svg(size, LENS_ICON[key] || LENS_ICON.file); }

  // Map-key glyphs drawn to match engine/render-nodes.js shapes.
  const GLYPH = {
    endpoint: (c) => [{ d: 'M18 12L7 18.5V5.5z', stroke: c }],
    sink: (c) => [{ d: 'M12 4l8 8-8 8-8-8z', stroke: c }, { tag: 'circle', cx: 12, cy: 12, r: 2, fill: c, stroke: c }],
    file: (c) => [{ d: 'M6.5 6.5h11v11h-11z', stroke: c }],
    function: (c) => [{ tag: 'circle', cx: 12, cy: 12, r: 4, stroke: c }],
    dir: (c) => [{ d: 'M4 8h6l1.5 2H20v8H4z', stroke: c }],
    import: (c) => [{ tag: 'circle', cx: 12, cy: 12, r: 3, stroke: c }, { d: 'M15 12h5', stroke: c }],
    section: (c) => [{ tag: 'circle', cx: 12, cy: 12, r: 6, stroke: c }, { tag: 'circle', cx: 12, cy: 12, r: 2, fill: c, stroke: c }],
    host: (c) => [{ d: 'M5 6h14v12H5z', stroke: c }, { d: 'M8 10h8M8 14h8', stroke: c }],
    port: (c) => [{ d: 'M8 20V10a4 4 0 0 1 8 0v10z', stroke: c }, { tag: 'circle', cx: 14, cy: 15, r: 0.8, fill: c, stroke: c }],
    data: (c) => [{ tag: 'circle', cx: 12, cy: 12, r: 6, stroke: c }, { tag: 'circle', cx: 12, cy: 12, r: 3.4, stroke: c }],
    path: (c) => [{ d: 'M3 16c4-8 8 4 18-6', stroke: c, 'stroke-dasharray': '1 3.5', 'stroke-width': '2.4' }],
    bubble: (c) => [{ d: 'M4 7h16v8H11l-4 3v-3H4z', stroke: c }],
    shield: (c) => [{ d: 'M12 4l7 3v5c0 4-3 7-7 8-4-1-7-4-7-8V7z', stroke: c }, { d: 'M9 12l2 2 4-4', stroke: c }],
    verified: (c) => [{ d: 'M5 5h14v14H5z', stroke: c }, { tag: 'circle', cx: 12, cy: 12, r: 2.5, fill: c, stroke: c }]
  };

  const KEY_BY_LENS = {
    file: ['endpoint', 'function', 'sink'],
    repo: ['dir', 'file', 'endpoint', 'sink'],
    binary: ['section', 'function', 'import', 'sink'],
    system: ['host', 'port', 'data', 'sink']
  };

  /* ---------------- toggle ---------------- */
  class ExplainToggle {
    constructor(root, o = {}) {
      this.root = root;
      this.key = `sms.v3.explain.${o.page || 'page'}`;
      const saved = localStorage.getItem(this.key);
      root.classList.add('oseg', 'ex-toggle');
      root.setAttribute('role', 'radiogroup');
      root.setAttribute('aria-label', 'Explanation level (E)');
      root.title = 'How much to explain (E): plain words, both, or expert detail';
      const labels = { simple: 'Simple', both: 'Both', expert: 'Expert' };
      this.btns = LEVELS.map((lv) => {
        const b = h('button', null, labels[lv], { type: 'button', role: 'radio', 'aria-checked': 'false' });
        b.dataset.level = lv;
        b.addEventListener('click', () => { explain.set(lv); localStorage.setItem(this.key, lv); });
        root.append(b);
        return b;
      });
      explain.on((lv) => this.btns.forEach((b) => b.setAttribute('aria-checked', String(b.dataset.level === lv))));
      explain.set(LEVELS.includes(saved) ? saved : (o.def || 'both'));
      document.addEventListener('keydown', (e) => {
        if (e.altKey || e.ctrlKey || e.metaKey || /input|textarea|select/i.test(e.target.tagName)) return;
        if (e.key.toLowerCase() === 'e') { explain.cycle(); localStorage.setItem(this.key, explain.level); }
      });
    }
  }

  /* ---------------- two-line explainer ---------------- */
  class Explainer {
    constructor(root, o = {}) {
      this.root = root;
      root.classList.add('ex');
      this.s = h('p', 'ex-line ex-simple x-simple');
      this.s.append(h('span', 'ex-k', o.simpleLabel || 'In plain words'), h('span', 'ex-t'));
      this.e = h('p', 'ex-line ex-expert x-expert');
      this.e.append(h('span', 'ex-k', o.expertLabel || 'Under the hood'), h('span', 'ex-t'));
      root.append(this.s, this.e);
    }
    set(x) {
      if (!x) return;
      if (x.simple !== undefined) this._put(this.s, x.simple);
      if (x.expert !== undefined) this._put(this.e, x.expert);
    }
    _put(line, text) {
      const t = line.lastChild;
      if (t.textContent === text) return;
      t.textContent = text;
      line.classList.remove('fresh');
      void line.offsetWidth;
      line.classList.add('fresh');
    }
  }

  /* ---------------- how to read this map ---------------- */
  class MapKey {
    constructor(root, o = {}) {
      this.root = root;
      this.compact = !!o.compact;
      root.classList.add('mapkey');
      if (this.compact) root.classList.add('compact');
      this.setLens(o.lens || 'file');
    }
    setLens(lens) {
      this.lens = lens;
      const L = Ls().get(lens);
      const S = P().STATE;
      const T = P().TEAMS;
      this.root.replaceChildren();
      this.root.style.setProperty('--lens', L.accent);
      if (!this.compact) {
        const head = h('div', 'mk-head');
        const ic = h('span', 'mk-lens');
        ic.append(lensIcon(lens, 18));
        const txt = h('div');
        txt.append(h('b', null, `${L.label} — ${L.metaphor.toLowerCase()}`), h('small', 'x-simple', L.simple), h('small', 'x-expert-only', L.expert));
        head.append(ic, txt);
        this.root.append(head);
      }
      const grid = h('ul', 'mk-grid');
      const row = (glyph, color, kid, pro) => {
        const li = h('li');
        li.append(svg(16, GLYPH[glyph](color)));
        const t = h('span');
        t.append(h('b', 'x-simple', kid), h('b', 'x-expert-only', pro));
        if (!this.compact) t.append(h('small', 'x-both-only', pro));
        li.append(t);
        li.title = `${kid} — ${pro}`;
        grid.append(li);
      };
      (KEY_BY_LENS[lens] || KEY_BY_LENS.file).forEach((k) => { const n = Ls().kind(lens, k); row(k, k === 'sink' ? S.suspect.color : '#cfe3ff', n.simple, n.expert); });
      row('path', T.red.hue, 'Red dots: the way a trick travels in', 'Taint / attack path');
      row('bubble', '#cfe3ff', 'Bubbles: agents talking to each other', 'Agent message');
      row('shield', T.blue.hue, 'Blue shield: a new lock', 'Guard · candidate patch');
      row('verified', T.purple.hue, 'Purple box: the lock was proven', 'Verified on a fresh target');
      this.root.append(grid);
    }
  }

  // Lens badge: icon + label (+ metaphor in simple mode).
  function lensBadge(root, lens) {
    const L = Ls().get(lens);
    root.replaceChildren();
    root.classList.add('lens-badge');
    root.dataset.lens = lens;
    root.style.setProperty('--lens', L.accent);
    root.title = `${L.label}: ${L.expert}`;
    root.append(lensIcon(lens, 14), h('b', null, L.label), h('span', 'x-simple', `· ${L.metaphor.toLowerCase()}`));
  }

  Object.assign(U, { ExplainToggle, Explainer, MapKey, lensIcon, lensBadge });
  SMS.explain = explain;
})();
