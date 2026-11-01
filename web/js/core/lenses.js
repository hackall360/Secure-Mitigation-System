// Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
// https://polyformproject.org/licenses/noncommercial/1.0.0
// SMS v3 · core/lenses.js — the four target LENSES and the two reading levels.
//
// A lens is "what kind of thing are we looking at". Each one changes how the map is drawn
// (engine/lens.js), what the rings and node kinds are called, and how the narrator tells
// the story (stream/narrator.js):
//
//   file    one source/config file      → a recipe card     (ruled page backdrop, page core)
//   repo    a project / repository      → a little city      (folder districts, hub core)
//   binary  a compiled program          → a sealed machine   (address ruler + section bands, chip core)
//   system  a cloned/snapshotted system → a house with doors (perimeter wall with doors, house core)
//
// Every name exists twice: `simple` (anyone, a five-year-old included) and `expert`
// (security people). Pages show one or both — see SMS.explain in ui/explainer.js.
//
// Add a lens: add an entry to LENSES (+ KIND overrides), teach of() to detect it,
// add its backdrop/core in engine/lens.js and its sentences in stream/narrator.js.
'use strict';
(() => {
  const SMS = (window.SMS = window.SMS || {});

  const LENSES = {
    file: {
      key: 'file', label: 'Single file', short: 'FILE', accent: '#2dd4bf',
      metaphor: 'A recipe card',
      simple: 'One page of instructions. We follow each ingredient from where it comes in to where it gets used.',
      expert: 'Intra-file taint analysis: sources → functions → sinks, with line spans.',
      rings: [{ simple: 'Parts of the page', expert: 'REGIONS' }, { simple: 'Steps', expert: 'FUNCTIONS · INPUTS' }, { simple: 'Details', expert: 'STATEMENTS · SINKS' }, { simple: 'Fine print', expert: 'EXPRESSIONS' }],
      words: { target: 'this file', thing: 'page', entry: 'where outside text comes in', sink: 'the risky line', copy: 'a photocopy of the page' }
    },
    repo: {
      key: 'repo', label: 'Project / repo', short: 'REPO', accent: '#22d3ee',
      metaphor: 'A little city',
      simple: 'Folders are neighbourhoods, files are buildings, and the roads between them are how code calls other code.',
      expert: 'Repository graph: directories, modules, routes, dependency manifest and cross-file calls.',
      rings: [{ simple: 'Neighbourhoods', expert: 'TOP-LEVEL DIRS' }, { simple: 'Buildings', expert: 'FILES · MODULES' }, { simple: 'Rooms', expert: 'SYMBOLS · ROUTES' }, { simple: 'Furniture', expert: 'CALL SITES' }],
      words: { target: 'this project', thing: 'city', entry: 'the front door', sink: 'the weak building', copy: 'a copy of the whole city' }
    },
    binary: {
      key: 'binary', label: 'Compiled binary', short: 'BIN', accent: '#e2e8f0',
      metaphor: 'A sealed machine',
      simple: "We can't read its recipe, so we look at its parts: gears (functions), plugs to the outside (imports) and labels stamped inside (strings).",
      expert: 'ELF / PE / Mach-O: sections, symbols, PLT imports and .rodata strings; dynamic probes through argv / stdin.',
      rings: [{ simple: 'Compartments', expert: 'SECTIONS' }, { simple: 'Parts', expert: 'SYMBOLS · IMPORTS' }, { simple: 'Pieces', expert: 'STRINGS · GADGETS' }, { simple: 'Bits', expert: 'INSTRUCTIONS' }],
      words: { target: 'this program', thing: 'machine', entry: 'the input slot', sink: 'the risky part', copy: 'a copy of the machine in a sealed box' }
    },
    system: {
      key: 'system', label: 'System snapshot', short: 'SYS', accent: '#f0abfc',
      metaphor: 'A house with doors',
      simple: 'We make a perfect copy of the house. The wall has doors (open ports), the rooms are computers, and the safe holds the data. We only ever test the copy.',
      expert: 'Cloned environment: hosts / containers, listening services, exposed ports, config and data stores behind a network perimeter.',
      rings: [{ simple: 'Rooms', expert: 'HOSTS · CONTAINERS' }, { simple: 'Doors & machines', expert: 'SERVICES · PORTS' }, { simple: 'Valuables', expert: 'DATA · CONFIG · SECRETS' }, { simple: 'Small stuff', expert: 'KEYS · TABLES' }],
      words: { target: 'the copy of this system', thing: 'house', entry: 'the open door', sink: 'the weak spot', copy: 'a perfect copy of the house' }
    }
  };
  const ORDER = ['file', 'repo', 'binary', 'system'];

  // Node kinds, in both languages. Lens entries override the generic ones.
  const KINDS = {
    core:      { simple: 'The thing we are checking', expert: 'Target root' },
    subsystem: { simple: 'A big part', expert: 'Subsystem' },
    module:    { simple: 'A piece of code', expert: 'Module' },
    file:      { simple: 'A file', expert: 'Source file' },
    function:  { simple: 'A step it follows', expert: 'Function / symbol' },
    endpoint:  { simple: 'A way in', expert: 'Entry point · taint source' },
    sink:      { simple: 'A danger spot', expert: 'Sink · dangerous call' },
    data:      { simple: 'Something valuable', expert: 'Data store / asset' },
    infra:     { simple: 'The sealed test room', expert: 'Sandbox infrastructure' },
    cve:       { simple: 'A known problem', expert: 'Advisory · CVE / GHSA' },
    section:   { simple: 'A compartment', expert: 'Binary section' },
    import:    { simple: 'A plug to the outside', expert: 'Imported symbol · PLT / GOT' },
    string:    { simple: 'A label stamped inside', expert: 'String constant · .rodata' },
    dir:       { simple: 'A neighbourhood (folder)', expert: 'Directory' },
    host:      { simple: 'A room (one computer)', expert: 'Host / container' },
    service:   { simple: 'A machine in the room', expert: 'Listening service / process' },
    port:      { simple: 'A door', expert: 'Network port' },
    config:    { simple: 'A rule sheet', expert: 'Configuration' },
    secret:    { simple: 'A key', expert: 'Secret / credential' }
  };
  const LENS_KINDS = {
    file: { function: { simple: 'A step (function)' }, endpoint: { simple: 'Where outside text comes in' }, sink: { simple: 'Where it gets used dangerously' }, subsystem: { simple: 'A part of the page' } },
    repo: { subsystem: { simple: 'A neighbourhood' }, file: { simple: 'A building (file)' }, function: { simple: 'A room (function)' }, endpoint: { simple: 'A front door (route)' }, import: { simple: 'A road to another town (dependency)' }, sink: { simple: 'A weak wall' } },
    binary: { function: { simple: 'A gear (function)' }, endpoint: { simple: 'A slot you can feed (input)' }, sink: { simple: 'A risky plug (dangerous import)' }, subsystem: { simple: 'A compartment' } },
    system: { endpoint: { simple: 'A door (open port)' }, data: { simple: 'The safe (data)' }, function: { simple: 'A worker (process)' }, subsystem: { simple: 'A wing of the house' } }
  };

  // Lens of a topology. Builders set topo.lens; this is the fallback for older/server maps.
  function of(topo) {
    if (!topo) return 'file';
    if (topo.lens && LENSES[topo.lens]) return topo.lens;
    const p = String(topo.profile || '');
    if (/^binary|_elf$/.test(p) || /ELF|PE|Mach-O/.test(String((topo.root || {}).sub || ''))) return 'binary';
    if (/^system/.test(p)) return 'system';
    if (/^repo/.test(p) || topo.dynamic) return 'repo';
    return 'file';
  }

  function get(key) { return LENSES[key] || LENSES.file; }

  function kind(lensKey, k) {
    const base = KINDS[k] || { simple: k, expert: k };
    const o = (LENS_KINDS[lensKey] || {})[k] || {};
    return { simple: o.simple || base.simple, expert: o.expert || base.expert };
  }

  function ring(lensKey, depth) {
    const r = get(lensKey).rings[depth - 1];
    return r || { simple: `Ring ${depth}`, expert: `R${depth}` };
  }

  SMS.lenses = { LENSES, ORDER, KINDS, of, get, kind, ring };
})();
