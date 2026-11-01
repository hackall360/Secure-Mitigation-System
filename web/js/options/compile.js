// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · options/compile.js — request compiler: turns form values into exactly what goes on the wire
// ({ endpoint, path(with query), body, query, proposed }). Mirrors the v2 payload shapes.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const O = (SMS.options = SMS.options || {});
  const { FIELDS, SOURCES, RUN, PROPOSED } = O;

  /* ------------------------------------------------------------------ */
  /* Request compiler — exactly what goes on the wire                    */
  /* ------------------------------------------------------------------ */
  // values: merged values of source + run (+ proposed) forms.
  // x: { fixture, sendProposed, inferenceMode }
  function compile(source, values, x = {}) {
    const src = SOURCES[source];
    const v = values;
    const t = (s) => (typeof s === 'string' ? s.trim() : s);
    const body = {};
    const query = {};
    const proposed = {};
    if (src.body) {
      src.fields.forEach((k) => {
        const f = FIELDS[k];
        if (f.wire !== 'body') return;
        let val = t(v[k]);
        if (f.parse && typeof val === 'string') val = f.parse(val);
        if (f.optional && (val === '' || val === undefined || val === null)) return;
        body[k] = val;
      });
      src.run.forEach((k) => { if (k in v) body[k] = v[k]; });
    }
    if (!src.noQuery) {
      RUN.forEach((k) => {
        const f = FIELDS[k];
        if (f.wire !== 'query' || !(k in v)) return;
        let val = v[k];
        if (f.encode) val = f.encode(val, v);
        if (f.omitIf && f.omitIf(val)) return;
        if (val === undefined || val === '' || val === null) return;
        query[k] = val;
      });
    }
    // source-specific shaping (mirrors v2)
    if (source === 'build') {
      body.intel_offline = x.inferenceMode === 'local' || !!v.build_offline || !v.allow_remote_build;
      if (body.flaw_count !== undefined) body.flaw_count = Math.max(1, Math.min(8, Math.trunc(body.flaw_count)));
    }
    if (source === 'project') body.allow_remote_inference = x.inferenceMode !== 'local' && !!v.allow_remote_inference;
    if (source === 'snippet') { body.filename = body.filename || ({ javascript: 'app.js', python: 'app.py', php: 'index.php' }[v.language]); }
    if (source === 'binary') { body.blob_b64 = '<base64 of the selected file>'; body.filename = body.filename || (v.binary && v.binary.name) || ''; }
    if (x.sendProposed) {
      PROPOSED.forEach((k) => { if (k in v && v[k] !== '') proposed[k] = v[k]; });
      if (Object.keys(proposed).length) {
        if (src.body) body.ui_options = proposed;
        else Object.entries(proposed).forEach(([k, val]) => { query[`opt_${k}`] = val; });
      }
    }
    const qs = Object.entries(query).map(([k, val]) => `${encodeURIComponent(k)}=${encodeURIComponent(val)}`).join('&');
    const endpoint = src.endpoint(v, x);
    return { source, endpoint, path: `${endpoint}${qs ? `?${qs}` : ''}`, body: src.body ? body : undefined, query, proposed };
  }

  Object.assign(O, { compile });
})();
