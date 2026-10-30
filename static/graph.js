// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMSGraph: cinematic force-directed phase graph (canvas 2D, zero-dep, CSP-safe).
// Primary renderer for the verification pipeline. Fallback = the existing
// log-derived timeline strip (#scan-timeline in panels.js), which stays mounted
// and keeps rendering every event even when this engine is off or unavailable.
// Team visual language: green = Matrix glow (generation), red = neon attack
// (jagged + glitch), blue = radar sweep (smooth pulse), purple = verified
// freeze (nodes lock in place). Honors prefers-reduced-motion (static layout).
'use strict';
(() => {
  // Node ids mirror the pipeline stages in static/index.html (data-stage).
  const STAGES = ['sandbox', 'baseline', 'analysis', 'probe', 'patch', 'regression', 'cleanup'];
  const TEAM_OF = {
    sandbox: 'system', baseline: 'system', analysis: 'red',
    probe: 'red', patch: 'blue', regression: 'blue', cleanup: 'system',
  };
  const COLORS = {
    green: '#34f5a2', red: '#ff3b5c', blue: '#38c8ff',
    purple: '#b06cff', system: '#8b98ad',
  };

  let canvas = null;
  let ctx = null;
  let nodes = [];
  let edges = [];
  let particles = [];
  let fallback = true; // until init() binds a usable 2d context
  let verified = false;
  let raf = 0;
  let activeStage = '';
  let motionOK = true;

  function reducedMotion() {
    try {
      return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    } catch {
      return false;
    }
  }

  function layout(seedW, seedH) {
    const w = seedW || 640;
    const h = seedH || 160;
    nodes = STAGES.map((stage, i) => ({
      id: stage,
      team: TEAM_OF[stage] || 'system',
      x: (w * (i + 0.7)) / (STAGES.length + 0.4),
      y: h / 2 + (i % 2 === 0 ? -h * 0.14 : h * 0.14),
      vx: 0,
      vy: 0,
      fx: null, // purple freeze pins verified nodes
      fy: null,
    }));
    edges = [];
    for (let i = 0; i < nodes.length - 1; i += 1) {
      edges.push({ from: nodes[i], to: nodes[i + 1], kind: nodes[i + 1].id });
    }
  }

  function spawnParticle(edge) {
    // Green (generation): Matrix-green motes drifting down-link.
    // Red (attack): fast jagged red shards on probe edges.
    // Blue (defense): smooth cyan sweep pulses on patch edges.
    const team = edge.to.team;
    const speed = team === 'red' ? 0.10 : team === 'blue' ? 0.05 : 0.03;
    particles.push({ edge, t: 0, speed, team });
    if (particles.length > 120) particles.splice(0, particles.length - 120);
  }

  function step() {
    // Tiny spring layout; verified-purple nodes stay frozen (fx/fy set).
    const w = canvas ? canvas.width : 640;
    const h = canvas ? canvas.height : 160;
    nodes.forEach((n) => {
      if (n.fx !== null && n.fx !== undefined) return;
      const home = layoutHome(n.id, w, h);
      n.vx += (home.x - n.x) * 0.004;
      n.vy += (home.y - n.y) * 0.004;
      n.vx *= 0.92;
      n.vy *= 0.92;
      n.x += n.vx;
      n.y += n.vy;
    });
    particles.forEach((p) => {
      p.t += p.speed;
      if (p.t >= 1) {
        p.t = 0;
        if (p.team === 'red' && !reducedMotion()) {
          // Glitch: red shards jitter the target node on impact.
          p.edge.to.x += (Math.random() - 0.5) * 6;
          p.edge.to.y += (Math.random() - 0.5) * 6;
        }
      }
    });
    particles = particles.filter((p) => p.t < 1 || true).slice(-120);
  }

  function layoutHome(stage, w, h) {
    const i = STAGES.indexOf(stage);
    return {
      x: (w * (i + 0.7)) / (STAGES.length + 0.4),
      y: h / 2 + (i % 2 === 0 ? -h * 0.14 : h * 0.14),
    };
  }

  function teamColor(node) {
    if (verified && (node.id === 'probe' || node.id === 'patch' || node.id === 'regression')) {
      return COLORS.purple; // verified secure: deep neon purple, frozen
    }
    if (node.id === activeStage) return COLORS[node.team] || COLORS.system;
    return COLORS.system;
  }

  function paint() {
    if (!ctx || !canvas) return;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    edges.forEach((e) => {
      ctx.strokeStyle = 'rgba(139,152,173,0.35)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      if (e.to.team === 'red') {
        // Jagged red attack link.
        const mx = (e.from.x + e.to.x) / 2;
        const my = (e.from.y + e.to.y) / 2 - 8;
        ctx.moveTo(e.from.x, e.from.y);
        ctx.lineTo(mx, my + 6);
        ctx.lineTo(mx + 6, my - 6);
        ctx.lineTo(e.to.x, e.to.y);
      } else {
        ctx.moveTo(e.from.x, e.from.y);
        ctx.lineTo(e.to.x, e.to.y);
      }
      ctx.stroke();
    });
    particles.forEach((p) => {
      const x = p.edge.from.x + (p.edge.to.x - p.edge.from.x) * p.t;
      const y = p.edge.from.y + (p.edge.to.y - p.edge.from.y) * p.t;
      ctx.fillStyle = p.team === 'green' ? COLORS.green
        : p.team === 'red' ? COLORS.red
          : p.team === 'blue' ? COLORS.blue : COLORS.system;
      ctx.beginPath();
      ctx.arc(x, y, p.team === 'red' ? 2.4 : 1.8, 0, Math.PI * 2);
      ctx.fill();
    });
    const now = (typeof performance !== 'undefined' && performance.now) ? performance.now() : 0;
    nodes.forEach((n) => {
      const color = teamColor(n);
      const frozen = verified && (n.id === 'probe' || n.id === 'patch' || n.id === 'regression');
      ctx.save();
      ctx.shadowColor = color;
      ctx.shadowBlur = n.id === activeStage ? 18 : 8;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.id === activeStage ? 9 : 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
      if (n.team === 'blue' && n.id === activeStage && !reducedMotion()) {
        // Radar sweep: rotating arc on the active blue node.
        const a = (now / 600) % (Math.PI * 2);
        ctx.strokeStyle = COLORS.blue;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(n.x, n.y, 13, a, a + Math.PI * 0.6);
        ctx.stroke();
      }
      if (frozen) {
        ctx.strokeStyle = COLORS.purple;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(n.x - 11, n.y - 11, 22, 22);
      }
      ctx.fillStyle = 'rgba(230,238,248,0.85)';
      ctx.font = '10px system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(n.id, n.x, n.y + 22);
    });
  }

  function loop() {
    raf = 0;
    if (fallback || !ctx) return;
    step();
    paint();
    // Purple freeze: verified graph stops animating (locked in place).
    if (verified || reducedMotion()) return;
    if (motionOK && !document.hidden) raf = requestAnimationFrame(loop);
  }

  function kick() {
    if (fallback || reducedMotion()) {
      paint();
      return;
    }
    if (!raf) raf = requestAnimationFrame(loop);
  }

  function init(canvasId) {
    try {
      motionOK = !reducedMotion();
      canvas = document.getElementById(canvasId || 'phase-graph');
      if (!canvas || typeof canvas.getContext !== 'function') {
        fallback = true;
        return false;
      }
      const maybe = canvas.getContext('2d');
      if (!maybe) {
        fallback = true;
        return false;
      }
      ctx = maybe;
      layout(canvas.width, canvas.height);
      fallback = false;
      paint();
      return true;
    } catch {
      fallback = true;
      return false;
    }
  }

  function isFallback() {
    // Fallback = timeline strip (#scan-timeline) stays the rendered path.
    if (fallback) return true;
    try {
      const strip = document.getElementById('scan-timeline');
      return !strip ? true : false;
    } catch {
      return true;
    }
  }

  function update(event) {
    // event: {stage} | {team, text} | {result} — read-only, never throws.
    try {
      if (!event || typeof event !== 'object') return;
      if (event.stage) {
        activeStage = event.stage;
        const edge = edges.find((e) => e.to.id === event.stage);
        if (edge && !fallback) {
          const team = event.team === 'green' ? 'green' : edge.to.team;
          spawnParticle({ from: edge.from, to: edge.to, kind: edge.kind });
          const last = particles[particles.length - 1];
          if (last) last.team = team;
        }
      }
      if (event.result) {
        const status = String(event.result.status || '');
        verified = ['verified', 'completed', 'no_findings', 'not_confirmed'].includes(status);
        if (verified) {
          nodes.forEach((n) => {
            if (n.id === 'probe' || n.id === 'patch' || n.id === 'regression') {
              n.fx = n.x;
              n.fy = n.y;
            }
          });
        } else {
          verified = false;
          nodes.forEach((n) => {
            n.fx = null;
            n.fy = null;
          });
        }
      }
      if (!fallback) kick();
    } catch { /* graph is decorative; never break logging */ }
  }

  function dispose() {
    if (raf) {
      try {
        cancelAnimationFrame(raf);
      } catch { /* noop */ }
      raf = 0;
    }
    particles = [];
  }

  window.addEventListener('pagehide', dispose);

  window.SMSGraph = {
    init, update, isFallback, kick, dispose,
    stages: STAGES,
  };
})();
