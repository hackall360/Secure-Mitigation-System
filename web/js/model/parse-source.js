// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · model/parse-source.js — real topology parsed from a pasted JS / Python / PHP snippet (regex based, in-browser).
// Extend: add patterns to SINKS / INPUTS for a language, or a new language key.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const T = (SMS.topology = SMS.topology || {});
  const { builder, addSandbox, slug } = T;

  const SINKS = {
    javascript: [/\beval\s*\(/, /\bnew Function\s*\(/, /child_process|\bexecSync?\s*\(|\bspawn(Sync)?\s*\(/, /\.query\s*\(/, /\.innerHTML\s*=/, /\bres\.send\s*\(/, /\bfs\.(readFile|writeFile|createReadStream)\w*\s*\(/, /\bnew RegExp\s*\(/, /\bvm\.run\w*\s*\(/],
    python: [/\beval\s*\(/, /\bexec\s*\(/, /\bos\.system\s*\(/, /\bsubprocess\.\w+\s*\(/, /\.execute\s*\(/, /\bpickle\.loads?\s*\(/, /\byaml\.load\s*\(/, /\bopen\s*\(/, /render_template_string\s*\(/],
    php: [/\b(shell_exec|exec|system|passthru|popen|proc_open)\s*\(/, /\beval\s*\(/, /\bmysqli?_query\s*\(|->query\s*\(/, /\b(include|require)(_once)?\s*\(?\s*\$/, /\bunserialize\s*\(/, /\becho\s+\$_(GET|POST|REQUEST)/, /\bfile_get_contents\s*\(\s*\$/]
  };
  const INPUTS = {
    javascript: /\breq\.(query|body|params|headers|cookies)(\.\w+|\[['"][^'"]+['"]\])?|process\.argv(\[\d+\])?|location\.(search|hash)/g,
    python: /\brequest\.(args|form|json|values|cookies)(\.get\(['"][^'"]+['"]\)|\[['"][^'"]+['"]\])?|sys\.argv(\[\d+\])?|\binput\s*\(/g,
    php: /\$_(GET|POST|REQUEST|COOKIE|SERVER)(\[['"][^'"]+['"]\])?/g
  };

  function fromSource(source, language = 'javascript', filename = 'snippet') {
    const lang = SINKS[language] ? language : 'javascript';
    const src = String(source || '');
    const b = builder({ label: filename, sub: `${lang} · ${src.split('\n').length} lines · parsed` }, 'parsed');
    const lines = src.split('\n');

    // functions with their line spans
    const fnRe = lang === 'python' ? /^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(/ : lang === 'php' ? /\bfunction\s+([A-Za-z_]\w*)\s*\(/ : /(?:\bfunction\s+([A-Za-z_$][\w$]*)\s*\(|\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>))/;
    const fns = [];
    lines.forEach((line, i) => { const m = fnRe.exec(line); if (m) fns.push({ name: m[1] || m[2], start: i }); });
    fns.forEach((f, i) => { f.end = i + 1 < fns.length ? fns[i + 1].start - 1 : lines.length - 1; });
    const scope = (i) => fns.find((f) => i >= f.start && i <= f.end) || null;

    // routes
    const routeRe = lang === 'python' ? /@\w+\.(?:route|get|post|put|delete)\(\s*['"]([^'"]+)['"](?:[^)]*methods=\[([^\]]+)\])?/ : /\b(?:app|router|server)\.(get|post|put|delete|patch|all|use)\(\s*['"`]([^'"`]+)['"`]/;
    const routes = [];
    lines.forEach((line, i) => {
      const m = routeRe.exec(line);
      if (!m) return;
      const path = lang === 'python' ? m[1] : m[2];
      const verb = lang === 'python' ? (m[2] ? m[2].replace(/['"\s]/g, '').split(',')[0] : 'GET') : m[1].toUpperCase();
      routes.push({ label: `${verb.toUpperCase()} ${path}`, line: i });
    });

    const inputs = new Map();
    const sinks = [];
    lines.forEach((line, i) => {
      (line.match(INPUTS[lang]) || []).forEach((m) => { if (!inputs.has(m)) inputs.set(m, i); });
      SINKS[lang].forEach((re) => {
        const m = re.exec(line);
        if (m) sinks.push({ label: m[0].replace(/\s+/g, '').replace(/\($/, '()').slice(0, 26), line: i });
      });
    });
    const imports = [];
    const impRe = lang === 'python' ? /^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))/ : lang === 'php' ? /\b(?:require|include)(?:_once)?\s*\(?\s*['"]([^'"]+)['"]/ : /\brequire\(\s*['"]([^'"]+)['"]\)|\bimport\s+[^'"]*from\s+['"]([^'"]+)['"]/;
    lines.forEach((line) => { const m = impRe.exec(line); if (m) { const v = m[1] || m[2]; if (v && !imports.includes(v)) imports.push(v); } });

    const entry = b.add('entry', 'Entry points', 'subsystem', 'core', { sub: `${routes.length} routes · ${inputs.size} inputs` });
    const code = b.add('code', 'Functions', 'subsystem', 'core', { sub: `${fns.length} defined` });
    const sinkSub = b.add('sinks', 'Sinks', 'subsystem', 'core', { sub: `${sinks.length} dangerous calls` });
    const deps = imports.length ? b.add('deps', 'Imports', 'subsystem', 'core', { sub: `${imports.length} modules` }) : null;
    addSandbox(b);

    const routeIds = routes.slice(0, 8).map((r, i) => ({ id: b.add(`route-${i}`, r.label, 'endpoint', entry, { sub: `line ${r.line + 1}` }), line: r.line }));
    const inputIds = [...inputs.entries()].slice(0, 8).map(([label, line], i) => ({ id: b.add(`in-${i}`, label.slice(0, 28), 'endpoint', entry, { sub: `line ${line + 1}` }), line }));
    const fnIds = fns.slice(0, 14).map((f, i) => ({ id: b.add(`fn-${slug(f.name)}-${i}`, `${f.name}()`, 'function', code, { sub: `L${f.start + 1}-${f.end + 1}` }), f }));
    const sinkIds = sinks.slice(0, 8).map((s, i) => ({ id: b.add(`sink-${i}`, s.label, 'sink', sinkSub, { sub: `line ${s.line + 1}` }), line: s.line }));
    imports.slice(0, 10).forEach((m, i) => b.add(`imp-${i}`, m.slice(0, 26), 'import', deps));

    const fnOf = (line) => { const f = scope(line); return f ? fnIds.find((x) => x.f === f) : null; };
    const paths = [];
    sinkIds.forEach((s) => {
      const f = fnOf(s.line);
      const fid = f ? f.id : null;
      const inp = inputIds.find((x) => (f ? x.line >= f.f.start && x.line <= f.f.end : true)) || inputIds[0];
      const route = routeIds.find((r) => (f ? Math.abs(r.line - f.f.start) <= 2 || (r.line <= s.line && s.line <= (f.f.end)) : r.line <= s.line)) || null;
      const path = [route && route.id, inp && inp.id, fid, s.id].filter(Boolean);
      if (path.length >= 2) { b.chain(path); paths.push(path); }
    });
    routeIds.forEach((r) => { const f = fnOf(r.line + 1) || fnOf(r.line); if (f && !paths.some((p) => p.includes(r.id))) b.chain([r.id, f.id]); });

    const attack = paths[0] || [];
    return b.done({ lens: 'file', attackPath: attack, entryId: attack[0] || null, sinkId: attack[attack.length - 1] || null, guardLink: attack.length >= 2 ? attack.slice(-2) : null, findings: { functions: fns.length, routes: routes.length, inputs: inputs.size, sinks: sinks.length, imports: imports.length } });
  }

  Object.assign(T, { SINKS, INPUTS, fromSource });
})();
