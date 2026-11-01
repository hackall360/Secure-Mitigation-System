// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · options/schema.js — THE run-options schema: ONE schema for every switch, text input, stepper and
// operational mode, rendered by both pages and compiled into the exact request
// the orchestrator receives. To add / rename a backend parameter, edit FIELDS
// (and SOURCES if it belongs to a source) — the UI, validation, persistence and
// request preview follow automatically.
//
// wire:   'body'  → JSON body key        (sent only for sources whose endpoint takes a body)
//         'query' → URL query parameter   (sent for every streaming source)
//         'ui'    → never sent; only shapes other values
// proposed: true  → shown with a "proposed" badge; sent only when "Send proposed controls"
//                   is on, as body.ui_options{} (or ?opt_<key>= when there is no body).
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const O = (SMS.options = SMS.options || {});

  /* ------------------------------------------------------------------ */
  /* Operational modes (scan intensity). Server health.scan_profiles     */
  /* overrides cycles/description at runtime.                            */
  /* ------------------------------------------------------------------ */
  const MODES = [
    { v: 'extra_light', l: 'Extra light', cycles: 1, d: '1 cycle · Red, Blue, Red, Blue' },
    { v: 'light', l: 'Light', cycles: 3, d: '3 cycles with cumulative focus' },
    { v: 'medium', l: 'Medium', cycles: 5, d: '5 cycles with cumulative focus' },
    { v: 'heavy', l: 'Heavy', cycles: 8, d: '8 cycles with cumulative focus' },
    { v: 'super_heavy', l: 'Super heavy', cycles: 12, d: '12 cycles with cumulative focus' },
    { v: 'ultra_heavy', l: 'Ultra heavy', cycles: 12, d: '12 cycles · tunable agent swarm · bounded auto-discovery' },
    { v: 'custom', l: 'Custom', cycles: null, d: 'Legacy single-pass cycles, 1–20' }
  ];
  const SWEEP_LABELS = { 1: 'single finding', 2: '+ deep pass', 3: '+ threat-actor pass', 4: '+ chain pass' };

  /* ------------------------------------------------------------------ */
  /* Fields                                                              */
  /* ------------------------------------------------------------------ */
  const isInt = (v) => Number.isInteger(v);
  const argv = (s) => { try { const a = JSON.parse(s); return Array.isArray(a) && a.length && a.every((x) => typeof x === 'string' && x) ? a : null; } catch { return null; } };

  const FIELDS = {
    // ---- operational mode + run sizing
    scan_profile: { type: 'segmented', group: 'run', label: 'Operational mode', wire: 'body', def: 'extra_light', options: MODES, demo: { options: ['extra_light', 'light'] } },
    cycles: { type: 'number', group: 'run', label: 'Cycles', wire: 'body', def: 1, min: 1, max: 20, step: 1, help: 'Derived from the mode unless Custom.', lockedIf: (v) => v.scan_profile !== 'custom', demo: { max: 3 } },
    red_agents: { type: 'number', group: 'run', label: 'Red agents', wire: 'body', def: 5, min: 1, max: 12, step: 1, unit: 'agents', help: 'Tunable in Ultra heavy.', lockedIf: (v) => v.scan_profile !== 'ultra_heavy', demo: { max: 5 } },
    blue_agents: { type: 'number', group: 'run', label: 'Blue agents', wire: 'body', def: 5, min: 1, max: 12, step: 1, unit: 'agents', help: 'Tunable in Ultra heavy.', lockedIf: (v) => v.scan_profile !== 'ultra_heavy', demo: { max: 5 } },
    context_budget: { type: 'number', group: 'run', label: 'Context budget', wire: 'body', def: 32768, min: 1024, max: 131072, step: 1024, unit: 'tokens', demo: { max: 32768 } },
    sweep_passes: { type: 'number', group: 'run', label: 'Sweep depth', wire: 'query', def: 1, min: 1, max: 4, step: 1, unit: 'passes', describe: (n) => SWEEP_LABELS[n] || '', omitIf: (n) => n === 1, demo: { max: 2 } },
    profile: { type: 'select', group: 'run', label: 'Model profile', wire: 'query', def: '', options: [], hideIfEmpty: true },
    research: { type: 'toggle', group: 'run', label: 'Ground with threat intel', help: 'OSV, CIRCL, GHSA, EPSS. Docker evidence still decides.', wire: 'query', def: false, encode: (on) => (on ? 'on' : undefined) },
    research_scanners: { type: 'toggle', group: 'run', label: 'Run local scanners', help: 'Trivy, Grype, OSV-Scanner, Dependency-Check, Dependency-Track.', wire: 'query', def: false, enabledIf: (v) => v.research, encode: (on, v) => (on && v.research ? 'trivy,grype,osv-scanner,dependency-check,dependency-track' : undefined), demo: { hidden: true } },

    // ---- proposed runtime controls (not sent unless enabled)
    max_runtime_min: { type: 'number', group: 'proposed', label: 'Max runtime', wire: 'body', proposed: true, def: 30, min: 1, max: 240, step: 1, unit: 'min', help: 'Hard stop for the whole run.' },
    probe_timeout_s: { type: 'number', group: 'proposed', label: 'Probe timeout', wire: 'body', proposed: true, def: 60, min: 5, max: 600, step: 5, unit: 's' },
    parallel_probes: { type: 'number', group: 'proposed', label: 'Parallel probes', wire: 'body', proposed: true, def: 1, min: 1, max: 8, step: 1 },
    require_regression: { type: 'toggle', group: 'proposed', label: 'Require regression pass', help: 'Reject a patch whose normal-input checks fail.', wire: 'body', proposed: true, def: true },
    auto_rollback: { type: 'toggle', group: 'proposed', label: 'Auto-rollback on failure', wire: 'body', proposed: true, def: true },
    stream_verbosity: { type: 'segmented', group: 'proposed', label: 'Stream verbosity', wire: 'body', proposed: true, def: 'normal', options: [{ v: 'quiet', l: 'Quiet' }, { v: 'normal', l: 'Normal' }, { v: 'verbose', l: 'Verbose' }] },
    run_label: { type: 'text', group: 'proposed', label: 'Run label', wire: 'body', proposed: true, def: '', max: 80, placeholder: 'release-2026-11 · staging' },

    // ---- Green build
    build_brief: { type: 'text', label: 'What should Greenhouse build?', wire: 'body', def: '', max: 500, placeholder: 'a tiny note-taking web app with login' },
    vulns: { type: 'text', label: 'Vulnerabilities to implement', wire: 'body', def: '', max: 500, placeholder: 'SQL injection, header reflection', help: 'CVEs, named classes or free text, comma separated.' },
    theme: { type: 'text', label: 'Extra flaw themes', wire: 'body', def: '', max: 200, optional: true },
    demo_size: { type: 'segmented', label: 'Demo size', wire: 'body', def: 'standard', options: [{ v: 'standard', l: 'Standard' }, { v: 'small', l: 'Small' }], demo: { def: 'small' } },
    flaw_count: { type: 'number', label: 'Flaw count', wire: 'body', def: '', min: 1, max: 8, step: 1, optional: true, emptyLabel: 'all', demo: { max: 3, def: 1 } },
    seed: { type: 'number', label: 'Seed', wire: 'body', def: '', min: -2147483648, max: 2147483647, step: 1, optional: true, emptyLabel: 'random' },
    build_offline: { type: 'toggle', label: 'Build offline', help: 'Skip live threat-intel lookups.', wire: 'ui', def: false },
    allow_remote_build: { type: 'toggle', label: 'Allow generated source to leave this host', help: 'Without it the demo builds offline.', wire: 'ui', def: false },

    // ---- Project
    path: { type: 'text', label: 'Absolute repository path', wire: 'body', def: '', placeholder: '/home/me/src/my-project', validate: (s) => (s.startsWith('/') ? '' : 'Repository path must be absolute.') },
    image: { type: 'text', label: 'Preloaded sandbox image', wire: 'body', def: '', placeholder: 'purplebox-node:latest' },
    command: { type: 'code', label: 'Start command', badge: 'JSON argv', wire: 'body', def: '', rows: 2, placeholder: '["npm", "start"]', parse: argv, validate: (s) => (argv(s) ? '' : 'Start command must be a JSON array of strings.') },
    test_command: { type: 'code', label: 'Regression test command', badge: 'JSON argv', wire: 'body', def: '', rows: 2, placeholder: '["npm", "test"]', parse: argv, validate: (s) => (argv(s) ? '' : 'Test command must be a JSON array of strings.') },
    contract: { type: 'textarea', label: 'Behavior contract', wire: 'body', def: '', rows: 3, placeholder: 'Behavior that must remain true, and the input boundary to verify.' },
    allow_remote_inference: { type: 'toggle', label: 'Allow source to leave this host', help: 'Source and analysis context may be sent to the configured Muse endpoint.', wire: 'body', def: false, validate: (on, ctx) => (on || ctx.inferenceMode === 'local' ? '' : 'Confirm that source may be sent to the configured Muse endpoint.') },

    // ---- Snippet (MCP)
    language: { type: 'segmented', label: 'Language', wire: 'body', def: 'javascript', options: [{ v: 'javascript', l: 'JavaScript' }, { v: 'python', l: 'Python' }, { v: 'php', l: 'PHP' }] },
    filename: { type: 'text', label: 'Filename', wire: 'body', def: '', max: 128, placeholder: 'app.js', optional: true, validate: (s) => (/[\\/]/.test(s) ? 'Filename must be a bare name, no paths.' : '') },
    source: { type: 'code', label: 'Source', badge: 'max 64 KiB · mapped as you type', wire: 'body', def: '', rows: 9, placeholder: 'Paste code — functions, routes, inputs and sinks appear on the map instantly.', validate: (s) => (new Blob([s]).size > 65536 ? 'Snippet exceeds 64 KiB.' : '') },

    // ---- Binary
    binary: { type: 'file', label: 'Compiled binary', badge: 'ELF · PE · Mach-O · 8 MiB', wire: 'ui', help: 'Parsed in your browser. Bytes leave only when you run.' },

    // ---- System snapshot (proposed endpoint /ws/system)
    snapshot_ref: { type: 'text', label: 'Snapshot / clone reference', wire: 'body', def: '', max: 200, placeholder: 'registry.local/shop-stack@sha256:… · ./compose.yml · vm-snap-0420', validate: (s) => (s.trim() ? '' : 'Name the snapshot, image, compose file or clone to restore.') },
    snapshot_kind: { type: 'segmented', label: 'Snapshot kind', wire: 'body', def: 'compose', options: [{ v: 'image', l: 'Container image' }, { v: 'compose', l: 'Compose stack' }, { v: 'vm', l: 'VM snapshot' }, { v: 'clone', l: 'Live clone' }] },
    services: { type: 'code', label: 'Services & ports', badge: 'one per line · mapped as you type', wire: 'body', def: '', rows: 6, placeholder: 'edge   nginx:1.25   443   public  -> app\napp    node:20      3000          -> db\ndb     postgres:16  5432', help: 'name · image · ports · public · -> talks-to. Public ports become doors in the wall.', validate: (s) => (/\S/.test(s) ? '' : 'List at least one service.') },

    // ---- Repo ingest
    ingest_repo: { type: 'text', label: 'Repository URL', wire: 'body', def: '', placeholder: 'https://github.com/org/repo', validate: (s) => (/^https:\/\/\S+$/.test(s) ? '' : 'Enter an https:// repository URL.') },
    commit_hash: { type: 'text', label: 'Pinned commit', wire: 'body', def: '', max: 40, placeholder: '40-hex commit sha', validate: (s) => (/^[0-9a-fA-F]{40}$/.test(s) ? '' : 'Enter the full 40-hex pinned commit.') }
  };

  const RUN = ['scan_profile', 'cycles', 'red_agents', 'blue_agents', 'context_budget', 'sweep_passes', 'profile', 'research', 'research_scanners'];
  const PROPOSED = Object.keys(FIELDS).filter((k) => FIELDS[k].proposed);

  // Source = what is being verified. `run` lists which run fields the endpoint body accepts.
  const SOURCES = {
    fixture: { label: 'Fixture', sub: 'Bundled target', endpoint: (v, x) => `/ws/combat/${encodeURIComponent(x.fixture || '')}`, fields: [], body: false, run: [] },
    build: { label: 'Green build', sub: 'Grow a demo', endpoint: () => '/ws/demo', fields: ['build_brief', 'vulns', 'theme', 'demo_size', 'flaw_count', 'seed', 'build_offline', 'allow_remote_build'], body: true, run: ['scan_profile', 'cycles', 'red_agents', 'blue_agents', 'context_budget'] },
    project: { label: 'Project', sub: 'Local repo', endpoint: () => '/ws/project', fields: ['path', 'image', 'command', 'test_command', 'contract', 'allow_remote_inference'], body: true, run: ['scan_profile', 'cycles', 'red_agents', 'blue_agents', 'context_budget'] },
    snippet: { label: 'Snippet', sub: 'MCP · parsed map', endpoint: () => 'POST /mcp', fields: ['language', 'filename', 'source', 'contract'], body: true, run: [], noQuery: true },
    binary: { label: 'Binary', sub: 'ELF · parsed map', endpoint: () => '/ws/binary', fields: ['binary', 'filename', 'contract'], body: true, run: [] },
    ingest: { label: 'Repo ingest', sub: 'Pinned commit', endpoint: () => '/ws/project', fields: ['ingest_repo', 'commit_hash'], body: true, run: [] },
    system: { label: 'System snapshot', sub: 'Clone · proposed', endpoint: () => '/ws/system', fields: ['snapshot_ref', 'snapshot_kind', 'services', 'contract'], body: true, run: ['scan_profile', 'cycles', 'red_agents', 'blue_agents', 'context_budget'], proposed: true }
  };
  // Which lens (core/lenses.js) each source is drawn with. Fixtures use the fixture's own lens.
  const SOURCE_LENS = { fixture: null, build: 'file', project: 'repo', snippet: 'file', binary: 'binary', ingest: 'repo', system: 'system' };
  const REQUIRED = { build: [], project: ['path', 'image', 'command', 'test_command', 'contract'], snippet: ['source', 'contract'], binary: ['contract'], ingest: ['ingest_repo', 'commit_hash'], system: ['snapshot_ref', 'services', 'contract'], fixture: [] };

  /* ------------------------------------------------------------------ */
  /* Context: limits for the demo page, server overrides                 */
  /* ------------------------------------------------------------------ */
  function spec(key, ctx) {
    const f = FIELDS[key];
    if (!f) return null;
    const out = Object.assign({ key }, f);
    if (ctx.page === 'demo' && f.demo) Object.assign(out, f.demo);
    if (key === 'scan_profile') {
      out.options = MODES.map((m) => {
        const srv = (ctx.scanProfiles || []).find((p) => p.key === m.v);
        return Object.assign({}, m, srv ? { cycles: srv.cycles, d: srv.description || m.d } : {});
      });
      if (ctx.page === 'demo' && f.demo) out.options = out.options.filter((o) => f.demo.options.includes(o.v));
    }
    if (key === 'profile') out.options = (ctx.models || []).map((p) => ({ v: p.key, l: p.label, d: p.description || `Red ${p.red_model} · Blue ${p.blue_model}` }));
    return out;
  }

  function defaults(keys, ctx) {
    const v = {};
    keys.forEach((k) => { const s = spec(k, ctx); if (s) v[k] = s.def; });
    if (keys.includes('profile') && ctx.defaultModel) v.profile = ctx.defaultModel;
    return v;
  }

  function modeCycles(v, ctx) {
    const m = spec('scan_profile', ctx).options.find((o) => o.v === v.scan_profile);
    return m && m.cycles ? m.cycles : null;
  }

  Object.assign(O, { FIELDS, MODES, SWEEP_LABELS, RUN, PROPOSED, SOURCES, SOURCE_LENS, REQUIRED, spec, defaults, modeCycles, isInt });
})();
