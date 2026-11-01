// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · palette + agent registry.
// Six agent families, one hue each. Every agent inside a family is a lighter or
// darker variant of that hue, so "same team, different personality" reads at a glance.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});

  // Family base colors + the angular sector each family occupies on the outer orbit.
  // Angles are canvas radians (0 = east, +PI/2 = south).
  const TEAMS = {
    red:    { key: 'red',    label: 'Red · Offense',        short: 'RED', kidShort: 'ATTACKERS',    hue: '#ff3b5c', soft: 'rgba(255,59,92,0.16)',  angle: Math.PI,              blurb: 'Proves the flaw inside the sandbox.', kid: 'The pretend burglars. They try to break in — only ever on a copy.' },
    yellow: { key: 'yellow', label: 'Yellow · Intel',        short: 'INTEL', kidShort: 'RESEARCHERS',  hue: '#facc15', soft: 'rgba(250,204,21,0.16)', angle: Math.PI * 4 / 3,      blurb: 'Grounds findings with CVE / OSV / EPSS.', kid: 'The librarians. They look up problems people have found before.' },
    orange: { key: 'orange', label: 'Orange · Orchestrator', short: 'ORCH', kidShort: 'STAGE CREW',   hue: '#fb923c', soft: 'rgba(251,146,60,0.16)', angle: Math.PI * 5 / 3,      blurb: 'Owns sandboxes, networks, telemetry.', kid: 'The stage crew. They build the sealed test room and clean it up.' },
    blue:   { key: 'blue',   label: 'Blue · Defense',        short: 'BLUE', kidShort: 'DEFENDERS',   hue: '#38bdf8', soft: 'rgba(56,189,248,0.16)', angle: 0,                    blurb: 'Writes the minimal sanitizing patch.', kid: 'The locksmiths. They fix the weak spot with the smallest change.' },
    purple: { key: 'purple', label: 'Purple · Verification', short: 'PURPLE', kidShort: 'REFEREES', hue: '#b06cff', soft: 'rgba(176,108,255,0.16)', angle: Math.PI / 3,          blurb: 'Re-probes, regresses, signs receipts.', kid: 'The referees. They check the fix really works, then sign for it.' },
    green:  { key: 'green',  label: 'Green · Builder',       short: 'GREEN', kidShort: 'BUILDERS',  hue: '#34f5a2', soft: 'rgba(52,245,162,0.16)', angle: Math.PI * 2 / 3,      blurb: 'Grows disposable vulnerable fixtures.', kid: 'The builders. They make practice targets, like a fire drill.' }
  };
  const TEAM_ORDER = ['red', 'yellow', 'orange', 'blue', 'purple', 'green'];

  // Personalities. `color` is the family hue shifted lighter/darker.
  // `leader` agents sit at the center of the family arc and speak for unnamed lines.
  const AGENTS = [
    { id: 'Warlord',      team: 'red',    color: '#ff2d55', leader: true, glyph: 'W', personality: 'Commander', role: 'Plans the kill chain, assigns probes' },
    { id: 'Breakwater',   team: 'red',    color: '#ff6b81', glyph: 'Bw', personality: 'Methodical', role: 'Walks every input boundary in order' },
    { id: 'Lockpick',     team: 'red',    color: '#c8102e', glyph: 'Lp', personality: 'Opportunist', role: 'Hunts auth, access and argv seams' },
    { id: 'Bloodhound',   team: 'red',    color: '#ff9aab', glyph: 'Bh', personality: 'Tracker', role: 'Follows tainted data to the sink' },
    { id: 'Sparkler',     team: 'red',    color: '#ff4f3a', glyph: 'Sp', personality: 'Chaotic', role: 'Mutation fuzzing, odd encodings' },
    { id: 'Cartographer', team: 'red',    color: '#9f1239', glyph: 'Ca', personality: 'Mapper', role: 'Recon of routes, files and symbols' },

    { id: 'Warden',       team: 'blue',   color: '#1fb6ff', leader: true, glyph: 'W', personality: 'Commander', role: 'Triages findings, assigns fixes' },
    { id: 'Bastion',      team: 'blue',   color: '#7dd3fc', glyph: 'Ba', personality: 'Hardener', role: 'Adds the smallest effective guard' },
    { id: 'Stitch',       team: 'blue',   color: '#0284c7', glyph: 'St', personality: 'Surgeon', role: 'Writes precise, bounded diffs' },
    { id: 'Librarian',    team: 'blue',   color: '#a5d8ff', glyph: 'Li', personality: 'Archivist', role: 'Recalls prior fixes from the vault' },
    { id: 'Sentinel',     team: 'blue',   color: '#38bdf8', glyph: 'Se', personality: 'Watcher', role: 'Guards normal-input behavior' },
    { id: 'Proofreader',  team: 'blue',   color: '#075985', glyph: 'Pr', personality: 'Reviewer', role: 'Lints the patch before submit' },

    { id: 'Arbiter',      team: 'purple', color: '#b06cff', leader: true, glyph: 'A', personality: 'Judge', role: 'Decides verdicts from Docker evidence' },
    { id: 'Notary',       team: 'purple', color: '#d4b0ff', glyph: 'No', personality: 'Custodian', role: 'Hashes and chains verdict receipts' },
    { id: 'Mirror',       team: 'purple', color: '#7c3aed', glyph: 'Mi', personality: 'Differential', role: 'Compares pre / post behavior' },

    { id: 'Greenhouse',   team: 'green',  color: '#34f5a2', leader: true, glyph: 'G', personality: 'Builder', role: 'Grows fresh vulnerable demos' },
    { id: 'Seedling',     team: 'green',  color: '#a7f3d0', glyph: 'Sd', personality: 'Scaffolder', role: 'Plants routes, data and fixtures' },

    { id: 'Almanac',      team: 'yellow', color: '#facc15', leader: true, glyph: 'Al', personality: 'Researcher', role: 'CVE / OSV / GHSA / EPSS lookups' },
    { id: 'Lantern',      team: 'yellow', color: '#fde68a', glyph: 'La', personality: 'Scanner', role: 'Trivy, Grype, OSV-Scanner sweeps' },

    { id: 'Conductor',    team: 'orange', color: '#fb923c', leader: true, glyph: 'C', personality: 'Orchestrator', role: 'Sandbox, network and snapshot lifecycle' },
    { id: 'Gauge',        team: 'orange', color: '#fdba74', glyph: 'Ga', personality: 'Telemetry', role: 'Tokens, cost and compression' },
    { id: 'Courier',      team: 'orange', color: '#c2410c', glyph: 'Co', personality: 'Ingest', role: 'Clones pinned repos into staging' }
  ];

  // Backend team names -> family.
  const TEAM_ALIAS = { red: 'red', blue: 'blue', green: 'green', research: 'yellow', system: 'orange', telemetry: 'orange', ingest: 'orange', purple: 'purple', verify: 'purple', yellow: 'yellow', orange: 'orange' };
  const DEFAULT_SPEAKER = { red: 'Warlord', blue: 'Warden', green: 'Greenhouse', research: 'Almanac', yellow: 'Almanac', system: 'Conductor', orange: 'Conductor', telemetry: 'Gauge', ingest: 'Courier', purple: 'Arbiter', verify: 'Arbiter' };

  // Structural-node states (nodes of the target, not agents).
  const STATE = {
    idle:        { color: '#7f93b0', label: 'unvisited', kid: 'not looked at yet' },
    scanned:     { color: '#cfe3ff', label: 'mapped', kid: 'looked at' },
    suspect:     { color: '#facc15', label: 'suspect', kid: 'looks risky' },
    compromised: { color: '#ff3b5c', label: 'reachable', kid: 'a way in works' },
    blocked:     { color: '#38bdf8', label: 'blocked', kid: 'blocked' },
    patched:     { color: '#38bdf8', label: 'patched', kid: 'locked' },
    verified:    { color: '#b06cff', label: 'verified', kid: 'lock proven' },
    grown:       { color: '#34f5a2', label: 'grown', kid: 'just built' },
    intel:       { color: '#facc15', label: 'intel', kid: 'known problem' }
  };

  const STAGES = ['sandbox', 'baseline', 'analysis', 'probe', 'patch', 'regression', 'cleanup'];
  const STAGE_META = {
    sandbox:    { n: '01', label: 'Sandbox',   team: 'orange', caption: 'Conductor isolates the target on an internal Docker network and snapshots it.' },
    baseline:   { n: '02', label: 'Baseline',  team: 'purple', caption: 'Normal-input checks prove the target behaves before anyone touches it.' },
    analysis:   { n: '03', label: 'Recon',     team: 'red',    caption: 'Red maps the attack surface and follows tainted data toward a sink.' },
    probe:      { n: '04', label: 'Probe',     team: 'red',    caption: 'Red proves the flaw with a live probe. Exit 0 means the boundary is reachable.' },
    patch:      { n: '05', label: 'Patch',     team: 'blue',   caption: 'Blue writes the smallest sanitizing patch that closes the boundary.' },
    regression: { n: '06', label: 'Re-verify', team: 'purple', caption: 'A fresh target is re-probed and regression-tested. Evidence, not opinion.' },
    cleanup:    { n: '07', label: 'Cleanup',   team: 'orange', caption: 'Containers, snapshots and networks are torn down. The original stays untouched.' }
  };

  const byId = new Map(AGENTS.map((a) => [a.id, a]));
  const NAME_RE = new RegExp(`\\b(${AGENTS.map((a) => a.id).join('|')})\\b`, 'g');

  function hexToRgb(hex) {
    const h = String(hex).replace('#', '');
    const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function rgba(hex, a) {
    const [r, g, b] = hexToRgb(hex);
    return `rgba(${r},${g},${b},${a})`;
  }
  function mix(hexA, hexB, t) {
    const a = hexToRgb(hexA);
    const b = hexToRgb(hexB);
    const c = a.map((v, i) => Math.round(v + (b[i] - v) * t));
    return `#${c.map((v) => v.toString(16).padStart(2, '0')).join('')}`;
  }

  function family(team) { return TEAM_ALIAS[team] || 'orange'; }
  function agent(id) { return byId.get(id) || null; }
  function teamAgents(team) { return AGENTS.filter((a) => a.team === team); }
  function speakerFor(team) { return DEFAULT_SPEAKER[team] || 'Conductor'; }
  function namesIn(text) {
    const out = [];
    String(text || '').replace(NAME_RE, (m) => { if (!out.includes(m)) out.push(m); return m; });
    return out;
  }

  SMS.palette = { TEAMS, TEAM_ORDER, AGENTS, STATE, STAGES, STAGE_META, TEAM_ALIAS, rgba, mix, hexToRgb, family, agent, teamAgents, speakerFor, namesIn };
})();
