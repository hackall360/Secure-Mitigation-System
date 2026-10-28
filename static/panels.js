// panels.js - Scan-timeline markers fed by writeLine(team, msg) in app.js.
// CSP-safe: textContent and setAttribute only, no innerHTML, no eval, no inline handlers.
// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
'use strict';

(function () {
  const MAX_MARKERS = 100;
  const KNOWN_TEAMS = ['red', 'blue', 'research', 'green', 'system'];
  // Every scan opens with sandbox setup, so drop the previous run's markers
  // and keep the timeline oldest-to-newest for the current run.
  const SCAN_START = /creating an internal docker network|original-project baseline checks|project specification accepted|greenhouse is growing/i;

  function classify(team, message) {
    const t = String(message).toLowerCase();
    if (/exit 0|reachable|verified|check passed/.test(t)) return { glyph: '◆', kind: 'success', label: 'Boundary reached' };
    if (/exit 1|blocked|not confirmed|rejected|rolled back/.test(t)) return { glyph: '✕', kind: 'blocked', label: 'Blocked' };
    if (/probe|proving|attack|boundary/.test(t)) return team === 'red'
      ? { glyph: '➤', kind: 'attack', label: 'Attack attempted' }
      : { glyph: '➤', kind: 'attack', label: 'Probe event' };
    if (/patch|sanitiz|replacement/.test(t)) return { glyph: '✚', kind: 'patch', label: 'Patch' };
    if (/regression|baseline|normal-input|checks passed|starting a fresh target/.test(t)) return { glyph: '✔', kind: 'test', label: 'Test' };
    if (/greenhouse|growing|seedling|build|demo/.test(t)) return { glyph: '▣', kind: 'build', label: 'Build' };
    if (/research|intel|cve|osv|ghsa|epss|trivy|grype|scanner/.test(t)) return { glyph: '◉', kind: 'research', label: 'Research' };
    if (/cleanup|removed|snapshot|network/.test(t)) return { glyph: '○', kind: 'cleanup', label: 'Cleanup' };
    return { glyph: '·', kind: 'event', label: 'Event' };
  }

  function clearMarkers(timeline) {
    timeline.querySelectorAll('.timeline-marker').forEach((node) => node.remove());
  }

  // Every log event appends one marker: stage color dot + text glyph + short label.
  function renderTimeline(team, msg) {
    try {
      const timeline = document.getElementById('scan-timeline');
      if (!timeline) return;
      const known = KNOWN_TEAMS.includes(team) ? team : 'system';
      const text = String(msg);
      if (SCAN_START.test(text)) clearMarkers(timeline);
      const empty = timeline.querySelector('.empty');
      if (empty) empty.remove();
      const slot = classify(known, text);
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
      label.textContent = `${slot.label} · ${text.slice(0, 72)}${text.length > 72 ? '…' : ''}`;
      const stamp = document.createElement('time');
      stamp.textContent = new Date().toLocaleTimeString([], { hour12: false });
      marker.setAttribute('title', text.slice(0, 280));
      marker.append(dot, glyph, label, stamp);
      const pinned = timeline.scrollWidth - timeline.scrollLeft - timeline.clientWidth < 80;
      timeline.append(marker);
      const markers = timeline.querySelectorAll('.timeline-marker');
      let excess = markers.length - MAX_MARKERS;
      let i = 0;
      while (excess > 0 && i < markers.length) { markers[i].remove(); excess -= 1; i += 1; }
      if (pinned) timeline.scrollLeft = timeline.scrollWidth;
    } catch { /* timeline is decorative; never break logging */ }
  }

  window.Panels = window.Panels || {};
  window.Panels.renderTimeline = renderTimeline;
})();
