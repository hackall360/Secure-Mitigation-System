// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · stream/interpreter.js — turns the orchestrator's (team, msg) stream into
// graph choreography and normalized HUD events.
//
//   interp.load(topo, { grow })     reset + draw a topology (grow: Greenhouse reveals nodes live)
//   interp.line(team, msg, meta)    one stream line  → returns + emits 'event'
//   interp.result(payload)          final verdict    → emits 'result'
//   interp.on('stage' | 'event' | 'result' | 'load', fn)
//
// Pipeline per line:  rules.stageOf → speaker/recipient → discover entities
//                     → first matching beat in stream/choreography.js → bubble → event
// Event shape: { seq, at, team, raw, speaker, to, toLabel, label, text, body, stage, exit, entities }
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});
  const P = () => SMS.palette;
  const T = () => SMS.topology;
  const R = () => SMS.rules;

  class Interpreter {
    constructor(graph) {
      this.g = graph;
      this.listeners = {};
      this.reset();
    }

    on(name, fn) { (this.listeners[name] = this.listeners[name] || []).push(fn); return this; }
    emit(name, p) { (this.listeners[name] || []).forEach((fn) => { try { fn(p); } catch { /* HUD errors never stop the stream */ } }); }

    reset() {
      this.seq = 0;
      this.stageIdx = -1;
      this.stage = '';
      this.topo = null;
      this.lastFile = null;
      this.labels = new Map();
      this.growQueue = [];
      this.stats = { events: 0, packets: 0, discovered: 0, findings: 0, patches: 0, verified: 0 };
      this.patched = false;
      this.compromised = false;
      this.memberTurn = {};
    }

    load(topo, o = {}) {
      this.reset();
      this.topo = topo;
      if (o.grow) {
        // Greenhouse mode: start with the core + subsystems, reveal the rest as it is "planted".
        const keep = topo.nodes.filter((n) => n.parent === 'core');
        this.growQueue = topo.nodes.filter((n) => n.parent !== 'core');
        this.g.setTopology(Object.assign({}, topo, { nodes: keep, links: [], flows: [], attackPath: [] }));
      } else {
        this.g.setTopology(topo);
      }
      this.g.nodes.forEach((n) => this.labels.set(n.label.toLowerCase(), n.id));
      this.emit('load', topo);
    }

    /* ---------- helpers (also used by choreography beats) ---------- */
    _id(label) { return this.labels.get(String(label).toLowerCase()) || null; }
    _sinkId() { return (this.topo && this.topo.sinkId && this.g.node(this.topo.sinkId)) ? this.topo.sinkId : null; }
    _path() { return (this.topo && this.topo.attackPath ? this.topo.attackPath : []).filter((id) => this.g.node(id)); }
    _leader(team) { const a = P().teamAgents(team).find((x) => x.leader); return a ? a.id : 'Conductor'; }

    _discover(label, kind, parentId, extra = {}) {
      const known = this._id(label);
      if (known) return known;
      const parent = parentId && this.g.node(parentId) ? parentId : 'core';
      const id = `dyn-${T().slug(label)}-${this.g.nodes.size}`;
      this.g.addNode(Object.assign({ id, label, kind, parent, state: 'scanned' }, extra));
      this.labels.set(label.toLowerCase(), id);
      this.stats.discovered += 1;
      return id;
    }

    _grow(n = 3, speaker = 'Greenhouse') {
      const out = [];
      for (let i = 0; i < n && this.growQueue.length; i += 1) {
        const spec = this.growQueue.shift();
        const node = this.g.addNode(Object.assign({}, spec, { state: 'grown', delay: i * 180 }));
        if (node) { this.labels.set(node.label.toLowerCase(), node.id); out.push(node.id); }
      }
      if (!this.growQueue.length && this.topo) {
        (this.topo.links || []).forEach((l) => this.g.link(l.source, l.target, l.kind || 'call'));
        this.g.setFlows(this.topo.flows || []);
        this.g.setAttackPath(this.topo.attackPath || []);
      }
      out.forEach((id, i) => this.g.send(i % 2 ? 'Seedling' : speaker, id, { label: i ? '' : 'PLANT', delay: i * 160, dur: 1100 }));
      return out;
    }

    _advanceStage(team, text) {
      const next = R().stageOf(team, text, this.stageIdx);
      if (next) {
        const idx = P().STAGES.indexOf(next);
        if (next === 'analysis' && team === 'red' && text.toLowerCase().includes('reviewing the cumulative')) this.stageIdx = -1;
        if (idx >= this.stageIdx || (next === 'sandbox' && this.stageIdx < 0)) {
          this.stageIdx = idx;
          if (next !== this.stage) { this.stage = next; this.g.setPhase(next); this.emit('stage', next); }
        }
      }
      return this.stage || 'sandbox';
    }

    // Who said it, and to whom. Named agents in the text win; otherwise the family lead.
    _speakers(team, text, fam, names, ents) {
      let speaker = names[0] || null;
      if (!speaker) speaker = (fam === 'orange' && R().verifierFor(text)) || P().speakerFor(team);
      if (team === 'research' && !names.length && /scanner|trivy|grype|osv-scanner|dependency/.test(text.toLowerCase())) speaker = 'Lantern';
      const spk = P().agent(speaker) || P().agent(P().speakerFor(team));
      const to = names.find((n) => n !== spk.id) || null;
      let label = R().bubbleLabel(text, ents);
      const toAgent = to && P().agent(to);
      if (spk.leader && toAgent && ents.exit === null) label = `ORDERS ▸ ${to.toUpperCase()}`;
      else if (toAgent && toAgent.leader && /report/i.test(text) && ents.exit === null) label = `REPORT ▸ ${to.toUpperCase()}`;
      return { spk, speaker: spk.id, to, label };
    }

    // Files, fn(), routes and CVEs named in the line become nodes on the map.
    _discoverEntities(ents) {
      const g = this.g;
      let focus = null;
      const srcParent = (this.topo && (this.topo.srcId || (g.node('handlers') ? 'handlers' : null))) || 'core';
      const lens = this.g.lens || 'file';
      ents.files.forEach((f) => {
        // Repo lens: a path grows its folder first, so the city gets a new neighbourhood.
        const dir = lens === 'repo' && f.includes('/') ? `${f.split('/').slice(0, -1).join('/')}/` : null;
        const parent = dir ? (this._id(dir) || this._discover(dir, 'dir', srcParent)) : srcParent;
        const id = this._discover(f.split('/').pop(), 'file', parent, { sub: f.includes('/') ? f : '' });
        this.lastFile = id; focus = focus || id;
      });
      // System lens: ports named in the stream are doors in the wall.
      if (lens === 'system') ents.ports.forEach((p) => { const id = this._discover(`:${p.replace('/tcp', '')}`, 'port', 'core', { sub: p }); focus = focus || id; });
      ents.fns.forEach((f) => { const id = this._discover(f, 'function', this.lastFile || (this.topo && this.topo.fileId) || srcParent); focus = focus || id; });
      ents.routes.forEach((r) => { const id = this._discover(r, 'endpoint', g.node('router') ? 'router' : g.node('entry') ? 'entry' : 'core'); focus = focus || id; });
      ents.cves.forEach((cv) => { const id = this._discover(cv, 'cve', this._sinkId() || 'core', { state: 'intel' }); g.setState(id, 'intel', true); focus = focus || id; });
      return focus;
    }

    /* ---------- one live line ---------- */
    line(rawTeam, rawText, meta) {
      const team = String(rawTeam || 'system');
      const text = String(rawText === undefined || rawText === null ? '' : rawText);
      const g = this.g;
      const fam = P().family(team);
      const names = P().namesIn(text);
      const ents = T().extract(text);
      const stage = this._advanceStage(team, text);
      const who = this._speakers(team, text, fam, names, ents);

      const c = {
        g, it: this, team, fam, text, lower: text.toLowerCase(), names, ents, stage,
        speaker: who.speaker, spk: who.spk, to: who.to, label: who.label,
        focus: this._discoverEntities(ents),
        path: this._path(), sink: this._sinkId(),
        fileId: this.lastFile || (this.topo && this.topo.fileId) || null
      };
      const beat = (SMS.choreography || []).find((b) => b.when(c));
      if (beat) beat.run(c);

      const { spk, speaker } = c;
      let to = c.to;
      if (!to && c.label) to = spk.leader ? 'Conductor' : this._leader(spk.team);
      if (to === speaker) to = spk.leader ? 'Conductor' : this._leader(spk.team);
      if (to && c.label !== '') g.send(speaker, to, { label: c.label });
      else g.speak(speaker);
      if (c.focus) g.focus(c.focus);
      else if (stage === 'cleanup') g.focus(null);
      // Between events the speaker is shown as working on whatever it last touched.
      if (stage === 'cleanup' && /removed/.test(c.lower)) g.setWorking(null);
      else g.setWorking(speaker, c.focus || (to && g.node(to) ? to : null) || this._sinkId() || 'core');

      this.seq += 1;
      this.stats.events += 1;
      this.stats.packets = this.seq;
      const ev = {
        seq: this.seq,
        at: R().eventTime(meta),
        team: spk.team,
        raw: team,
        speaker,
        to: to || null,
        toLabel: to ? (P().agent(to) ? to : ((g.node(to) || {}).label || to)) : null,
        label: c.label,
        text,
        body: text.replace(new RegExp(`^${speaker}:\\s*`), ''),
        stage,
        exit: ents.exit,
        entities: ents,
        beat: beat ? beat.name : null
      };
      this.emit('event', ev);
      return ev;
    }

    /* ---------- final result ---------- */
    result(payload = {}) {
      const g = this.g;
      const status = String(payload.status || '');
      const ok = R().OK_STATUSES.includes(status);
      const verified = status === 'verified' || (status === 'completed' && this.patched);
      if (verified) {
        g.setVerdict('verified');
        this.stats.verified += 1;
      } else if (!ok) {
        g.setVerdict('failed');
        const sink = this._sinkId();
        if (sink && this.compromised) g.setState(sink, 'compromised');
      } else {
        g.setVerdict('clear');
        g.sweepWave('#2dd4bf');
      }
      g.send('Arbiter', 'core', { label: `VERDICT · ${status.toUpperCase().replace(/_/g, ' ')}`.slice(0, 28), color: verified ? P().TEAMS.purple.hue : ok ? '#2dd4bf' : P().TEAMS.red.hue, dur: 1600 });
      const receipt = payload.receipt || payload.verdict_receipt;
      const sha = receipt && (receipt.patch_sha256 || receipt.patch_hash);
      if (sha) g.send('Notary', 'Arbiter', { label: `SHA ${String(sha).slice(0, 10)}…`, delay: 500 });
      g.focus(null);
      g.setWorking(null);
      this.emit('result', { status, ok, verified, payload });
    }
  }

  SMS.Interpreter = Interpreter;
})();
