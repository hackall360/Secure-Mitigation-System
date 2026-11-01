// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · headless test suite (Playwright). No real backend needed: /api/* and /ws/* are mocked.
//
//   cd <v3 folder> && python3 -m http.server 8765 &
//   node tools/tests/smoke.js [http://localhost:8765/] [--shots /tmp/sms-shots]
//
// Exit code is non-zero if any check fails. Add a check: push another `test('name', async (page) => …)`.
'use strict';
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const BASE = (process.argv.find((a) => /^https?:\/\//.test(a)) || 'http://localhost:8765/').replace(/\/?$/, '/');
const SHOTS = process.argv.includes('--shots') ? process.argv[process.argv.indexOf('--shots') + 1] : null;
const FIXTURE_ELF = path.join(__dirname, 'fixtures', 'argv_echo');

const HEALTH = { inference_mode: 'hosted', api_key_configured: true, docker: { state: 'ready' }, profiles: [{ key: 'balanced', label: 'Balanced', description: 'Spark', red_model: 'muse-spark', blue_model: 'muse-spark' }], default_profile: 'balanced', scan_profiles: [] };
const TARGETS = { node_query_sink: { title: 'Node query sink', filename: 'app.js', description: 'q' }, php_command_sink: { title: 'PHP command sink', filename: 'index.php', description: 'c' } };
const STREAM = [['system', 'Creating an internal Docker network.'], ['red', 'Analyzing app.js.'], ['red', 'Boundary check exited 0.'], ['blue', 'Applied bounded sanitation-only replacements to app.js.'], ['system', 'Boundary check exited 1.']];

const tests = [];
const test = (name, fn, o = {}) => tests.push({ name, fn, o });
const assert = (cond, msg) => { if (!cond) throw new Error(msg); };

async function mockBackend(page, log) {
  await page.route('**/api/health', (r) => r.fulfill({ json: HEALTH }));
  await page.route('**/api/targets', (r) => r.fulfill({ json: TARGETS }));
  await page.routeWebSocket(/\/ws\//, (ws) => {
    log.ws = ws.url();
    ws.onMessage((m) => { log.body = String(m); });
    STREAM.forEach(([team, msg], i) => setTimeout(() => ws.send(JSON.stringify({ team, msg, ts: Date.now() / 1000 })), 300 + i * 350));
    setTimeout(() => { ws.send(JSON.stringify({ type: 'result', status: 'verified', message: 'mock', pre_probe_exit: 0, post_probe_exit: 1 })); ws.close(); }, 300 + STREAM.length * 350 + 200);
  });
}

/* ---------- every page loads without errors ---------- */
['index.html', 'demo-setup.html', 'prod-setup.html', 'visualizer.html'].forEach((p) => test(`loads ${p}`, async (page) => {
  await page.goto(BASE + p);
  await page.waitForTimeout(1200);
  assert(await page.evaluate(() => !!(window.SMS && SMS.SpiderGraph && SMS.Interpreter && SMS.options && SMS.hud && SMS.launch)), 'SMS namespace incomplete');
}));

test('visual pages without a launch redirect to setup', async (page) => {
  await page.goto(BASE + 'console.html'); await page.waitForURL(/prod-setup/);
  await page.goto(BASE + 'demo.html'); await page.waitForURL(/demo-setup/);
});

/* ---------- contracts (pure logic, evaluated in the page) ---------- */
test('options.compile matches the v2 wire contract', async (page) => {
  await page.goto(BASE + 'prod-setup.html');
  const r = await page.evaluate(() => {
    const O = SMS.options;
    const v = Object.assign(O.defaults(O.RUN, { page: 'console' }), { path: '/srv/a', image: 'img', command: '["npm","start"]', test_command: '["npm","test"]', contract: 'c', allow_remote_inference: true, scan_profile: 'ultra_heavy', cycles: 12, red_agents: 8, sweep_passes: 2, profile: 'balanced', research: true });
    return { project: O.compile('project', v, {}), fixture: O.compile('fixture', v, { fixture: 'node_query_sink' }) };
  });
  assert(r.project.path === '/ws/project?sweep_passes=2&profile=balanced&research=on', `project path ${r.project.path}`);
  assert(JSON.stringify(r.project.body.command) === '["npm","start"]' && r.project.body.red_agents === 8 && r.project.body.allow_remote_inference === true, 'project body');
  assert(r.fixture.body === undefined && r.fixture.path.startsWith('/ws/combat/node_query_sink?'), 'fixture request');
});

test('interpreter: stages, taint, patch, verdict', async (page) => {
  await page.goto(BASE + 'visualizer.html');
  const r = await page.evaluate((stream) => {
    const g = new SMS.SpiderGraph(document.createElement('canvas'), { mode: 'console' });
    const it = new SMS.Interpreter(g);
    const stages = [];
    it.on('stage', (s) => stages.push(s));
    it.load(SMS.topology.profile('node_query_sink', {}));
    const evs = stream.map(([t, m]) => it.line(t, m));
    it.result({ status: 'verified' });
    g.destroy();
    return { stages, findings: it.stats.findings, patches: it.stats.patches, verdict: g.verdict, sink: g.node('sink').state, beats: evs.map((e) => e.beat) };
  }, STREAM);
  assert(r.stages.join() === 'sandbox,analysis,probe,patch', `stages ${r.stages}`);
  assert(r.findings === 1 && r.patches === 1, 'stats');
  assert(r.verdict === 'verified' && r.sink === 'verified', `verdict ${r.verdict} sink ${r.sink}`);
  assert(r.beats.includes('probe-reachable') && r.beats.includes('blue-patch') && r.beats.includes('probe-blocked'), `beats ${r.beats}`);
});

test('ELF parser finds symbols and dangerous imports', async (page) => {
  await page.goto(BASE + 'prod-setup.html');
  const b64 = fs.readFileSync(FIXTURE_ELF).toString('base64');
  const f = await page.evaluate((s) => { const bin = atob(s); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i += 1) u[i] = bin.charCodeAt(i); return SMS.topology.fromBinary(u.buffer, 'argv_echo').findings; }, b64);
  assert(f.format === 'ELF64' && f.dangerous.includes('strcpy') && f.dangerous.includes('printf'), JSON.stringify(f));
});

/* ---------- lenses + explain layer ---------- */
test('lenses: every source is drawn with the right lens', async (page) => {
  await page.goto(BASE + 'prod-setup.html');
  const r = await page.evaluate(() => {
    const T = SMS.topology;
    const of = SMS.lenses.of;
    return {
      fixture: of(T.profile('node_query_sink', {})), conf: of(T.profile('mysql_insecure_conf', {})), elf: of(T.profile('binary_argv_echo', {})),
      repo: of(T.profile('repo_notes_app', {})), sys: of(T.profile('system_shop_stack', {})),
      project: of(T.project({ path: '/srv/x' })), snippet: of(T.fromSource('eval(req.query.x)', 'javascript', 'a.js')),
      system: of(T.fromSystem('web nginx 80 public', 'snap')), map: SMS.options.SOURCE_LENS,
      req: SMS.options.compile('system', { snapshot_ref: 'snap@1', snapshot_kind: 'vm', services: 'a b 1', contract: 'c', scan_profile: 'light', cycles: 3, red_agents: 5, blue_agents: 5, context_budget: 32768, sweep_passes: 1, research: false }, {})
    };
  });
  assert(r.fixture === 'file' && r.conf === 'file' && r.elf === 'binary' && r.repo === 'repo' && r.sys === 'system', `profiles ${JSON.stringify(r)}`);
  assert(r.project === 'repo' && r.snippet === 'file' && r.system === 'system', 'builders');
  assert(r.map.project === 'repo' && r.map.binary === 'binary' && r.map.system === 'system', 'SOURCE_LENS');
  assert(r.req.path === '/ws/system' && r.req.body.services === 'a b 1' && r.req.body.snapshot_kind === 'vm' && r.req.body.scan_profile === 'light', `system request ${JSON.stringify(r.req)}`);
});

test('system parser: doors, attack path, findings', async (page) => {
  await page.goto(BASE + 'prod-setup.html');
  const r = await page.evaluate(() => {
    const t = SMS.topology.fromSystem(SMS.topology.SHOP_STACK, 'reg/shop-stack@sha256:abc');
    const n = (id) => t.nodes.find((x) => x.id === id);
    const chain = SMS.topology.fromSystem('lb haproxy 443 public -> api\napi python 8000 -> pg\npg postgres:16 5432', 's');
    return { label: t.root.label, f: t.findings, entry: n(t.entryId), sink: n(t.sinkId), doors: t.nodes.filter((x) => x.kind === 'port' && x.meta && x.meta.public).length, chain: chain.attackPath.map((id) => chain.nodes.find((x) => x.id === id).label) };
  });
  assert(r.label === 'shop-stack', `label ${r.label}`);
  assert(r.f.services === 5 && r.f.public === 2 && r.f.exposedStores.join() === 'cache', `findings ${JSON.stringify(r.f)}`);
  assert(r.entry.kind === 'port' && r.entry.meta.public && r.sink.kind === 'data', 'path should run from a public door to the data');
  assert(r.doors === 2, `doors ${r.doors}`);
  assert(r.chain[0] === ':443' && r.chain[r.chain.length - 1] === 'customer tables', `chain ${r.chain}`);
});

test('narrator: plain words and expert detail for every lens and phase', async (page) => {
  await page.goto(BASE + 'visualizer.html');
  const bad = await page.evaluate(() => {
    const out = [];
    SMS.lenses.ORDER.forEach((lens) => {
      const ctx = SMS.narrator.context(SMS.topology.profile({ file: 'node_query_sink', repo: 'repo_notes_app', binary: 'binary_argv_echo', system: 'system_shop_stack' }[lens], {}), null);
      SMS.palette.STAGES.forEach((st) => { const x = SMS.narrator.stage(lens, st, ctx); if (!x || !x.simple || !x.expert || /\{|\}|undefined/.test(x.simple + x.expert)) out.push(`${lens}/${st}`); });
      const v = SMS.narrator.verdict(lens, { status: 'verified', regression_passed: true }, ctx);
      if (!/never touched/.test(v.simple) || /\{/.test(v.simple)) out.push(`${lens}/verdict`);
      const e = SMS.narrator.event(lens, { beat: 'probe-reachable', text: '' }, ctx);
      if (!e || /\{/.test(e.simple + e.expert)) out.push(`${lens}/event`);
    });
    return out;
  });
  assert(!bad.length, `missing or unfilled sentences: ${bad.join(', ')}`);
});

test('explain switch: simple / both / expert change what is visible', async (page) => {
  await page.goto(BASE + 'visualizer.html?lens=system'); await page.waitForTimeout(1200);
  assert(await page.evaluate(() => SMS.SpiderGraph && document.querySelector('#d-lens').textContent.includes('System snapshot')), 'lens badge');
  await page.click('#ex-toggle button[data-level="simple"]');
  assert(await page.evaluate(() => document.body.dataset.explain) === 'simple', 'simple level');
  assert(!(await page.isVisible('.ex-expert')) && await page.isVisible('.ex-simple'), 'simple hides expert line');
  await page.click('#ex-toggle button[data-level="expert"]');
  assert(!(await page.isVisible('.ex-simple')) && await page.isVisible('.ex-expert'), 'expert hides plain words');
  await page.keyboard.press('e');
  assert(await page.evaluate(() => document.body.dataset.explain) === 'simple', 'E cycles');
});

test('visualizer: each lens loads its own map', async (page) => {
  for (const lens of ['file', 'repo', 'binary', 'system']) {
    await page.goto(`${BASE}visualizer.html?lens=${lens}`); await page.waitForTimeout(700);
    const got = await page.evaluate(() => document.querySelector('#v-lens [aria-checked="true"]').textContent);
    assert(got === (await page.evaluate((l) => SMS.lenses.get(l).label, lens)), `lens ${lens} → ${got}`);
  }
});

test('scramble text always lands on the real string (even with rAF stalled, rapid re-calls)', async (page) => {
  await page.goto(BASE + 'visualizer.html'); await page.waitForTimeout(600);
  const r = await page.evaluate(async () => {
    window.requestAnimationFrame = () => 0; // simulate a background tab / screen-capture stall
    const el = document.createElement('h2'); document.body.append(el);
    SMS.hud.scramble(el, 'first line that should be replaced', 650);
    await new Promise((ok) => setTimeout(ok, 120));
    const want = 'Tidy up: the test copy is thrown away. {braces} \\ / stay';
    SMS.hud.scramble(el, want, 650);
    await new Promise((ok) => setTimeout(ok, 1000));
    return [el.textContent, want, el.getAttribute('aria-label')];
  });
  assert(r[0] === r[1], `scramble stuck: "${r[0]}"`);
  assert(r[2] === r[1], 'aria-label should carry the final text');
});

/* ---------- flows ---------- */
test('start → demo setup → demo (fake run) → verdict', async (page) => {
  await page.goto(BASE); await page.waitForTimeout(400);
  await page.keyboard.press('1'); await page.waitForURL(/demo-setup/); await page.waitForTimeout(900);
  await page.click('[data-speed]').catch(() => {});
  await page.click('#launch'); await page.waitForURL(/demo\.html/);
  await page.click('[data-speed="4"]');
  await page.waitForSelector('#verdict:not([hidden])', { timeout: 40000 });
}, { timeout: 60000 });

test('demo live run streams and shows a verdict', async (page, log) => {
  await page.goto(BASE + 'demo-setup.html'); await page.waitForTimeout(1200);
  await page.click('#launch'); await page.waitForURL(/demo\.html/);
  await page.waitForSelector('#verdict:not([hidden])', { timeout: 15000 });
  assert(/\/ws\/combat\/node_query_sink/.test(log.ws), `ws ${log.ws}`);
}, { live: true });

test('prod setup → console (fake run) → result', async (page) => {
  await page.goto(BASE); await page.waitForTimeout(400);
  await page.click('.l-card[data-key="2"]'); await page.waitForURL(/prod-setup/); await page.waitForTimeout(900);
  await page.click('#fake'); await page.waitForURL(/console\.html/);
  await page.waitForSelector('#result:not([hidden])', { timeout: 60000 });
}, { timeout: 80000 });

test('prod live binary: bytes reach the socket intact', async (page, log) => {
  await page.goto(BASE + 'prod-setup.html'); await page.waitForTimeout(1200);
  await page.click('[data-mode="binary"]');
  await page.setInputFiles('[data-key="binary"] input[type=file]', FIXTURE_ELF);
  await page.fill('[data-key="contract"] textarea', 'echo must not interpret format strings');
  await page.waitForTimeout(800);
  await page.click('#launch'); await page.waitForURL(/console\.html/);
  await page.waitForSelector('#result:not([hidden])', { timeout: 15000 });
  assert(/\/ws\/binary/.test(log.ws), `ws ${log.ws}`);
  assert(JSON.parse(log.body).blob_b64.startsWith('f0VMRg'), 'ELF bytes not in body');
}, { live: true });

test('demo showcase (system snapshot) fake run → verdict in plain words', async (page) => {
  await page.goto(BASE + 'demo-setup.html'); await page.waitForTimeout(900);
  await page.click('.s-tcard[data-key="system_shop_stack"]');
  await page.click('#launch'); await page.waitForURL(/demo\.html/);
  await page.click('[data-speed="4"]');
  await page.waitForSelector('#verdict:not([hidden])', { timeout: 40000 });
  assert(/door/.test(await page.textContent('#v-simple')), 'plain-words verdict should mention the door');
  assert(await page.evaluate(() => document.body.dataset.explain) === 'both', 'demo default explain level');
}, { timeout: 60000 });

test('prod live system snapshot: request goes to /ws/system', async (page, log) => {
  await page.goto(BASE + 'prod-setup.html'); await page.waitForTimeout(1200);
  await page.click('[data-mode="system"]');
  await page.fill('[data-key="snapshot_ref"] input', 'registry.local/shop@sha256:1');
  await page.fill('[data-key="services"] textarea', 'web nginx 443 public -> db\ndb postgres 5432');
  await page.fill('[data-key="contract"] textarea', 'checkout keeps working');
  await page.waitForTimeout(500);
  await page.click('#launch'); await page.waitForURL(/console\.html/);
  await page.waitForSelector('#result:not([hidden])', { timeout: 15000 });
  assert(/\/ws\/system/.test(log.ws), `ws ${log.ws}`);
  const body = JSON.parse(log.body);
  assert(body.snapshot_ref === 'registry.local/shop@sha256:1' && /postgres/.test(body.services), 'system body');
  assert(await page.evaluate(() => document.querySelector('#c-lens').textContent.includes('System snapshot')), 'console lens badge');
}, { live: true });

test('visualizer injections', async (page) => {
  await page.goto(BASE + 'visualizer.html'); await page.waitForTimeout(1500);
  for (const label of ['Probe · exit 0', 'Patch applied', 'Burst ×20', 'Verdict · pass']) { await page.click(`text=${label}`); await page.waitForTimeout(500); }
  assert(Number(await page.textContent('#st-msgs')) >= 20, 'burst did not register');
});

(async () => {
  const browser = await chromium.launch();
  let failed = 0;
  for (const t of tests) {
    const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
    const errs = [];
    const log = {};
    page.on('pageerror', (e) => errs.push(`pageerror: ${e.message}`));
    page.on('console', (m) => { if (m.type() === 'error' && !(!t.o.live && /404|Failed to load resource/.test(m.text()))) errs.push(m.text()); });
    if (t.o.live) await mockBackend(page, log);
    page.setDefaultTimeout(t.o.timeout || 30000);
    try {
      await t.fn(page, log);
      if (errs.length) throw new Error(errs.join(' | '));
      console.log(`  ✓ ${t.name}`);
    } catch (e) {
      failed += 1;
      console.log(`  ✗ ${t.name}\n      ${e.message.split('\n')[0]}`);
    }
    if (SHOTS) { fs.mkdirSync(SHOTS, { recursive: true }); await page.screenshot({ path: path.join(SHOTS, `${t.name.replace(/\W+/g, '-')}.png`) }).catch(() => {}); }
    await page.close();
  }
  await browser.close();
  console.log(failed ? `\n${failed} of ${tests.length} failed` : `\nall ${tests.length} passed`);
  process.exit(failed ? 1 : 0);
})();
