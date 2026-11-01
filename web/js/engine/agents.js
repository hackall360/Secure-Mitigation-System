// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · engine/agents.js — Agent state: speaking, tethers, team filter, working indicator.
// Mixin: methods are added to SMS.SpiderGraph.prototype. Load after engine/graph.js.
'use strict';
(() => {
  const SMS = window.SMS;
  const { now } = SMS.engine;

  Object.assign(SMS.SpiderGraph.prototype, {
    agent(id) { return this.agents.get(id) || null; },

    speak(id) {
      const a = this.agents.get(id);
      if (!a) return;
      a.speakAt = now();
      a.awake = true;
      a.msgs += 1;
      this.emit('speak', a);
    },

    wake(ids) { ids.forEach((id) => { const a = this.agents.get(id); if (a) a.awake = true; }); },

    tether(agentId, nodeId, ms = 2600) {
      const a = this.agents.get(agentId);
      if (!a || !this.nodes.has(nodeId)) return;
      this.tethers = this.tethers.filter((t) => t.agent !== agentId);
      this.tethers.push({ agent: agentId, node: nodeId, born: now(), until: now() + ms, color: a.color });
    },

    setTeamFilter(set) { this.teamFilter = set && set.size ? set : null; },

    _teamVisible(team) { return !this.teamFilter || this.teamFilter.has(team); },

    // Which agent is busy between events, and on what. Drawn as a spinning ring, a live
    // tether and an elapsed-since-last-event counter, so long real-time gaps never look frozen.
    setWorking(agentId, nodeId) {
      if (!agentId) { this.working = null; return; }
      this.working = { agent: agentId, node: nodeId && this.nodes.has(nodeId) ? nodeId : null, since: now() };
    }
  });
})();
