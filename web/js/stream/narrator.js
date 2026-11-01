// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · stream/narrator.js — tells the run as a story, twice: once in plain words for
// anyone watching, once in precise terms for security people. Lens-aware (core/lenses.js).
//
//   const ctx = SMS.narrator.context(topo, graph)        names used in sentences
//   SMS.narrator.intro(lens, ctx)          → { simple, expert }   before anything happens
//   SMS.narrator.stage(lens, stage, ctx)   → { simple, expert }   on every phase change
//   SMS.narrator.event(lens, ev, ctx, it)  → { simple, expert } | null   per interpreter event
//   SMS.narrator.verdict(lens, result, ctx)→ { simple, expert }   final story
//
// Change wording here only. Beat names come from stream/choreography.js (ev.beat).
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const Ls = () => SMS.lenses;

  const fill = (s, ctx) => String(s).replace(/\{(\w+)\}/g, (_, k) => (ctx[k] !== undefined && ctx[k] !== null ? ctx[k] : ''));
  const pick = (table, lens) => (typeof table === 'string' ? table : table[lens] || table.any);

  function context(topo, graph) {
    const node = (id) => (graph && graph.node(id)) || (topo && (topo.nodes || []).find((n) => n.id === id)) || null;
    const lbl = (id, d) => ((node(id) || {}).label || d);
    const lens = Ls().of(topo);
    const w = Ls().get(lens).words;
    const path = (topo && topo.attackPath) || [];
    return Object.assign({}, w, {
      lens,
      name: (topo && topo.root && topo.root.label) || 'the target',
      entryName: lbl(topo && topo.entryId, path.length ? lbl(path[0], 'the input') : 'the input'),
      sinkName: lbl(topo && topo.sinkId, path.length ? lbl(path[path.length - 1], 'the sink') : 'the sink'),
      hops: path.length ? Math.max(1, path.length - 1) : 0,
      pathNames: path.map((id) => lbl(id, id)).join(' → ')
    });
  }

  /* ---------------- phases ---------------- */
  const STAGE = {
    sandbox: {
      simple: {
        file: 'First we make {copy} and put it in a sealed test room. The real file is never touched.',
        repo: 'First we build {copy} inside a sealed test room. The real project is never touched.',
        binary: 'First we put {copy}. It cannot reach anything outside.',
        system: 'First we make {copy} on a sealed test lot. Nobody touches the real house.'
      },
      expert: {
        file: 'Immutable snapshot → target container on an internal network (no egress); probe container is ephemeral.',
        repo: 'Checkout at the pinned commit into a read-only image; start / test commands run from argv inside the sandbox.',
        binary: 'Binary mounted read-only in a no-egress container; argv / stdin harness, no host access.',
        system: 'Snapshot restored into an isolated network namespace; services start from the cloned image; egress denied.'
      }
    },
    baseline: {
      simple: { any: 'Before changing anything, we check the copy works normally — like testing a light switch first.' },
      expert: { any: 'Normal-input checks on the unpatched target; behaviour contract recorded as the baseline.' }
    },
    analysis: {
      simple: {
        file: 'Red reads the page looking for a spot where outside words get used without being checked.',
        repo: 'Red walks the streets looking for a building with a weak wall.',
        binary: "Red studies the machine's parts list for a part that trusts whatever you feed it.",
        system: 'Red walks around the house checking every door and window.'
      },
      expert: {
        file: 'Taint trace inside one file: source → function → sink, line by line.',
        repo: 'Cross-file call graph and route table; dependency manifest checked against advisories.',
        binary: 'Symbol and import triage (PLT), format strings in .rodata; argv → call chain.',
        system: 'Port and service enumeration, config audit, auth surface; reachability from the perimeter.'
      }
    },
    probe: {
      simple: {
        file: 'Red tries a trick input on the copy. If the trick works, the problem is real.',
        repo: 'Red tries the weak wall on the copy of the city. If it gives, the problem is real.',
        binary: 'Red feeds the machine a weird input to see if it misbehaves.',
        system: 'Red tries the door handle on the copy. If it opens, the lock is broken.'
      },
      expert: {
        any: 'Deterministic proof-of-concept from a fresh probe container. Exit 0 = boundary reachable, exit 1 = blocked.',
        binary: 'Crafted argv / stdin from a fresh probe container. Exit 0 = boundary reachable, exit 1 = blocked.',
        system: 'Network probe against the exposed service from a fresh probe container. Exit 0 = reachable, exit 1 = blocked.'
      }
    },
    patch: {
      simple: {
        file: 'Blue adds the smallest possible lock so the trick stops working — nothing else changes.',
        repo: 'Blue fixes the weak wall with the smallest change, without rebuilding the neighbourhood.',
        binary: 'Blue fixes the risky part so it treats input as plain text, then rebuilds the machine.',
        system: 'Blue fixes the lock (a settings change) without moving any furniture.'
      },
      expert: {
        file: 'Minimal sanitizer diff scoped to the sink; lint and scope checks before submit.',
        repo: 'Minimal diff (may span files); lint, scope and contract checks before submit.',
        binary: 'Fix at the call site (e.g. printf("%s", arg)) and rebuild; no in-place binary patching.',
        system: 'Config / policy hardening (bind address, auth, firewall rule) applied to the snapshot.'
      }
    },
    regression: {
      simple: { any: 'Purple builds a brand-new copy with the fix, tries the exact same trick again, and checks everything else still works.' },
      expert: { any: 'Fresh target from the patched snapshot; original PoC re-run (expect exit 1), regression and differential checks; receipt hash-chained.' }
    },
    cleanup: {
      simple: { any: 'Tidy up: the test copy is thrown away. The real {thing} was never touched.' },
      expert: { any: 'Containers, snapshots and networks removed. The original target is unchanged.' }
    }
  };

  function intro(lens, ctx) {
    const L = Ls().get(lens);
    return { simple: `${L.metaphor}. ${L.simple}`, expert: `${L.label} · ${L.expert}` };
  }

  function stage(lens, st, ctx) {
    const s = STAGE[st];
    if (!s) return null;
    return { simple: fill(pick(s.simple, lens), ctx), expert: fill(pick(s.expert, lens), ctx) };
  }

  /* ---------------- per event (keyed by choreography beat) ---------------- */
  const BEAT = {
    'probe-reachable': () => ({ simple: 'The trick worked on the copy: {entry} really does lead to {sink}. That is a real problem.', expert: 'PoC exit 0 · {entryName} → {sinkName} reachable on the unpatched snapshot ({hops} hops).' }),
    'probe-blocked': (ev, it) => (it && it.patched
      ? { simple: 'Same trick, on a new copy that has the fix — it bounced off. The lock holds.', expert: 'Re-probe exit 1 · blocked at {sinkName} on a fresh patched target.' }
      : { simple: "The trick didn't get through this time.", expert: 'Probe exit 1 · boundary not reachable.' }),
    'probe-other-exit': () => ({ simple: "The test didn't give a clear answer, so we don't count it either way.", expert: 'Probe exit ≠ 0/1 · inconclusive; not counted as evidence.' }),
    'red-recon': (ev) => (/taint|flows|reaches|unescaped|follow/i.test(ev.text)
      ? { simple: 'Red followed the outside input step by step: {pathNames}.', expert: 'Taint path · {pathNames}.' }
      : null),
    'red-probe': (ev) => (/mutation|fuzz|variant/i.test(ev.text) ? { simple: 'Red tries lots of slightly different tricks, like jiggling a key.', expert: 'Mutation variants: quoting, encodings, length edges.' } : null),
    'blue-patch': (ev) => (/bounded sanitation|applied|patch(ed)? (applied|ready)/i.test(ev.text)
      ? { simple: 'Blue put a lock right in front of {sink}.', expert: 'Candidate patch applied at {sinkName}; guard placed on the last hop.' }
      : /vault|recall/i.test(ev.text) ? { simple: 'Blue remembers how a problem like this was fixed before.', expert: 'Fix vault recall for this pattern.' } : null),
    'purple-verify': (ev) => (/receipt|sha/i.test(ev.text)
      ? { simple: 'Purple writes a tamper-proof receipt — like a sealed envelope with a signature.', expert: 'Verdict receipt hash-chained (patch sha256 + pre/post exits).' }
      : /regression|normal-input|passed/i.test(ev.text) ? { simple: 'Normal things still work after the fix.', expert: 'Regression suite passed on the patched target.' }
        : /differential/i.test(ev.text) ? { simple: 'Good inputs act the same as before; bad inputs are now turned away.', expert: 'Differential: normal inputs identical, attack inputs rejected.' } : null),
    'intel-reports': () => ({ simple: 'Yellow checks the library of known problems to see if this has happened before.', expert: 'Threat-intel grounding (OSV / GHSA / CVE / EPSS). Docker evidence still decides.' }),
    'green-grows': () => ({ simple: 'Green is building a practice target with a planted flaw — like a fire drill.', expert: 'Greenhouse growing a disposable vulnerable fixture.' }),
    'telemetry-ingest': (ev) => (ev.raw === 'ingest' ? { simple: 'Orange fetches the exact version of the code we were asked to check.', expert: 'Ingest: pinned commit cloned into staging.' } : { simple: 'Orange keeps score of time and effort.', expert: 'Telemetry: tokens, cost, compression.' }),
    'sandbox-setup': () => null,
    'baseline-checks': () => null,
    cleanup: (ev) => (/removed/i.test(ev.text) ? { simple: 'All tidied up. The test copy is gone; the real {thing} was never touched.', expert: 'Session containers, snapshots and network removed.' } : null)
  };

  function event(lens, ev, ctx, it) {
    if (!ev) return null;
    const fn = BEAT[ev.beat];
    const out = fn ? fn(ev, it) : null;
    if (!out) return null;
    return { simple: fill(out.simple, ctx), expert: fill(out.expert, ctx) };
  }

  /* ---------------- verdict ---------------- */
  function verdict(lens, p = {}, ctx) {
    const st = String(p.status || '');
    let simple;
    let expert;
    if (st === 'verified' || (st === 'completed' && p.post_probe_exit === 1)) {
      simple = 'Red found a way in through {entry}. Blue added a lock. We tried the same trick on a brand-new copy and it was blocked — and everything else still works. The real {thing} was never touched.';
      expert = 'Pre-patch PoC exit 0, post-patch exit 1 on a fresh target, regression {reg}. Receipt chained.';
    } else if (st === 'failed' || st === 'not_confirmed') {
      simple = 'The trick still works after the fix attempt, so we did NOT call it safe. Nothing was changed on the real {thing}.';
      expert = 'Boundary still reachable after the candidate patch (post exit {post}). No verdict issued.';
    } else if (/no_finding/.test(st)) {
      simple = "We looked carefully and couldn't find a way in this time.";
      expert = 'No reachable boundary found this cycle.';
    } else if (st === 'rejected' || st === 'rolled_back') {
      simple = 'The fix broke something normal, so we threw it away. Safety first.';
      expert = 'Candidate patch rejected / rolled back (regression or contract failure).';
    } else if (st === 'stopped') {
      simple = 'We stopped early. Nothing was changed.';
      expert = 'Run cancelled by the operator; server-side cleanup continues.';
    } else {
      simple = "The run ended before we could decide. Nothing was changed.";
      expert = `Status ${st || 'unknown'}; no verified verdict.`;
    }
    const x = Object.assign({}, ctx, { reg: p.regression_passed === false ? 'failed' : p.regression_passed ? 'passed' : 'not reported', post: p.post_probe_exit ?? p.post_exit_code ?? '?' });
    return { simple: fill(simple, x), expert: fill(expert, x) };
  }

  SMS.narrator = { context, intro, stage, event, verdict, STAGE, BEAT };
})();
