// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · model/parse-system.js — real topology for the SYSTEM lens, parsed from a short
// services description (one service per line). Typed on prod-setup.html, mapped as you type.
//
//   # name   image          ports      flags        depends
//   edge     nginx:1.25     443        public   ->  app
//   app      node:20        3000                ->  db,cache
//   db       postgres:16    5432
//   cache    redis:7        6379       public
//
// Tokens: first = service name · `1234` / `80,443` / `53/udp` = ports · `public` (or `exposed`, `*`)
// = reachable from outside the wall · `-> a,b` = talks to · anything with `:` `/` `@` = image.
// Map: snapshot (core) → host per service (R1) → ports, process, data/config (R2) → valuables (R3).
// Attack path: a public datastore wins ("unlocked back door"); otherwise the shortest walk from
// a public port through `->` edges to a datastore.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const T = (SMS.topology = SMS.topology || {});
  const { builder, addSandbox, slug } = T;

  const DATASTORE = /(postgres|mysql|mariadb|mongo|redis|memcache|elastic|opensearch|cassandra|couch|minio|sqlite|clickhouse|rabbit|kafka|etcd|vault)/i;
  const VALUABLE = [[/redis|memcache/i, 'session keys'], [/postgres|mysql|mariadb|sqlite|clickhouse|cassandra/i, 'customer tables'], [/mongo|couch/i, 'documents'], [/elastic|opensearch/i, 'search index'], [/minio/i, 'object bucket'], [/rabbit|kafka/i, 'message queue'], [/etcd|vault/i, 'cluster secrets']];
  const CONFIG = [[/nginx/i, 'nginx.conf'], [/apache|httpd/i, 'httpd.conf'], [/node/i, '.env'], [/python|django|flask/i, 'settings.py'], [/php/i, 'php.ini'], [/redis/i, 'redis.conf'], [/postgres/i, 'pg_hba.conf'], [/mysql|mariadb/i, 'my.cnf']];

  function parseServices(text) {
    const out = [];
    String(text || '').split('\n').forEach((raw) => {
      const line = raw.replace(/#.*$/, '').trim();
      if (!line) return;
      const toks = line.split(/\s+/);
      const svc = { name: toks.shift().replace(/[^\w.-]/g, '').slice(0, 24) || `svc${out.length + 1}`, image: '', ports: [], public: false, deps: [] };
      for (let i = 0; i < toks.length; i += 1) {
        const tk = toks[i];
        if (tk === '->' || tk === '→') { (toks[i + 1] || '').split(',').filter(Boolean).forEach((d) => svc.deps.push(d)); i += 1; }
        else if (/^->/.test(tk)) tk.slice(2).split(',').filter(Boolean).forEach((d) => svc.deps.push(d));
        else if (/^(public|exposed|\*)$/i.test(tk)) svc.public = true;
        else if (/^\d{1,5}(\/(tcp|udp))?(,\d{1,5}(\/(tcp|udp))?)*$/.test(tk)) tk.split(',').forEach((p) => svc.ports.push(/\//.test(p) ? p : `${p}/tcp`));
        else if (!svc.image) svc.image = tk.slice(0, 40);
      }
      if (!out.some((s) => s.name === svc.name)) out.push(svc);
    });
    return out.slice(0, 12);
  }

  function fromSystem(text, ref = 'snapshot', o = {}) {
    const services = parseServices(text);
    const pubCount = services.filter((s) => s.public).length;
    const portCount = services.reduce((n, s) => n + s.ports.length, 0);
    const b = builder({ label: String(ref || 'snapshot').split('@')[0].split('/').filter(Boolean).pop().replace(/\.(ya?ml|json)$/, '').slice(0, 32) || 'snapshot', sub: `${o.kindLabel || 'system snapshot'} · ${services.length} services · ${portCount} ports · ${pubCount} public` }, o.provenance || 'parsed');
    const ids = {};
    services.forEach((s) => {
      const host = b.add(`host-${slug(s.name)}`, s.name, 'host', 'core', { sub: s.image || 'container' });
      const store = DATASTORE.test(`${s.image} ${s.name}`);
      const ports = s.ports.map((p) => b.add(`port-${slug(s.name)}-${slug(p)}`, `:${p.replace('/tcp', '')}`, 'port', host, { sub: s.public ? 'public · outside can knock' : 'internal only', meta: { public: s.public } }));
      const proc = b.add(`svc-${slug(s.name)}`, (s.image.split(/[:@]/)[0].split('/').pop() || s.name).slice(0, 20), 'service', host, { sub: store ? 'datastore' : 'process' });
      let data = null;
      if (store) {
        const v = VALUABLE.find(([re]) => re.test(`${s.image} ${s.name}`));
        data = b.add(`data-${slug(s.name)}`, v ? v[1] : 'stored data', 'data', proc, { sub: 'valuable' });
      }
      const cf = CONFIG.find(([re]) => re.test(`${s.image} ${s.name}`));
      const cfg = cf ? b.add(`cfg-${slug(s.name)}`, cf[1], 'config', proc) : null;
      ports.forEach((p) => b.call(p, proc));
      ids[s.name] = { host, proc, ports, data, cfg, store, svc: s };
    });
    // talks-to edges
    services.forEach((s) => s.deps.forEach((d) => { if (ids[d]) b.call(ids[s.name].proc, ids[d].ports[0] || ids[d].proc); }));
    // ambient flows: each public door → its process → what it talks to
    services.filter((s) => s.public && ids[s.name].ports.length).forEach((s) => {
      const me = ids[s.name];
      const tail = s.deps.map((d) => ids[d]).filter(Boolean)[0];
      b.topo.flows.push([me.ports[0], me.proc].concat(tail ? [tail.ports[0] || tail.proc, tail.proc] : []).filter((x, i, a) => x && a.indexOf(x) === i));
    });
    addSandbox(b);

    // attack path
    let path = [];
    const pubStore = services.find((s) => s.public && ids[s.name].store && ids[s.name].ports.length);
    if (pubStore) { const x = ids[pubStore.name]; path = [x.ports[0], x.proc, x.data].filter(Boolean); }
    else {
      const starts = services.filter((s) => s.public && ids[s.name].ports.length);
      const seen = new Set();
      const q = starts.map((s) => [s.name]);
      while (q.length && !path.length) {
        const trail = q.shift();
        const cur = trail[trail.length - 1];
        if (seen.has(cur)) continue;
        seen.add(cur);
        if (ids[cur].store && trail.length > 1) {
          path = [ids[trail[0]].ports[0]];
          trail.forEach((n, i) => { if (i > 0 && ids[n].ports[0]) path.push(ids[n].ports[0]); path.push(ids[n].proc); });
          if (ids[cur].data) path.push(ids[cur].data);
          break;
        }
        ids[cur].svc.deps.forEach((d) => { if (ids[d]) q.push(trail.concat(d)); });
      }
      if (!path.length && starts.length) { const x = ids[starts[0].name]; path = [x.ports[0], x.proc, x.cfg].filter(Boolean); }
    }
    path = path.filter((x, i, a) => a.indexOf(x) === i);
    if (path.length >= 2) b.topo.flows.push(path.slice());
    return b.done({
      lens: 'system', attackPath: path, entryId: path[0] || null, sinkId: path[path.length - 1] || null,
      guardLink: path.length >= 2 ? path.slice(-2) : null, fileId: path.length >= 2 ? path[path.length - 2] : null,
      findings: { services: services.length, ports: portCount, public: pubCount, datastores: services.filter((s) => ids[s.name].store).length, exposedStores: services.filter((s) => s.public && ids[s.name].store).map((s) => s.name) }
    });
  }

  Object.assign(T, { parseServices, fromSystem });
})();
