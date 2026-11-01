// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · model/topo-profiles.js — modelled maps for bundled fixtures and generic projects.
// Add a fixture profile: add a PROFILES[key] builder and (optionally) map it in guessProfile().
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const T = (SMS.topology = SMS.topology || {});
  const { builder, addSandbox, hex } = T;

  /* ---------------- modelled profiles ---------------- */
  const PROFILES = {
    node_query_sink(t) {
      const b = builder({ label: t.filename || 'app.js', sub: 'node · fixture node_query_sink' }, 'modelled');
      const http = b.add('http', 'HTTP server', 'subsystem', 'core', { sub: ':3000/tcp' });
      const listen = b.add('listen', 'listener', 'endpoint', http, { sub: '0.0.0.0:3000' });
      const parse = b.add('qs', 'querystring', 'function', http, { sub: 'parse()' });
      const router = b.add('router', 'Router', 'subsystem', 'core', { sub: 'express-style' });
      const rRoot = b.add('r-root', 'GET /', 'endpoint', router);
      const rSearch = b.add('r-search', 'GET /search?q=', 'endpoint', router, { sub: 'user input' });
      const handlers = b.add('handlers', 'Handlers', 'subsystem', 'core', { sub: t.filename || 'app.js' });
      const file = b.add('file', t.filename || 'app.js', 'file', handlers);
      const search = b.add('fn-search', 'searchHandler()', 'function', file);
      const render = b.add('fn-render', 'render()', 'function', file);
      const data = b.add('data', 'Data layer', 'subsystem', 'core', { sub: 'sql driver' });
      const sink = b.add('sink', 'db.query(sql)', 'sink', data, { sub: 'string-built SQL' });
      const table = b.add('tbl', 'users', 'data', data, { sub: 'table' });
      const runtime = b.add('runtime', 'Runtime', 'subsystem', 'core', { sub: 'node' });
      b.add('env', 'process.env', 'data', runtime);
      b.add('pkg', 'package.json', 'file', runtime);
      addSandbox(b);
      b.chain([listen, parse, rSearch, search, sink, table]);
      b.chain([listen, parse, rRoot, render]);
      return b.done({ attackPath: [listen, parse, rSearch, search, sink, table], entryId: rSearch, sinkId: sink, guardLink: [search, sink], fileId: file });
    },
    php_command_sink(t) {
      const b = builder({ label: t.filename || 'index.php', sub: 'php · fixture php_command_sink' }, 'modelled');
      const web = b.add('web', 'Web server', 'subsystem', 'core', { sub: ':8080/tcp' });
      const listen = b.add('listen', 'listener', 'endpoint', web, { sub: '0.0.0.0:8080' });
      const sapi = b.add('sapi', 'php-fpm', 'function', web, { sub: 'SAPI' });
      const router = b.add('router', 'Router', 'subsystem', 'core');
      const rPing = b.add('r-ping', 'GET /?host=', 'endpoint', router, { sub: '$_GET[host]' });
      const rHealth = b.add('r-health', 'GET /health', 'endpoint', router);
      const handlers = b.add('handlers', 'Handlers', 'subsystem', 'core', { sub: t.filename || 'index.php' });
      const file = b.add('file', t.filename || 'index.php', 'file', handlers);
      const fn = b.add('fn-ping', 'ping()', 'function', file);
      const fnOk = b.add('fn-ok', 'health()', 'function', file);
      const shell = b.add('shell', 'Shell', 'subsystem', 'core', { sub: '/bin/sh' });
      const sink = b.add('sink', 'shell_exec($cmd)', 'sink', shell, { sub: 'argv concat' });
      const bin = b.add('bin', '/bin/ping', 'data', shell);
      const fs = b.add('fs', 'Filesystem', 'subsystem', 'core');
      b.add('etc', '/etc/passwd', 'data', fs);
      addSandbox(b);
      b.chain([listen, sapi, rPing, fn, sink, bin]);
      b.chain([listen, sapi, rHealth, fnOk]);
      return b.done({ attackPath: [listen, sapi, rPing, fn, sink, bin], entryId: rPing, sinkId: sink, guardLink: [fn, sink], fileId: file });
    },
    mysql_insecure_conf(t) {
      const b = builder({ label: t.filename || 'my.cnf', sub: 'mysqld · fixture mysql_insecure_conf' }, 'modelled');
      const net = b.add('netsub', 'Network', 'subsystem', 'core', { sub: ':3306/tcp' });
      const listen = b.add('listen', 'client', 'endpoint', net, { sub: '0.0.0.0:3306' });
      const bind = b.add('bind', 'bind-address', 'function', net);
      const cfg = b.add('cfg', 'Config', 'subsystem', 'core', { sub: t.filename || 'my.cnf' });
      const file = b.add('file', t.filename || 'my.cnf', 'file', cfg);
      const sect = b.add('mysqld', '[mysqld]', 'function', file);
      const sink = b.add('sink', 'insecure directive', 'sink', file, { sub: 'unsafe default' });
      const auth = b.add('auth', 'Auth', 'subsystem', 'core');
      const user = b.add('user', "'root'@'%'", 'data', auth);
      b.add('plugin', 'auth plugin', 'function', auth);
      const store = b.add('store', 'Storage', 'subsystem', 'core');
      const db = b.add('db', 'datadir', 'data', store);
      b.add('files', 'secure_file_priv', 'function', store);
      addSandbox(b);
      b.chain([listen, bind, sect, sink, user, db]);
      return b.done({ attackPath: [listen, bind, sect, sink, user], entryId: listen, sinkId: sink, guardLink: [sect, sink], fileId: file });
    },
    binary_argv_echo(t) {
      const b = builder({ label: t.filename || 'argv_echo', sub: 'ELF · fixture binary_argv_echo' }, 'modelled');
      const input = b.add('input', 'Process input', 'subsystem', 'core');
      const argv = b.add('argv', 'argv[1]', 'endpoint', input, { sub: 'attacker controlled' });
      b.add('envp', 'envp', 'endpoint', input);
      const text = b.add('text', '.text', 'section', 'core', { sub: 'code' });
      const main = b.add('main', 'main', 'function', text, { sub: hex(0x401136) });
      const echo = b.add('echo', 'echo_arg', 'function', text, { sub: hex(0x401196) });
      const plt = b.add('plt', '.plt', 'section', 'core', { sub: 'imports' });
      const sink = b.add('sink', 'printf', 'sink', plt, { sub: 'fmt = argv' });
      b.add('puts', 'puts', 'import', plt);
      b.add('strlen', 'strlen', 'import', plt);
      const ro = b.add('rodata', '.rodata', 'section', 'core');
      b.add('fmt', '"%s\\n"', 'string', ro);
      addSandbox(b);
      b.chain([argv, main, echo, sink]);
      return b.done({ attackPath: [argv, main, echo, sink], entryId: argv, sinkId: sink, guardLink: [echo, sink], fileId: main });
    }
  };

  function guessProfile(target = {}, key = '') {
    if (PROFILES[key]) return key;
    const f = String(target.filename || key).toLowerCase();
    if (/\.php$/.test(f)) return 'php_command_sink';
    if (/\.(cnf|conf|ini|sql)$/.test(f)) return 'mysql_insecure_conf';
    if (/\.(elf|bin|exe|so|out)$/.test(f) || /binary/.test(key)) return 'binary_argv_echo';
    return 'node_query_sink';
  }

  function profile(key, target = {}) {
    const k = guessProfile(target, key);
    const topo = PROFILES[k](target);
    topo.profile = k;
    topo.lens = topo.lens || (/^binary/.test(k) ? 'binary' : 'file');
    return topo;
  }

  // Generic project map (path-only knowledge until the stream names files).
  function project(spec = {}) {
    const name = String(spec.path || spec.repo || 'project').split('/').filter(Boolean).pop() || 'project';
    const b = builder({ label: name, sub: spec.image || spec.commit || 'repository' }, 'modelled');
    const entry = b.add('entry', 'Entry', 'subsystem', 'core', { sub: Array.isArray(spec.command) ? spec.command.join(' ').slice(0, 28) : 'start command' });
    const listen = b.add('listen', 'process', 'endpoint', entry);
    const src = b.add('src', 'Source', 'subsystem', 'core', { sub: 'files appear as named' });
    const tests = b.add('tests', 'Tests', 'subsystem', 'core', { sub: Array.isArray(spec.test_command) ? spec.test_command.join(' ').slice(0, 28) : 'regression' });
    b.add('suite', 'regression suite', 'function', tests);
    const deps = b.add('deps', 'Dependencies', 'subsystem', 'core', { sub: 'manifest' });
    b.add('lock', 'lockfile', 'file', deps);
    addSandbox(b);
    return b.done({ attackPath: [listen], entryId: listen, sinkId: null, srcId: src, dynamic: true, lens: 'repo' });
  }

  Object.assign(T, { PROFILES, guessProfile, profile, project });
})();
