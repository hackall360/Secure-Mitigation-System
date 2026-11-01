// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · core/handoff.js — passes a configured run from a selection screen to a visual page.
// Flow: index.html → demo-setup.html | prod-setup.html → demo.html | console.html
//
// Launch object (sessionStorage 'sms.v3.launch'):
//   { v, createdAt, page:'demo'|'console', kind:'live'|'fake', mode, fixture, key?, title, filename?,
//     request:{ path, body?, mcp?, binary? }, topo:{ type:'profile'|'project'|'source'|'binary'|'system', ... },
//     grow?, values?, summary:[[label, value], ...] }
// Binaries are stored in IndexedDB ('sms-v3' / 'blobs' / 'binary') because they can exceed sessionStorage.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});

  const KEY = 'sms.v3.launch';

  function save(launch) {
    const data = Object.assign({ v: 1, createdAt: Date.now() }, launch);
    sessionStorage.setItem(KEY, JSON.stringify(data));
    return data;
  }
  function load() {
    try { return JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch { return null; }
  }
  function clear() { sessionStorage.removeItem(KEY); }

  // Binary bytes can exceed sessionStorage limits — keep them in IndexedDB.
  function db() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open('sms-v3', 1);
      req.onupgradeneeded = () => req.result.createObjectStore('blobs');
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  async function putBlob(name, buf) {
    const d = await db();
    return new Promise((resolve, reject) => {
      const tx = d.transaction('blobs', 'readwrite');
      tx.objectStore('blobs').put(buf, name);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }
  async function getBlob(name) {
    const d = await db();
    return new Promise((resolve, reject) => {
      const tx = d.transaction('blobs', 'readonly');
      const r = tx.objectStore('blobs').get(name);
      r.onsuccess = () => resolve(r.result || null);
      r.onerror = () => reject(r.error);
    });
  }

  // Rebuild the topology on the visual page from the launch description. Returns { topo, buf }.
  async function topology(launch) {
    const T = SMS.topology;
    const t = launch.topo || {};
    if (t.type === 'source') return { topo: T.fromSource(t.source || '', t.language, t.filename), buf: null };
    if (t.type === 'binary') {
      const buf = await getBlob('binary').catch(() => null);
      return buf ? { topo: T.fromBinary(buf, t.filename), buf } : { topo: T.project({ path: t.filename || 'binary' }), buf: null };
    }
    if (t.type === 'project') return { topo: T.project(t.spec || {}), buf: null };
    if (t.type === 'system') return { topo: T.fromSystem(t.services || '', t.ref || 'snapshot', { kindLabel: t.kindLabel }), buf: null };
    return { topo: T.profile(t.key || 'node_query_sink', t.target || {}), buf: null };
  }

  SMS.launch = Object.assign(SMS.launch || {}, { save, load, clear, putBlob, getBlob, topology });
})();
