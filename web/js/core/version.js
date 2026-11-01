// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · core/version.js — name, version, description and build notes shown on the
// start page (Version info). Bump `version` / `date` and append to `changes` on each release.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});

  const VERSION = {
    name: 'Secure Mitigation System',
    short: 'SMS',
    version: '3.1.0',
    ui: 'Web UI v3',
    channel: 'hackathon build',
    date: '2026-10-31',
    description: 'Boundary verification with an agent swarm on Meta Muse. Red agents prove a flaw inside an isolated Docker sandbox, blue agents write the smallest patch, and purple agents re-probe a fresh copy and sign a verdict receipt. Evidence decides every verdict.',
    contract: ['GET /api/health', 'GET /api/targets', 'WS /ws/combat/:target', 'WS /ws/project', 'WS /ws/demo', 'WS /ws/binary', 'POST /mcp', 'WS /ws/system (proposed)'],
    changes: [
      'Radial spider-web system map with six color-coded agent families and 22 personalities',
      'Live communication bubbles, data-flow particles, taint, guard and verified states',
      'Real-time stream rendering: burst pacing, working indicator, stream meter, server timestamps',
      'Schema-driven run controls: operational modes, switches, steppers, request preview',
      'Separate Demo and Production flows with their own selection screens',
      'Client-side snippet and ELF parsing for real topology',
      'Visualizer test bench for simulated runs',
      'Four lenses: single file (a page), repository (a city), binary (a machine), system snapshot (a house with doors)',
      'Explain switch: plain words, both, or expert detail — narrated phases, events and verdicts',
      'System snapshot source with a services parser, showcase repo and system targets'
    ]
  };

  SMS.version = VERSION;
  SMS.launch = Object.assign(SMS.launch || {}, { VERSION });
})();
