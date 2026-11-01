// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · ui/result-view.js — renders a final result payload into the console's Result pane
// (needs the #result … #r-cycles markup from console.html). Also exposes the helpers used by
// downloads and history: summarize(p) → { pre, post, receipt, recs }, redact(evidence).
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const U = (SMS.hud = SMS.hud || {});
  const { h, elapsed } = U;
  const $ = (id) => document.getElementById(id);

  const RESULT_LABELS = { verified: 'Boundary check passed', not_confirmed: 'Boundary not confirmed', no_finding: 'No finding this cycle', inconclusive: 'Probe inconclusive', rolled_back: 'Change rolled back', rejected: 'Candidate patch rejected', failed: 'Boundary still reachable', no_findings: 'No findings', partial: 'Verification partially completed', completed: 'Project verification completed', error: 'Scan could not complete' };

  function summarize(p) {
    const recs = p.cycle_reports || p.cycles || [];
    const ev0 = recs[0] && recs[0].evidence;
    const pre = p.pre_probe_exit ?? p.pre_exit_code ?? (ev0 && ev0.pre_verification && ev0.pre_verification.probe ? ev0.pre_verification.probe.exit_code : undefined);
    const post = p.post_probe_exit ?? p.post_exit_code ?? (ev0 && ev0.patched_verification && ev0.patched_verification.probe ? ev0.patched_verification.probe.exit_code : undefined);
    const receipt = p.receipt || p.verdict_receipt || ((recs.find((c) => c && c.receipt) || {}).receipt);
    return { pre, post, receipt, recs };
  }
  function exitText(c, post) {
    if (c === undefined || c === null) return ['not run', undefined];
    if (c === 0) return ['exit 0 · reachable', post ? false : undefined];
    if (c === 1) return ['exit 1 · blocked', post ? true : undefined];
    return [`exit ${c} · inconclusive`, false];
  }
  function renderResult(p, o = {}) {
    const source = o.source;
    const { pre, post, receipt, recs } = summarize(p);
    const ok = SMS.OK_STATUSES.includes(p.status);
    $('result-empty').hidden = true;
    $('result').hidden = false;
    $('r-kicker').textContent = source === 'fake' || p.replay ? 'Result · fake run (scripted)' : 'Result · live orchestrator';
    $('r-title').textContent = RESULT_LABELS[p.status] || 'Scan finished';
    $('r-msg').textContent = p.message || '';
    document.querySelector('.c-rhead').dataset.tone = p.status === 'verified' || p.status === 'completed' ? 'good' : ok ? 'neutral' : 'bad';
    const facts = $('r-facts');
    facts.replaceChildren();
    const fact = (k, v, good) => { const d = h('div'); const dd = h('dd', null, v); if (good !== undefined) dd.dataset.good = String(good); d.append(h('dt', null, k), dd); facts.append(d); };
    const bp = p.baseline_passed ?? (p.baseline_verification ? p.baseline_verification.fresh_target && p.baseline_verification.regression && p.baseline_verification.regression.exit_code === 0 : undefined);
    fact('Baseline', bp === undefined ? 'not reported' : bp ? 'passed' : 'not passed', bp);
    fact('Pre-patch probe', ...exitText(pre, false));
    fact('Post-patch probe', ...exitText(post, true));
    fact('Regression', p.regression_passed === undefined ? 'not reported' : p.regression_passed ? 'passed' : 'not passed', p.regression_passed);
    const sha = receipt && (receipt.patch_sha256 || receipt.patch_hash || receipt.patch_sha);
    fact('Receipt', sha ? `sha ${String(sha).slice(0, 16)}…` : 'not reported', sha ? true : undefined);
    const chain = receipt ? (typeof receipt.chain_ok === 'boolean' ? receipt.chain_ok : receipt.prev_receipt_sha && receipt.prev_receipt_sha === sha) : undefined;
    fact('Receipt chain', chain === undefined ? 'unknown' : chain ? 'chain verified' : 'chain broken', chain);
    const cleanup = p.cleanup_ok !== undefined ? p.cleanup_ok : !p.cleanup || p.cleanup.succeeded;
    fact('Cleanup', cleanup ? 'resources removed' : 'inspect Docker', cleanup);
    if (o.started) fact('Wall time', elapsed(Date.now() - o.started));
    const comp = p.compression || {};
    if (comp.raw_tokens_estimated) fact('Compression', `${Number(comp.raw_tokens_estimated).toLocaleString()} → ${Number(comp.compressed_tokens_sent).toLocaleString()} tok`, true);
    if (p.vault_recall && p.vault_recall !== 'VAULT_UNAVAILABLE') fact('Vault recall', String(p.vault_recall).slice(0, 60));
    if (Array.isArray(p.pass_results) && p.pass_results.length) fact('Sweep', `${p.pass_results.filter((x) => x.cleared || (x.post_exit_code === 1 && x.regression_passed)).length}/${p.pass_results.length} passes hold`);

    $('dl-receipt').hidden = !receipt;
    const diff = p.diff || p.cumulative_diff || '';
    $('dl-patch').hidden = !diff;
    $('cp-diff').hidden = !diff;
    $('r-diff-wrap').hidden = !diff;
    if (diff) {
      const pre2 = $('r-diff');
      pre2.replaceChildren();
      let add = 0; let del = 0;
      diff.split('\n').forEach((line) => {
        const cls = line.startsWith('+++') || line.startsWith('---') ? 'file' : line.startsWith('+') ? 'add' : line.startsWith('-') ? 'del' : line.startsWith('@@') ? 'hunk' : '';
        if (cls === 'add') add += 1;
        if (cls === 'del') del += 1;
        pre2.append(h('span', cls, `${line}\n`));
      });
      $('r-diffstat').textContent = `+${add} −${del}`;
    }
    const calls = (p.usage && p.usage.calls) || [];
    $('r-usage').hidden = !calls.length;
    if (calls.length) {
      const cost = p.cost_usd ?? p.total_cost_usd;
      const ul = h('ul');
      calls.forEach((c) => {
        const blue = c.role === 'blue' || String(c.role || '').startsWith('project_blue_');
        const li = h('li');
        li.style.setProperty('--c', blue ? '#38bdf8' : '#ff3b5c');
        li.append(h('b', null, blue ? 'Blue' : 'Red'), h('span', null, `${c.model} · ${Number(c.prompt_tokens || 0).toLocaleString()} in · ${Number(c.completion_tokens || 0).toLocaleString()} out · ${Number(c.seconds || 0).toFixed(1)}s`), h('em', null, `$${Number(c.cost_usd || 0).toFixed(4)}`));
        ul.append(li);
      });
      $('r-usage').replaceChildren(h('span', null, 'Estimated cost '), h('strong', null, cost === undefined || cost === null ? 'unknown' : `$${Number(cost).toFixed(4)}`), h('span', null, ` · ${Number(p.total_tokens || 0).toLocaleString()} tokens`), ul);
    }
    const cyc = $('r-cycles');
    cyc.replaceChildren();
    cyc.hidden = !recs.length && !(p.research_records || []).length;
    if ((p.research_records || []).length) {
      const d = h('details');
      d.append(h('summary', null, `Threat intel · ${p.research_records.length} records (untrusted grounding)`), h('pre', null, p.research_records.slice(0, 16).map((r) => `${r.cve_id || '?'} [${r.source || r.scanner || '?'}] ${r.severity || ''} ${r.title || ''}`).join('\n')));
      cyc.append(d);
    }
    recs.forEach((c, i) => {
      const d = h('details');
      if (i === recs.length - 1) d.open = true;
      d.append(h('summary', null, `Cycle ${c.cycle || i + 1}${c.pass_number ? ` · pass ${c.pass_number}` : ''}${c.status ? ` · ${c.status}` : ''}`));
      if (c.report || c.message) d.append(h('p', null, c.report || c.message));
      if (c.evidence) d.append(h('pre', null, JSON.stringify(redact(c.evidence), null, 2).slice(0, 6000)));
      cyc.append(d);
    });
  }
  function redact(v) {
    if (Array.isArray(v)) return v.map(redact);
    if (v && typeof v === 'object') { const o = {}; Object.entries(v).forEach(([k, x]) => { o[k] = k === 'verification_script_python' ? '[exploit details withheld]' : (k === 'output' && typeof x === 'string' && x.length > 500 ? `${x.slice(0, 500)}\n[truncated]` : redact(x)); }); return o; }
    return v;
  }

  SMS.views = Object.assign(SMS.views || {}, { RESULT_LABELS, summarize, exitText, renderResult, redact });
})();
