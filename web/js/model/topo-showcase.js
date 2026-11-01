// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · model/topo-showcase.js — modelled maps that exist so every LENS has a showcase target:
//   repo_notes_app      repo lens   · multi-folder Node app, ORDER BY injection across three files
//   system_shop_stack   system lens · snapshot of a 5-service stack, Redis left open to the internet
// They plug into PROFILES, so SMS.topology.profile(key) and the fake-run scripts just work.
// A backend fixture with the same key gets the same map (live demo); otherwise they are fake-run only.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const T = (SMS.topology = SMS.topology || {});
  const { builder, addSandbox } = T;

  const SHOP_STACK = [
    '# name   image           ports   flags    depends',
    'edge     nginx:1.25      443     public   -> web',
    'web      node:20         3000             -> db,cache',
    'worker   python:3.12                      -> db,cache',
    'db       postgres:16     5432',
    'cache    redis:7         6379    public'
  ].join('\n');

  const SHOWCASE = {
    repo_notes_app(t) {
      const b = builder({ label: t.filename || 'notes-app', sub: 'repository · node · 11 files · 3 deps' }, 'modelled');
      const routes = b.add('d-routes', 'src/routes/', 'dir', 'core', { sub: 'HTTP handlers' });
      const fAuth = b.add('f-auth', 'auth.js', 'file', routes);
      b.add('r-login', 'POST /login', 'endpoint', fAuth);
      const fNotes = b.add('f-notes', 'notes.js', 'file', routes);
      b.add('r-notes', 'GET /notes', 'endpoint', fNotes);
      const fExport = b.add('f-export', 'export.js', 'file', routes);
      const entry = b.add('r-export', 'GET /notes/export?sort=', 'endpoint', fExport, { sub: 'user input: sort' });
      const exp = b.add('fn-export', 'exportNotes()', 'function', fExport);
      const db = b.add('d-db', 'src/db/', 'dir', 'core', { sub: 'data access' });
      const fQ = b.add('f-queries', 'queries.js', 'file', db);
      const order = b.add('fn-order', 'buildOrderBy()', 'function', fQ);
      const sink = b.add('sink', 'knex.raw()', 'sink', fQ, { sub: 'string-built ORDER BY' });
      const fPool = b.add('f-pool', 'pool.js', 'file', db);
      const table = b.add('tbl', 'notes table', 'data', fPool, { sub: 'postgres' });
      const views = b.add('d-views', 'src/views/', 'dir', 'core', { sub: 'templates' });
      const fView = b.add('f-view', 'note.ejs', 'file', views);
      const render = b.add('fn-render', 'render()', 'function', fView);
      const tests = b.add('d-test', 'test/', 'dir', 'core', { sub: 'regression' });
      b.add('f-test', 'notes.test.js', 'file', tests);
      const root = b.add('d-root', 'project root', 'dir', 'core', { sub: 'manifests' });
      const pkg = b.add('f-pkg', 'package.json', 'file', root);
      ['express', 'knex', 'ejs'].forEach((d) => b.add(`dep-${d}`, d, 'import', pkg, { sub: 'dependency' }));
      b.add('f-docker', 'Dockerfile', 'config', root);
      addSandbox(b);
      b.chain([entry, exp, order, sink, table]);
      b.chain(['r-notes', render]);
      b.call(exp, render);
      return b.done({ lens: 'repo', attackPath: [entry, exp, order, sink, table], entryId: entry, sinkId: sink, guardLink: [order, sink], fileId: fQ, srcId: routes });
    },

    system_shop_stack(t) {
      const topo = T.fromSystem(SHOP_STACK, t.filename || 'shop-stack@snap-0420', { provenance: 'modelled', kindLabel: 'compose snapshot' });
      topo.servicesText = SHOP_STACK;
      return topo;
    }
  };

  Object.assign(T.PROFILES, SHOWCASE);
  T.SHOP_STACK = SHOP_STACK;
})();
