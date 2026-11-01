// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · Replay — scripted sample sessions for offline demos.
// The lines use the same vocabulary the orchestrator emits, so the replay drives
// the exact same interpreter path as a live socket. Every run is labelled FAKE RUN in the UI.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});

  const VOCAB = {
    node_query_sink: { file: 'app.js', entry: 'GET /search?q=', fn: 'searchHandler()', sink: 'db.query()', cwe: 'CWE-89 SQL injection', kind: 'string-built SQL', fix: 'parameterized query', input: 'q' },
    php_command_sink: { file: 'index.php', entry: 'GET /?host=', fn: 'ping()', sink: 'shell_exec()', cwe: 'CWE-78 OS command injection', kind: 'argv concatenation', fix: 'escapeshellarg() allow-list', input: 'host' },
    mysql_insecure_conf: { file: 'my.cnf', entry: 'client 3306/tcp', fn: '[mysqld]', sink: 'insecure directive', cwe: 'CWE-1188 insecure default', kind: 'unsafe default directive', fix: 'hardened directive', input: 'remote client' },
    binary_argv_echo: { file: 'argv_echo', entry: 'argv[1]', fn: 'echo_arg()', sink: 'printf()', cwe: 'CWE-134 format string', kind: 'argv used as format', fix: 'printf("%s", arg)', input: 'argv[1]' },
    repo_notes_app: { file: 'src/routes/export.js', entry: 'GET /notes/export?sort=', fn: 'exportNotes()', sink: 'knex.raw()', cwe: 'CWE-89 SQL injection (ORDER BY)', kind: 'string-built ORDER BY', fix: 'allow-listed sort column', input: 'sort',
      recon: [
        ['red', 'Cartographer: walked src/routes/, src/db/ and src/views/ · 11 files, 3 dependencies in package.json.'],
        ['red', 'Bloodhound: sort leaves src/routes/export.js, crosses into src/db/queries.js buildOrderBy() and lands in knex.raw().']
      ] },
    system_shop_stack: { file: 'shop-stack snapshot', entry: '6379/tcp', fn: 'redis', sink: 'session keys', cwe: 'CWE-306 missing authentication', kind: 'unauthenticated service on a public port', fix: 'bind to the internal network + requirepass', input: 'a raw TCP client',
      recon: [
        ['red', 'Cartographer: port sweep of the snapshot · 443/tcp public, 6379/tcp public, 3000/tcp and 5432/tcp internal only.'],
        ['red', 'Lockpick: 6379/tcp answers PING without AUTH — the session keys behind it are readable from outside the wall.']
      ] },
    custom: { file: 'snippet', entry: 'input', fn: 'handler()', sink: 'sink', cwe: 'boundary flaw', kind: 'unsanitized input', fix: 'sanitizer', input: 'input' }
  };

  function vocabFor(key, topo) {
    const v = Object.assign({}, VOCAB[key] || VOCAB.custom);
    if (topo && !VOCAB[key]) {
      const node = (id) => (topo.nodes || []).find((n) => n.id === id);
      const path = (topo.attackPath || []).map(node).filter(Boolean);
      if (path.length) {
        v.entry = path[0].label;
        v.sink = path[path.length - 1].label;
        const fn = path.find((n) => n.kind === 'function');
        if (fn) v.fn = fn.label;
      }
      v.file = topo.root.label;
    }
    return v;
  }

  // [delayMs, team, msg]
  function script(key, topo, o = {}) {
    const v = vocabFor(key, topo);
    const L = [];
    const add = (d, team, msg) => L.push([d, team, msg]);
    if (o.grow) {
      add(300, 'green', `Greenhouse is growing a fresh demo around ${v.file}. Stand by for seedlings.`);
      add(1500, 'green', 'Seedling: planted the HTTP listener and router skeleton.');
      add(1400, 'green', `Seedling: planted route ${v.entry} and its handler.`);
      add(1400, 'green', `Greenhouse grew a deliberately wobbly ${v.kind} at ${v.sink} (${v.cwe}).`);
      add(1400, 'green', 'Seedling: planted data fixtures and the regression suite.');
      add(1200, 'green', 'Greenhouse grew the sandbox wiring. Handing over to red and blue.');
    }
    add(o.grow ? 1200 : 400, 'system', 'Creating an internal Docker network for this session (sms-net, no egress).');
    add(1300, 'system', `Original fixture is ready · immutable target snapshot of ${v.file} taken.`);
    add(1200, 'system', 'Conductor: target container started from the read-only snapshot.');
    add(1300, 'system', 'Original fixture normal-input checks passed (3/3). Baseline recorded.');
    add(1300, 'red', `Analyzing ${v.file} for an input boundary with Muse Spark.`);
    add(1200, 'red', `Warlord: Cartographer, map the surface of ${v.file}. Bloodhound, follow ${v.input}.`);
    add(1500, 'red', `Cartographer: mapped ${v.entry} → ${v.fn} → ${v.sink}. Reporting to Warlord.`);
    (v.recon || []).forEach(([team, msg]) => add(1500, team, msg));
    add(1300, 'research', `Almanac: static pattern match · ${v.cwe} (${v.kind}). Live intel lookups are opt-in.`);
    add(1400, 'red', `Bloodhound: tainted ${v.input} flows into ${v.fn} and reaches ${v.sink} unescaped.`);
    add(1200, 'red', 'Warlord: Breakwater, prove it in Docker. Sparkler, prepare mutations.');
    add(1100, 'red', 'Proving the finding with a boundary probe from a fresh probe container.');
    add(1500, 'red', 'Sparkler: mutation variants ready · quoting, comments, encodings, length edges.');
    add(1700, 'red', 'Breakwater: boundary check exited 0 — boundary reachable on the original target.');
    add(1200, 'system', 'Arbiter: pre-patch evidence recorded · probe exit 0 on the unpatched snapshot.');
    add(1300, 'blue', `Warden: finding accepted. Stitch, write the fix; Bastion, keep it minimal.`);
    add(1100, 'blue', `Requesting a sanitization patch for ${v.fn} from Muse Spark.`);
    add(1500, 'blue', `Librarian: vault recall · 1 prior ${v.fix} fix found for this pattern.`);
    add(1500, 'blue', `Stitch: bounded sanitation-only replacements applied to ${v.file} (+3 −1).`);
    add(1200, 'blue', 'Proofreader: patch lint clean · no behavior outside the boundary changed.');
    add(1300, 'system', 'Starting a fresh target from the patched snapshot.');
    add(1200, 'system', 'Verifying a fresh target with the original probe.');
    add(1500, 'system', 'Sentinel: regression suite passed on the patched target (3/3).');
    add(1300, 'system', 'Arbiter: boundary check exited 1 — the original probe is blocked after the patch.');
    add(1300, 'system', 'Mirror: differential check · normal inputs identical, attack inputs now rejected.');
    add(1200, 'system', 'Notary: verdict receipt chained · patch sha256 recorded with pre/post exits.');
    add(1100, 'telemetry', 'Gauge: 18,412 → 6,930 tokens sent this run (context compression saved 62%).');
    add(1300, 'system', 'Removing project session containers.');
    add(1400, 'system', 'Session containers, snapshots, and network removed.');
    return L;
  }

  function result(key, topo) {
    const v = vocabFor(key, topo);
    // Custom (user-supplied) maps borrow the diff shape of their lens's showcase target.
    if (!VOCAB[key] || key === 'custom') key = ({ system: 'system_shop_stack', binary: 'binary_argv_echo', repo: 'repo_notes_app' })[topo && topo.lens] || key;
    const sha = 'a3f9c2e17b0d4e55c1f08a6b92de7731f4c0b8e2d9a61f3e05b7c4d2e8f1a9b6';
    const diff = key === 'php_command_sink'
      ? `--- a/${v.file}\n+++ b/${v.file}\n@@ -6,4 +6,6 @@\n function ping($host) {\n-  return shell_exec("ping -c1 " . $host);\n+  if (!preg_match('/^[a-z0-9.-]{1,253}$/i', $host)) { http_response_code(400); return ''; }\n+  return shell_exec("ping -c1 " . escapeshellarg($host));\n }\n`
      : key === 'binary_argv_echo'
        ? `--- a/echo.c\n+++ b/echo.c\n@@ -4,3 +4,3 @@\n void echo_arg(const char *arg) {\n-  printf(arg);\n+  printf("%s", arg);\n }\n`
        : key === 'repo_notes_app'
          ? `--- a/src/db/queries.js\n+++ b/src/db/queries.js\n@@ -21,4 +21,6 @@\n function buildOrderBy(sort) {\n-  return knex.raw('ORDER BY ' + sort);\n+  const allowed = { title: 'title', created: 'created_at', updated: 'updated_at' };\n+  const col = allowed[String(sort)] || 'created_at';\n+  return knex.raw('ORDER BY ??', [col]);\n }\n`
        : key === 'system_shop_stack'
          ? `--- a/cache/redis.conf\n+++ b/cache/redis.conf\n@@ -1,4 +1,5 @@\n-bind 0.0.0.0\n-protected-mode no\n+bind 127.0.0.1 ::1\n+protected-mode yes\n+requirepass \${REDIS_PASSWORD}\n--- a/compose.yml\n+++ b/compose.yml\n@@ -30,3 +30,2 @@\n   cache:\n-    ports: ["6379:6379"]\n+    expose: ["6379"]\n`
        : key === 'mysql_insecure_conf'
          ? `--- a/${v.file}\n+++ b/${v.file}\n@@ -1,5 +1,6 @@\n [mysqld]\n-bind-address = 0.0.0.0\n+bind-address = 127.0.0.1\n+local_infile = 0\n`
          : `--- a/${v.file}\n+++ b/${v.file}\n@@ -12,4 +12,6 @@\n async function searchHandler(req, res) {\n-  const rows = await db.query("SELECT * FROM users WHERE name = '" + req.query.q + "'");\n+  const q = String(req.query.q ?? '').slice(0, 128);\n+  const rows = await db.query('SELECT * FROM users WHERE name = ?', [q]);\n   res.json(rows);\n }\n`;
    return {
      type: 'result',
      status: 'verified',
      replay: true,
      target: key,
      message: `Fake run (scripted): the original probe reached ${v.sink}, the candidate patch blocked it on a fresh target, and normal-input regression still passes.`,
      baseline_passed: true,
      pre_probe_exit: 0,
      post_probe_exit: 1,
      pre_exit_code: 0,
      post_exit_code: 1,
      regression_passed: true,
      cleanup_ok: true,
      diff,
      receipt: { fixture: key, pre_exit_code: 0, post_exit_code: 1, regression_passed: true, differential_passed: true, patch_sha256: sha, prev_receipt_sha: sha, chain_ok: true },
      cost_usd: 0.0142,
      total_tokens: 6930,
      usage: { calls: [
        { role: 'red', model: 'muse-spark', prompt_tokens: 2810, completion_tokens: 412, reasoning_tokens: 655, seconds: 3.4, cost_usd: 0.0051 },
        { role: 'blue', model: 'muse-spark', prompt_tokens: 2240, completion_tokens: 388, reasoning_tokens: 425, seconds: 2.9, cost_usd: 0.0091 }
      ] },
      compression: { raw_tokens_estimated: 18412, compressed_tokens_sent: 6930, tokens_saved: 11482, compression_ratio: 0.62 }
    };
  }

  // Timed player with pause / speed / step. Feeds the same callbacks as a live link.
  class Replay {
    constructor(lines, final, handlers) {
      this.lines = lines;
      this.final = final;
      this.h = handlers;
      this.i = 0;
      this.speed = 1;
      this.paused = false;
      this.timer = 0;
      this.done = false;
    }
    start() { this._next(); return this; }
    _next() {
      clearTimeout(this.timer);
      if (this.paused || this.done) return;
      if (this.i >= this.lines.length) {
        this.timer = setTimeout(() => { this.done = true; this.h.onResult && this.h.onResult(this.final); this.h.onClose && this.h.onClose({ replay: true }); }, 900 / this.speed);
        return;
      }
      const [d, team, msg] = this.lines[this.i];
      this.timer = setTimeout(() => {
        this.i += 1;
        this.h.onLine && this.h.onLine(team, msg);
        this._next();
      }, d / this.speed);
    }
    pause() { this.paused = true; clearTimeout(this.timer); }
    resume() { if (!this.paused) return; this.paused = false; this._next(); }
    toggle() { if (this.paused) this.resume(); else this.pause(); return this.paused; }
    setSpeed(s) { this.speed = s; if (!this.paused) this._next(); }
    step() {
      if (this.done) return;
      clearTimeout(this.timer);
      if (this.i < this.lines.length) { const [, team, msg] = this.lines[this.i]; this.i += 1; this.h.onLine && this.h.onLine(team, msg); }
      if (!this.paused) this._next();
    }
    stop() { this.done = true; clearTimeout(this.timer); }
    progress() { return this.lines.length ? this.i / this.lines.length : 0; }
  }

  SMS.scenario = { script, result, vocabFor, Replay };
})();
