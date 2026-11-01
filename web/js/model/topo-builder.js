// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · model/topo-builder.js — topology format + builder helpers shared by every topology source.
//
// Topology format (consumed by SpiderGraph.setTopology / Interpreter.load):
//   { root: {id:'core', label, sub, kind:'core'},
//     nodes: [{ id, label, sub?, kind, parent, delay? }],   kind: subsystem|file|module|function|endpoint|sink|data|infra|section|import|string|cve
//                                                         |dir|host|service|port|config|secret   (meta.public on ports = door in the wall)
//     links: [{ source, target, kind:'call' }],             extra (non-tree) edges
//     flows: [[id, id, ...]],                                 ambient data-flow paths
//     attackPath: [id, ...], entryId, sinkId, guardLink:[a,b], fileId?, srcId?,
//     provenance: 'modelled' | 'parsed', findings?,
//     lens: 'file' | 'repo' | 'binary' | 'system' }   how the map is drawn + narrated (core/lenses.js)
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const T = (SMS.topology = SMS.topology || {});
  const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 48) || 'n';
  const hex = (n, w = 6) => `0x${Number(n).toString(16).padStart(w, '0')}`;

  function builder(rootSpec, provenance) {
    const topo = { root: Object.assign({ id: 'core', kind: 'core', depth: 0 }, rootSpec), nodes: [], links: [], flows: [], attackPath: [], provenance };
    let d = 120;
    const api = {
      topo,
      add(id, label, kind, parent, extra = {}) {
        topo.nodes.push(Object.assign({ id, label, kind, parent: parent || 'core', delay: (d += 70) }, extra));
        return id;
      },
      call(a, b) { topo.links.push({ source: a, target: b, kind: 'call' }); },
      chain(ids) { for (let i = 0; i < ids.length - 1; i += 1) api.call(ids[i], ids[i + 1]); topo.flows.push(ids); },
      done(extra) { return Object.assign(topo, extra); }
    };
    return api;
  }

  function addSandbox(b) {
    const sb = b.add('sandbox', 'Sandbox', 'subsystem', 'core', { sub: 'docker · internal net' });
    b.add('net', 'sms-net', 'infra', sb, { sub: 'internal · no egress' });
    b.add('ctr-target', 'target ctr', 'infra', sb, { sub: 'read-only snapshot' });
    b.add('ctr-probe', 'probe ctr', 'infra', sb, { sub: 'ephemeral' });
    return sb;
  }

  Object.assign(T, { slug, hex, builder, addSandbox });
})();
