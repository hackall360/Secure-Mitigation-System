// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · engine/graph.js — SpiderGraph: radial "spider web" system map on canvas 2D.
//   · the target sits at the center; subsystems, files, symbols and sinks float outward on rings
//   · six agent families orbit the web in fixed sectors, each agent a shade of its family hue
//   · data-flow particles run along program paths; tainted paths turn red, guards turn blue
//   · communication is drawn as labelled bubbles flying between agents and nodes
// This file holds the constructor and the event emitter. Behaviour lives in mixins:
//   graph-model · layout · agents · effects · camera · input · loop · render-scene · render-nodes · render-agents
// Zero dependencies, CSP-safe, DPR-aware, reduced-motion aware.
'use strict';
(() => {
  const SMS = window.SMS;
  const { now, reducedMotion } = SMS.engine;

  class SpiderGraph {
    constructor(canvas, opts = {}) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.opts = Object.assign({ mode: 'console', ambient: false, interactive: true, agents: true }, opts);
      this.nodes = new Map();
      this.links = [];
      this.linkIndex = new Map();
      this.agents = new Map();
      this.packets = [];
      this.particles = [];
      this.waves = [];
      this.tethers = [];
      this.flows = [];
      this.attackPath = [];
      this.listeners = {};
      this.layers = { web: true, flow: true, comms: true, labels: 'auto', sweep: true };
      this.teamFilter = null;
      this.hover = null;
      this.selected = null;
      this.focusId = null;
      this.director = this.opts.mode === 'demo';
      this.userCam = false;
      this.cam = { x: 0, y: 0, s: 0.6 };
      this.camT = { x: 0, y: 0, s: 0.6 };
      this.w = 0; this.h = 0; this.dpr = 1;
      this.insets = { l: 0, r: 0, t: 0, b: 0 };
      this.vx0 = 0; this.vy0 = 0;
      this.t0 = now();
      this.last = this.t0;
      this.raf = 0;
      this.running = false;
      this.verdict = '';
      this.phase = '';
      this.sweepA = -Math.PI / 2;
      this.flowClock = 0;
      this.sendCursor = 0;
      this.working = null;
      this.maxDepth = 3;
      this.drag = null;
      this.reduced = reducedMotion();
      this._resize();
      this._bind();
      if (this.opts.agents) this._initAgents();
      this.start();
    }

    /* events: 'select' | 'hover' | 'hovermove' | 'speak' | 'discover' */
    on(name, fn) { (this.listeners[name] = this.listeners[name] || []).push(fn); return this; }
    emit(name, payload) { (this.listeners[name] || []).forEach((fn) => { try { fn(payload); } catch { /* listener errors never stop the frame */ } }); }
  }

  SMS.SpiderGraph = SpiderGraph;
})();
