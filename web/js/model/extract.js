// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · model/extract.js — entities named in live stream lines (files, fn(), VERB /routes, CVE/GHSA ids, ports, exit codes).
// The interpreter adds these to the map as they appear.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const T = (SMS.topology = SMS.topology || {});
  const FILE_RE = /(?:^|[\s'"`(\[])((?:[\w.-]+\/)*[\w.-]+\.(?:js|mjs|cjs|ts|tsx|php|py|rb|go|rs|c|h|cc|cpp|java|kt|sql|cnf|conf|ini|json|ya?ml|toml|sh|html|lock))\b/g;
  const FN_RE = /\b([A-Za-z_][\w.$]{2,40})\(\)/g;
  const ROUTE_RE = /\b(GET|POST|PUT|PATCH|DELETE)\s+(\/[\w\-/{}:.?=&]*)/g;
  const CVE_RE = /\b(CVE-\d{4}-\d{4,7}|GHSA-[\w]{4}-[\w]{4}-[\w]{4})\b/gi;
  const EXIT_RE = /boundary check exited\s+(\d+)|\bexit(?:ed)?\s+(?:code\s+)?(\d+)\b/i;
  const PORT_RE = /\b(\d{2,5})\/(tcp|udp)\b/g;

  function extract(text) {
    const s = String(text || '');
    const all = (re, pick) => { const out = []; re.lastIndex = 0; let m; while ((m = re.exec(s)) && out.length < 6) { const v = pick(m); if (v && !out.includes(v)) out.push(v); } return out; };
    const exit = EXIT_RE.exec(s);
    return {
      files: all(FILE_RE, (m) => m[1]).filter((f) => !/^\d/.test(f) && f.length < 64),
      fns: all(FN_RE, (m) => `${m[1]}()`),
      routes: all(ROUTE_RE, (m) => `${m[1]} ${m[2]}`),
      cves: all(CVE_RE, (m) => m[1].toUpperCase()),
      ports: all(PORT_RE, (m) => `${m[1]}/${m[2]}`),
      exit: exit ? Number(exit[1] !== undefined ? exit[1] : exit[2]) : null
    };
  }

  Object.assign(T, { extract });
})();
