// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · stream/rules.js — text rules that read the orchestrator's wording.
// If the backend changes how it phrases a line, THIS is the file to update.
//   stageOf()     which of the 7 phases a line advances to (mirrors v2 advanceStage())
//   verifierFor() which purple agent speaks for an unnamed verification line
//   eventTime()   server timestamp (ts | time | timestamp: s, ms or ISO) or arrival time
//   bubbleLabel() the short uppercase label drawn on a message bubble
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const P = () => SMS.palette;

  // Result statuses that count as "the run finished cleanly".
  const OK_STATUSES = ['verified', 'not_confirmed', 'no_findings', 'completed', 'no_finding'];

  function stageOf(team, text, current) {
    const t = text.toLowerCase();
    if (team === 'green') return 'sandbox';
    if (t.includes('original-project baseline checks')) return 'baseline';
    if (team === 'red' && t.includes('reviewing the cumulative verified snapshot')) return 'analysis';
    if (team === 'red' && t.includes('proving the finding')) return 'probe';
    if (team === 'blue' && t.includes('bounded sanitation-only replacements')) return 'patch';
    if (t.includes('verifying a fresh target with the original probe')) return 'regression';
    if (t.includes('removing project session containers')) return 'cleanup';
    if (t.includes('creating an internal docker network')) return 'sandbox';
    if (t.includes('normal-input checks passed') && current < 2) return 'baseline';
    if (team === 'red' && t.startsWith('analyzing')) return 'analysis';
    if (team === 'research') return current < 2 ? 'analysis' : null;
    if (team === 'red' && t.includes('boundary check exited')) return 'probe';
    if (team === 'blue' && t.startsWith('requesting a sanitization patch')) return 'patch';
    if (t.includes('starting a fresh target from the patched snapshot')) return 'regression';
    if (t.includes('session containers, snapshots, and network removed')) return 'cleanup';
    // Real backend lines carry a "[phase …]" / "[sweep …]" tag prefix; match the body too.
    const b = t.replace(/^\[[^\]]*\]\s*/, '');
    if (team === 'red' && b.startsWith('analyzing')) return 'analysis'; // workflow.py:378
    if (b.startsWith('static reversing profile collected')) return 'analysis'; // binary_sweep.py:150
    if (b.includes('binary harness is ready; baseline checks passed') && current < 2) return 'baseline'; // binary_sweep.py:163
    if (team === 'blue' && b.startsWith('requesting a sanitization patch')) return 'patch'; // workflow.py:451, sweep.py:453
    if (b.includes('post-patch boundary check exited')) return 'regression'; // workflow.py:497, sweep.py:524
    return null;
  }

  function verifierFor(text) {
    const t = text.toLowerCase();
    if (/receipt|sha256|chain/.test(t)) return 'Notary';
    if (/differential|mutation/.test(t)) return 'Mirror';
    if (/regression|fresh target|baseline|normal-input|verdict|re-probe|evidence/.test(t)) return 'Arbiter';
    return null;
  }

  function eventTime(meta) {
    const raw = meta && (meta.ts ?? meta.time ?? meta.timestamp);
    if (raw === undefined || raw === null || raw === '') return Date.now();
    if (typeof raw === 'number') return raw < 1e12 ? raw * 1000 : raw;
    const p = Date.parse(raw);
    return Number.isFinite(p) ? p : Date.now();
  }

  const STOP = new Set(['the', 'a', 'an', 'of', 'to', 'for', 'and', 'is', 'on', 'in', 'with', 'this', 'from', 'it', 'its', 'be', 'by', 'at', 'now']);
  function bubbleLabel(text, ents) {
    if (ents.exit !== null) return `EXIT ${ents.exit} · ${ents.exit === 0 ? 'REACHABLE' : ents.exit === 1 ? 'BLOCKED' : 'INCONCLUSIVE'}`;
    if (ents.cves.length) return ents.cves[0];
    const t = text.toLowerCase();
    if (/passed/.test(t) && /regression|normal-input|baseline/.test(t)) return 'CHECKS ✓ PASSED';
    if (/receipt/.test(t)) return 'RECEIPT ⛓ SIGNED';
    if (/rate limit|429/.test(t)) return 'THROTTLED 429';
    if (/docker/.test(t) && /unreachable|offline/.test(t)) return 'DOCKER OFFLINE';
    const names = new Set(P().AGENTS.map((a) => a.id.toLowerCase()));
    const words = text.replace(/[^\w\s/.>\-()?=]/g, ' ').split(/\s+/)
      .filter((w) => w && !STOP.has(w.toLowerCase()) && !names.has(w.toLowerCase()))
      .slice(0, 3).join(' ');
    return words.toUpperCase().slice(0, 24);
  }

  SMS.rules = { OK_STATUSES, stageOf, verifierFor, eventTime, bubbleLabel };
  SMS.OK_STATUSES = OK_STATUSES;
})();
