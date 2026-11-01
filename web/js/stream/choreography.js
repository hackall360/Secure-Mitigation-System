// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · stream/choreography.js — what the map DOES for each kind of stream line.
//
// An ordered list of beats. For every line the interpreter walks the list and runs
// the FIRST beat whose when(c) is true. A beat may change:
//   c.to     who the bubble flies to (agent id or node id; null = no bubble)
//   c.label  bubble text ('' = no bubble, the speaker just pulses)
//   c.focus  node the director camera / working indicator should look at
// and may call any graph effect (c.g.flowPath, setState, guard, tether, wave, send, …).
//
// Context c: { g, it (interpreter), team (raw backend team), fam (color family), text, lower,
//   names (agent names in the line), ents (topology extract), stage, speaker, spk (agent record),
//   path (attack path ids), sink, fileId, to, label, focus }
//
// To add behaviour: insert a beat ABOVE the more general beats it should win over.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const P = () => SMS.palette;
  const hue = (fam) => P().TEAMS[fam].hue;
  const label = (g, id, fallback) => ((g.node(id) || {}).label || fallback);

  const BEATS = [
    {
      name: 'green-grows',
      when: (c) => c.fam === 'green',
      run(c) {
        const planted = c.it._grow(/grew|planted|seedling|growing|route|built/.test(c.lower) ? 4 : 2, c.speaker);
        c.focus = planted[0] || 'core';
        if (!c.to) c.to = planted[0] || 'core';
        c.label = c.label || 'GROW';
      }
    },
    {
      name: 'intel-reports',
      when: (c) => c.team === 'research' || c.fam === 'yellow',
      run(c) {
        if (!c.to) c.to = 'Warlord';
        if (!c.ents.cves.length && c.sink) c.g.tether(c.speaker, c.sink, 2600);
      }
    },
    {
      name: 'telemetry-ingest',
      when: (c) => c.team === 'telemetry' || c.team === 'ingest',
      run(c) {
        if (!c.to) c.to = 'Conductor';
        if (c.team === 'ingest') c.g.sweepWave(hue('orange'));
      }
    },
    {
      name: 'probe-reachable',   // "boundary check exited 0" before any patch → taint the attack path
      when: (c) => c.ents.exit === 0 && !c.it.patched,
      run(c) {
        const { g, path, sink, speaker } = c;
        c.it.compromised = true;
        c.it.stats.findings += 1;
        path.forEach((id, i) => g.setState(id, i === path.length - 1 || i === 0 ? 'compromised' : 'suspect', i !== path.length - 1));
        if (path.length > 1) g.flowPath(path, { color: hue('red'), count: 5, speed: 0.026, kind: 'taint', size: 2.2 });
        if (sink) { c.focus = sink; g.wave(sink, hue('red'), 70, 2.4); }
        g.send(g.node('ctr-probe') ? 'ctr-probe' : 'core', speaker, { label: c.label, color: hue('red'), team: 'red', dur: 1300 });
        if (speaker !== 'Arbiter') g.send(speaker, 'Arbiter', { label: 'EVIDENCE · exit 0', delay: 700 });
        if (c.names.length < 2 && speaker !== 'Warlord' && c.spk.team === 'red') g.send(speaker, 'Warlord', { label: 'REACHABLE ✓', delay: 400 });
        c.to = null; c.label = '';
      }
    },
    {
      name: 'probe-blocked',     // "exited 1" → particles stop at the guard; sink shows blocked/patched
      when: (c) => c.ents.exit === 1,
      run(c) {
        const { g, path, sink } = c;
        if (path.length > 1) g.flowPath(path, { color: hue('red'), count: 3, speed: 0.024, kind: 'taint', size: 1.8 });
        if (sink) { g.setState(sink, c.it.patched ? 'patched' : 'blocked'); c.focus = sink; }
        g.send(g.node('ctr-probe') ? 'ctr-probe' : 'core', 'Arbiter', { label: c.label, color: hue('blue'), team: 'purple', dur: 1300 });
        c.to = null; c.label = '';
      }
    },
    {
      name: 'probe-other-exit',
      when: (c) => c.ents.exit !== null,
      run(c) {
        if (c.sink) c.g.setState(c.sink, 'suspect');
        c.to = c.to || 'Arbiter';
      }
    },
    {
      name: 'sandbox-setup',
      when: (c) => c.stage === 'sandbox' && c.fam === 'orange',
      run(c) {
        const { g, lower } = c;
        const infra = ['net', 'ctr-target', 'ctr-probe'].filter((id) => g.node(id));
        if (/network/.test(lower) && g.node('net')) { c.to = c.to || 'net'; g.setState('net', 'scanned'); }
        else if (/snapshot|fixture is ready|container/.test(lower) && g.node('ctr-target')) { c.to = c.to || 'ctr-target'; g.setState('ctr-target', 'scanned'); }
        else c.to = c.to || infra[0] || 'core';
        if (/creating an internal docker network/.test(lower)) g.sweepWave(hue('orange'));
        c.focus = c.focus || c.to;
      }
    },
    {
      name: 'baseline-checks',
      when: (c) => c.stage === 'baseline' && c.fam !== 'red' && c.fam !== 'blue',
      run(c) {
        c.to = c.to || 'core';
        (c.g.flows || []).forEach((f) => c.g.flowPath(f, { color: '#e2f3ff', speed: 0.02, size: 1.6, kind: 'check' }));
        c.g.wave('core', hue('purple'), 60);
      }
    },
    {
      name: 'red-probe',         // during the probe phase red tethers to the sink
      when: (c) => c.fam === 'red' && c.stage === 'probe',
      run(c) {
        const { g, path, sink, lower } = c;
        const tgt = sink || path[path.length - 1] || 'core';
        if (!c.to) { c.to = tgt; c.label = /proving/.test(lower) ? `PROBE ▸ ${label(g, tgt, 'sink')}`.slice(0, 26) : c.label; }
        g.tether(c.speaker, tgt, 3200);
        c.focus = c.focus || tgt;
        if (path.length > 1 && /mutation|fuzz|variant/.test(lower)) g.flowPath(path, { color: c.spk.color, count: 4, speed: 0.03, kind: 'probe', size: 1.6 });
      }
    },
    {
      name: 'red-recon',         // recon walks outward along the attack path, one node per line
      when: (c) => c.fam === 'red',
      run(c) {
        const { g, path, sink, lower, fileId } = c;
        const step = (c.it.memberTurn.red = (c.it.memberTurn.red || 0) + 1);
        const walk = path.length ? path[Math.min(path.length - 1, step)] : fileId;
        const tgt = c.focus || walk || fileId || 'core';
        if (g.node(tgt) && g.node(tgt).state === 'idle') g.setState(tgt, 'scanned', true);
        if (!c.to) c.to = tgt;
        g.tether(c.speaker, tgt, 3000);
        if (/taint|flows|reaches|unescaped|follow/.test(lower) && path.length > 1) {
          g.flowPath(path, { color: c.spk.color, count: 2, speed: 0.022, kind: 'probe', size: 1.5 });
          path.slice(1, -1).forEach((id) => g.setState(id, 'suspect', true));
          if (sink) g.setState(sink, 'suspect');
        }
        if (/^analyzing/.test(lower) && !c.names.length) c.label = `RECON ▸ ${label(g, tgt, 'target')}`.slice(0, 26);
        c.focus = c.focus || tgt;
      }
    },
    {
      name: 'blue-patch',        // a patch line puts a shield on the guarded edge
      when: (c) => c.fam === 'blue',
      run(c) {
        const { g, sink, fileId, lower, text } = c;
        const tgt = sink || fileId || 'core';
        if (/bounded sanitation|applied|patch(ed)? (applied|ready)/.test(lower)) {
          c.it.patched = true;
          c.it.stats.patches += 1;
          const gl = c.it.topo && c.it.topo.guardLink;
          if (gl) g.guard(gl[0], gl[1], true);
          if (sink) g.setState(sink, 'patched');
          if (fileId) g.setState(fileId, 'patched', true);
          g.send(c.speaker, 'Arbiter', { label: 'CANDIDATE.PATCH', delay: 600 });
          c.label = /[+−-]\d/.test(text) ? (text.match(/\(?\+\d+\s*[−-]\d+\)?/) || ['PATCH'])[0].replace(/[()]/g, '') : 'PATCH APPLIED';
        } else if (/requesting a sanitization patch/.test(lower) && !c.names.length) {
          c.label = `PATCH ▸ ${label(g, tgt, 'sink')}`.slice(0, 26);
        }
        if (!c.to) c.to = c.names.length ? null : tgt;
        g.tether(c.speaker, tgt, 3000);
        c.focus = c.focus || tgt;
      }
    },
    {
      name: 'purple-verify',
      when: (c) => c.fam === 'purple' || c.stage === 'regression',
      run(c) {
        const { g, path, sink, lower } = c;
        if (/fresh target|re-?probe|original probe/.test(lower)) {
          c.to = c.to || 'core';
          if (path.length > 1) g.flowPath(path, { color: hue('purple'), count: 3, speed: 0.024, kind: 'verify', size: 1.8 });
          if (g.node('ctr-target')) g.setState('ctr-target', 'verified', true);
        } else if (/regression|normal-input|passed/.test(lower)) {
          c.to = c.to || 'core';
          (g.flows || []).forEach((f) => g.flowPath(f, { color: '#e2f3ff', speed: 0.022, size: 1.5, kind: 'check' }));
        } else if (/receipt|sha/.test(lower)) {
          c.to = c.to || 'Arbiter';
        } else if (/differential|mutation/.test(lower)) {
          c.to = c.to || sink || 'core';
          if (path.length > 1) g.flowPath(path, { color: hue('purple'), count: 2, speed: 0.028, kind: 'verify', size: 1.5 });
        } else c.to = c.to || 'core';
        c.focus = c.focus || (path.length ? sink : 'core');
      }
    },
    {
      name: 'cleanup',
      when: (c) => c.stage === 'cleanup' || /cleanup|removed|removing/.test(c.lower),
      run(c) {
        ['ctr-probe', 'ctr-target', 'net'].forEach((id, i) => { if (c.g.node(id)) c.g.send('Conductor', id, { label: i ? '' : 'TEARDOWN', delay: i * 220, dur: 1000 }); });
        if (/removed/.test(c.lower)) c.g.sweepWave(hue('orange'));
        c.to = null; c.label = ''; c.focus = null;
      }
    }
  ];

  SMS.choreography = BEATS;
})();
