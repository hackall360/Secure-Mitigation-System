// panels.js - Scan-timeline markers fed by writeLine(team, msg) in app.js.
// CSP-safe: textContent and setAttribute only, no innerHTML, no eval, no inline handlers.
// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
'use strict';

(function () {
  const MAX_MARKERS = 100;
  const LABEL_CHARS = 72;
  const TITLE_CHARS = 280;
  const TEXT_CAP = 2000;
  const SCROLL_PIN_PX = 80;
  const KNOWN_TEAMS = ['red', 'blue', 'research', 'green', 'system'];
  // Scan openers only (not mid-run milestones): a new run clears the timeline.
  // Matches live strings in workflow.py / project_workflow.py / cve_workflow.py
  // and the client-side openers in app.js (spec accepted, greenhouse growing).
  const SCAN_START = /creating an internal docker network|original fixture is ready|original-project normal-input checks passed|project specification accepted|greenhouse is growing|deep scan:\s*snapshotting/i;
  const EXIT_RE = /boundary check exited\s+(\d+)|\bexit\s+(\d+)/i;
  const BLOCKED_RE = /not confirmed|rejected|rolled back|replacement exceeds|exceeds[^.]{0,40}budget|did not use a fresh target/i;
  const REGRESSION_RE = /starting a fresh target|verifying a fresh target|regression|normal-input checks passed|original fixture is ready|original-project normal-input/i;
  const PATCH_RE = /requesting a sanitization patch|bounded sanitation|sanitization|sanitizer|diff --git|cumulative diff/i;
  const RESEARCH_RE = /research|intel|cve|osv|ghsa|epss|trivy|grype|scanner|deep scan|static signals|nvd|advisory|threat.intel|red patterns|blue patterns|grounded/i;
  const PROBE_RE = /proving the finding|boundary|attack|reachable/i;
  const CLEANUP_RE = /cleanup|session containers, snapshots, and network removed|removing project session containers|containers removed/i;
  const BUILD_RE = /creating an internal docker network|immutable target snapshot|greenhouse|growing|seedling|planted|\bgrew\b|wobbly|building from|snapshot/i;

  // rAF-batched append queue: writeLine can burst (deep-scan loops); one
  // fragment + one layout read per frame keeps the strip jank-free.
  let pending = [];
  let scheduled = false;
  let markerCount = 0;

  function classify(team, lower) {
    const exit = EXIT_RE.exec(lower);
    if (exit) {
      const code = Number(exit[1] !== undefined ? exit[1] : exit[2]);
      if (code === 0) return { glyph: '◆', kind: 'success', label: 'Boundary reached' };
      if (code === 1) return { glyph: '✕', kind: 'blocked', label: 'Blocked' };
      return { glyph: '?', kind: 'event', label: 'Inconclusive' };
    }
    if (BLOCKED_RE.test(lower)) return { glyph: '✕', kind: 'blocked', label: 'Blocked' };
    // Regression before patch: "fresh target from the patched snapshot" must read as re-verify, not patch.
    if (REGRESSION_RE.test(lower)) return { glyph: '✔', kind: 'test', label: 'Test' };
    if (PATCH_RE.test(lower)) return { glyph: '✚', kind: 'patch', label: 'Patch' };
    if (RESEARCH_RE.test(lower)) return { glyph: '◉', kind: 'research', label: 'Research' };
    // Probe after research/regression so intel and re-verify lines keep their phase color.
    if (PROBE_RE.test(lower)) return team === 'red'
      ? { glyph: '➤', kind: 'attack', label: 'Attack attempted' }
      : { glyph: '➤', kind: 'attack', label: 'Probe event' };
    // Cleanup before build: the teardown line mentions snapshots/network too.
    if (CLEANUP_RE.test(lower)) return { glyph: '○', kind: 'cleanup', label: 'Cleanup' };
    if (BUILD_RE.test(lower)) return { glyph: '▣', kind: 'build', label: 'Build' };
    return { glyph: '·', kind: 'event', label: 'Event' };
  }

  function clearMarkers(timeline) {
    timeline.querySelectorAll('.timeline-marker').forEach((node) => node.remove());
    markerCount = 0;
  }

  function reducedMotion() {
    try {
      return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    } catch {
      return false;
    }
  }

  function buildMarker(known, text, slot, stamp) {
    const marker = document.createElement('span');
    marker.className = 'timeline-marker';
    marker.dataset.team = known;
    marker.dataset.kind = slot.kind;
    const dot = document.createElement('i');
    dot.className = 'dot';
    dot.setAttribute('aria-hidden', 'true');
    const glyph = document.createElement('b');
    glyph.className = 'glyph';
    glyph.setAttribute('aria-hidden', 'true');
    glyph.textContent = slot.glyph;
    const label = document.createElement('span');
    label.className = 'tlabel';
    label.textContent = `${slot.label} · ${text.slice(0, LABEL_CHARS)}${text.length > LABEL_CHARS ? '…' : ''}`;
    const time = document.createElement('time');
    time.textContent = stamp;
    marker.setAttribute('title', text.slice(0, TITLE_CHARS));
    marker.append(dot, glyph, label, time);
    if (reducedMotion()) marker.style.animation = 'none';
    return marker;
  }

  function flush() {
    scheduled = false;
    try {
      const timeline = document.getElementById('scan-timeline');
      if (!timeline || !pending.length) {
        pending = [];
        return;
      }
      const batch = pending;
      pending = [];
      const pinned = timeline.scrollWidth - timeline.scrollLeft - timeline.clientWidth < SCROLL_PIN_PX;
      const stamp = new Date().toLocaleTimeString([], { hour12: false });
      const frag = document.createDocumentFragment();
      let fresh = 0;
      for (let i = 0; i < batch.length; i += 1) {
        const known = KNOWN_TEAMS.includes(batch[i][0]) ? batch[i][0] : 'system';
        const raw = String(batch[i][1] === undefined || batch[i][1] === null ? '' : batch[i][1]);
        const text = raw.length > TEXT_CAP ? raw.slice(0, TEXT_CAP) : raw;
        const lower = text.toLowerCase();
        if (SCAN_START.test(text)) {
          clearMarkers(timeline);
          frag.replaceChildren();
          fresh = 0;
        }
        frag.append(buildMarker(known, text, classify(known, lower), stamp));
        fresh += 1;
      }
      const empty = timeline.querySelector('.empty');
      if (empty) empty.remove();
      timeline.append(frag);
      markerCount += fresh;
      // Trim oldest-first without a full NodeList walk per event.
      let guard = fresh + 1;
      while (markerCount > MAX_MARKERS && guard > 0) {
        const first = timeline.querySelector('.timeline-marker');
        if (!first) {
          markerCount = 0;
          break;
        }
        first.remove();
        markerCount -= 1;
        guard -= 1;
      }
      if (pinned) timeline.scrollLeft = timeline.scrollWidth;
    } catch { /* timeline is decorative; never break logging */ }
  }

  function scheduleFlush() {
    if (scheduled) return;
    scheduled = true;
    try {
      if (typeof requestAnimationFrame === 'function') requestAnimationFrame(flush);
      else setTimeout(flush, 0);
    } catch {
      scheduled = false;
    }
  }

  // Every log event queues one marker: stage color dot + text glyph + short label.
  function renderTimeline(team, msg) {
    try {
      if (!document || typeof document.getElementById !== 'function') return;
      if (!document.getElementById('scan-timeline')) return;
      pending.push([team, msg]);
      if (pending.length > MAX_MARKERS) pending.splice(0, pending.length - MAX_MARKERS);
      scheduleFlush();
    } catch { /* timeline is decorative; never break logging */ }
  }

  window.Panels = window.Panels || {};
  window.Panels.renderTimeline = renderTimeline;
})();
