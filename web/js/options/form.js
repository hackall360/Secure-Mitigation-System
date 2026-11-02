// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · options/form.js — OptionForm: renders schema fields as switches, steppers, segmented
// selectors, text/code inputs and file pickers; validates and persists values.
// Usage: new SMS.options.OptionForm(rootEl, { keys, ctx:{page,source,...}, storageKey, onChange })
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const O = (SMS.options = SMS.options || {});
  const { FIELDS, SOURCES, spec, defaults, modeCycles, isInt } = O;

  const h = (tag, cls, text, attrs) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    if (attrs) Object.entries(attrs).forEach(([k, x]) => { if (x !== undefined && x !== null && x !== false) n.setAttribute(k, x === true ? '' : x); });
    return n;
  };
  let uid = 0;

  class OptionForm {
    // o: { keys, ctx: { page, source, scanProfiles, models, defaultModel, inferenceMode }, values, onChange, storageKey }
    constructor(root, o) {
      this.root = root;
      this.o = o;
      this.ctx = o.ctx || { page: 'console' };
      this.keys = o.keys.filter((k) => FIELDS[k]);
      this.v = Object.assign(defaults(this.keys, this.ctx), this._load(), o.values || {});
      this.nodes = {};
      this.disabled = false;
      this.render();
    }

    _load() {
      if (!this.o.storageKey) return {};
      try {
        const saved = JSON.parse(localStorage.getItem(this.o.storageKey) || '{}');
        const out = {};
        this.keys.forEach((k) => { if (k in saved && FIELDS[k].type !== 'file') out[k] = saved[k]; });
        return out;
      } catch { return {}; }
    }
    _save() {
      if (!this.o.storageKey) return;
      try {
        const keep = {};
        this.keys.forEach((k) => { if (FIELDS[k].type !== 'file' && k !== 'source') keep[k] = this.v[k]; });
        localStorage.setItem(this.o.storageKey, JSON.stringify(keep));
      } catch { /* quota */ }
    }

    setContext(ctx) {
      Object.assign(this.ctx, ctx);
      if (this.keys.includes('profile') && ctx.defaultModel && !this.v.profile) this.v.profile = ctx.defaultModel;
      this.render();
    }

    values() { return Object.assign({}, this.v); }

    set(key, val, silent) {
      if (!(key in FIELDS)) return;
      this.v[key] = val;
      if (key === 'scan_profile') {
        const c = modeCycles(this.v, this.ctx);
        if (c !== null && this.keys.includes('cycles')) this.v.cycles = Math.min(c, spec('cycles', this.ctx).max);
      }
      this._sync();
      this._save();
      if (!silent && this.o.onChange) this.o.onChange(key, val, this.values());
    }

    disable(on) { this.disabled = on; this._sync(); }

    render() {
      this.root.replaceChildren();
      this.nodes = {};
      if (this.keys.includes('scan_profile')) { const c = modeCycles(this.v, this.ctx); if (c !== null && 'cycles' in this.v) this.v.cycles = Math.min(c, spec('cycles', this.ctx).max); }
      this.keys.forEach((k) => {
        const s = spec(k, this.ctx);
        if (!s || s.hidden) return;
        const el = this._field(s);
        if (el) { this.nodes[k] = el; this.root.append(el); }
      });
      this._sync();
    }

    _badges(s, wrap) {
      if (s.badge) wrap.append(h('span', 'ob', s.badge));
      if (s.proposed) wrap.append(h('span', 'ob prop', 'proposed', { title: 'Not part of the current backend contract. Sent only when "Send proposed controls" is on.' }));
      else if (s.wire === 'query') wrap.append(h('span', 'ob q', 'query', { title: 'Sent as a URL query parameter' }));
      wrap.append(h('span', 'ob na', 'not used', { title: 'This source’s endpoint does not take this setting', hidden: true }));
    }

    _field(s) {
      const id = `opt-${s.key}-${(uid += 1)}`;
      const box = h('div', `of of-${s.type}`);
      box.dataset.key = s.key;
      const head = h('div', 'of-head');
      const lab = h('label', 'of-label', s.label, { for: id });
      head.append(lab);
      this._badges(s, head);

      if (s.type === 'toggle') {
        box.className = 'of of-toggle';
        const lbl = h('label', 'tg', null, { for: id });
        const input = h('input', null, null, { type: 'checkbox', id, role: 'switch' });
        input.addEventListener('change', () => this.set(s.key, input.checked));
        const sw = h('span', 'tg-sw', null, { 'aria-hidden': 'true' });
        sw.append(h('i'));
        const txt = h('span', 'tg-txt');
        const top = h('span', 'tg-top');
        top.append(h('b', null, s.label));
        this._badges(s, top);
        txt.append(top);
        if (s.help) txt.append(h('small', null, s.help));
        lbl.append(input, sw, txt);
        box.append(lbl);
        box._input = input;
        return box;
      }

      box.append(head);
      let input;
      if (s.type === 'text') {
        input = h('input', null, null, { id, type: 'text', maxlength: s.max, placeholder: s.placeholder, autocomplete: 'off', spellcheck: 'false' });
        input.addEventListener('input', () => this.set(s.key, input.value));
        box.append(input);
      } else if (s.type === 'textarea' || s.type === 'code') {
        input = h('textarea', s.type === 'code' ? 'code' : null, null, { id, rows: s.rows || 3, placeholder: s.placeholder, spellcheck: 'false' });
        input.addEventListener('input', () => this.set(s.key, input.value));
        box.append(input);
      } else if (s.type === 'select') {
        input = h('select', null, null, { id });
        (s.options || []).forEach((o) => { const op = h('option', null, o.l, { value: o.v }); input.append(op); });
        input.addEventListener('change', () => this.set(s.key, input.value));
        box.append(input);
        if (s.hideIfEmpty && !(s.options || []).length) return null;
      } else if (s.type === 'segmented') {
        const seg = h('div', 'oseg', null, { role: 'radiogroup', 'aria-label': s.label });
        lab.removeAttribute('for');
        (s.options || []).forEach((o) => {
          const b = h('button', null, o.l, { type: 'button', role: 'radio', title: o.d || '' });
          b.dataset.v = o.v;
          b.addEventListener('click', () => this.set(s.key, o.v));
          seg.append(b);
        });
        seg.addEventListener('keydown', (e) => {
          const d = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
          if (!d) return;
          const opts = s.options.map((o) => o.v);
          const i = opts.indexOf(this.v[s.key]);
          e.preventDefault();
          this.set(s.key, opts[(i + d + opts.length) % opts.length]);
          const b = seg.querySelector(`[data-v="${this.v[s.key]}"]`);
          if (b) b.focus();
        });
        box.append(seg);
        box._seg = seg;
        box.append(h('small', 'of-desc'));
      } else if (s.type === 'number') {
        box.append(this._stepper(s, id));
        if (s.describe) box.append(h('small', 'of-desc of-num'));
        input = box.querySelector('input');
      } else if (s.type === 'file') {
        input = h('input', null, null, { id, type: 'file' });
        input.addEventListener('change', () => this.set(s.key, input.files[0] || null));
        box.append(input);
      }
      if (s.help && s.type !== 'segmented') box.append(h('small', 'of-help', s.help));
      box.append(h('small', 'of-err', null, { role: 'alert', hidden: true }));
      box._input = input;
      return box;
    }

    _stepper(s, id) {
      const wrap = h('div', 'stp');
      const dec = h('button', 'stp-b', '−', { type: 'button', 'aria-label': `Decrease ${s.label}`, tabindex: '-1' });
      const inc = h('button', 'stp-b', '+', { type: 'button', 'aria-label': `Increase ${s.label}`, tabindex: '-1' });
      const input = h('input', null, null, { id, type: 'text', inputmode: 'numeric', role: 'spinbutton', 'aria-valuemin': s.min, 'aria-valuemax': s.max, placeholder: s.emptyLabel || '' });
      const unit = h('span', 'stp-u', s.unit || '');
      const clampV = (n) => Math.max(s.min, Math.min(s.max, n));
      const bump = (dir, mult = 1) => {
        const cur = this.v[s.key];
        const base = cur === '' || cur === null || cur === undefined ? (dir > 0 ? s.min - s.step : s.min) : Number(cur);
        const next = clampV(base + dir * s.step * mult);
        this.set(s.key, next);
        // _sync skips the focused input (typing guard); bump is always
        // programmatic (keyboard/buttons), so echo the new value directly.
        input.value = String(next);
      };
      // press-and-hold accelerates
      const hold = (btn, dir) => {
        let t = 0; let n = 0;
        const go = () => { bump(dir, n > 12 ? 10 : 1); n += 1; t = setTimeout(go, n < 3 ? 320 : 70); };
        btn.addEventListener('pointerdown', (e) => { e.preventDefault(); if (btn.disabled) return; n = 0; go(); });
        ['pointerup', 'pointerleave', 'pointercancel'].forEach((ev) => btn.addEventListener(ev, () => clearTimeout(t)));
      };
      hold(dec, -1);
      hold(inc, 1);
      input.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowUp') { e.preventDefault(); bump(1, e.shiftKey ? 10 : 1); }
        if (e.key === 'ArrowDown') { e.preventDefault(); bump(-1, e.shiftKey ? 10 : 1); }
      });
      input.addEventListener('input', () => {
        const raw = input.value.trim();
        if (raw === '' && s.optional) { this.set(s.key, ''); return; }
        if (/^-?\d+$/.test(raw)) this.set(s.key, Number(raw));
      });
      input.addEventListener('blur', () => {
        const val = this.v[s.key];
        if (val === '' && s.optional) return;
        if (!isInt(val)) this.set(s.key, s.def === '' ? s.min : s.def);
        else this.set(s.key, clampV(val));
      });
      wrap.append(dec, input, unit, inc);
      return wrap;
    }

    _sync() {
      Object.entries(this.nodes).forEach(([k, box]) => {
        const s = spec(k, this.ctx);
        const val = this.v[k];
        const locked = this.disabled || (s.lockedIf && s.lockedIf(this.v)) || (s.enabledIf && !s.enabledIf(this.v));
        box.classList.toggle('locked', !!locked);
        const i = box._input;
        if (s.type === 'toggle') { i.checked = !!val; i.disabled = !!locked; }
        else if (s.type === 'segmented') {
          box._seg.querySelectorAll('button').forEach((b) => { const on = b.dataset.v === val; b.setAttribute('aria-checked', String(on)); b.tabIndex = on ? 0 : -1; b.disabled = !!this.disabled; });
          const opt = (s.options || []).find((o) => o.v === val);
          box.querySelector('.of-desc').textContent = opt && opt.d ? opt.d : '';
        } else if (s.type === 'number') {
          if (document.activeElement !== i) i.value = val === '' || val === undefined || val === null ? '' : String(val);
          i.disabled = !!locked;
          i.setAttribute('aria-valuenow', val === '' ? '' : val);
          const [dec, inc] = box.querySelectorAll('.stp-b');
          dec.disabled = !!locked || (val !== '' && val <= s.min);
          inc.disabled = !!locked || (val !== '' && val >= s.max);
          const u = box.querySelector('.stp-u');
          u.textContent = s.unit || '';
          const nd = box.querySelector('.of-num');
          if (nd) nd.textContent = s.describe && isInt(val) ? s.describe(val) : '';
        } else if (s.type === 'file') { i.disabled = !!locked; }
        else if (i) { if (document.activeElement !== i && i.value !== String(val ?? '')) i.value = val ?? ''; i.disabled = !!locked; }
        // "not used by this source" hint
        const src = SOURCES[this.ctx.source];
        const na = box.querySelector('.ob.na');
        if (na && src && FIELDS[k].group === 'run') {
          const used = FIELDS[k].wire === 'query' ? !src.noQuery : src.run.includes(k);
          na.hidden = used;
          box.classList.toggle('unused', !used);
        } else if (na) na.hidden = true;
      });
    }

    // Validate required + field validators. Returns [messages]; marks fields.
    validate(required = []) {
      const errs = [];
      Object.entries(this.nodes).forEach(([k, box]) => {
        const s = spec(k, this.ctx);
        const val = this.v[k];
        let msg = '';
        const empty = val === '' || val === null || val === undefined;
        if (required.includes(k) && (empty || (typeof val === 'string' && !val.trim()))) msg = `${s.label} is required.`;
        else if (!empty && s.type === 'number' && (!isInt(val) || val < s.min || val > s.max)) msg = `${s.label} must be a whole number from ${s.min} to ${s.max}.`;
        else if (!empty && s.validate) msg = s.validate(typeof val === 'string' ? val.trim() : val, this.ctx);
        else if (s.type === 'toggle' && s.validate) msg = s.validate(val, this.ctx);
        const e = box.querySelector('.of-err');
        if (e) { e.hidden = !msg; e.textContent = msg; }
        if (box._input) { if (msg) box._input.setAttribute('aria-invalid', 'true'); else box._input.removeAttribute('aria-invalid'); }
        if (msg) errs.push(msg);
      });
      return errs;
    }
  }

  Object.assign(O, { OptionForm });
})();
