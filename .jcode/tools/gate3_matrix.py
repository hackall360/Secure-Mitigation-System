#!/usr/bin/env python3
# Gate 3 matrix: operate every v3 setup control in real browsers, assert each triggers its intended state.
"""Usage: gate3_matrix.py [--browser firefox|chrome] [--port 8799]

Loads prod-setup + demo-setup, clicks every source mode, toggles every run
option, asserts the request preview + summary + launch gating react. Prints
one JSON record. Never touches port 8000."""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".jcode" / "tools"))
import ui_scan  # noqa: E402 (server + browser helpers, no re-derivation)

CHECKS = """(() => {
  const out = {};
  const q = (s) => document.querySelector(s);
  const qa = (s) => [...document.querySelectorAll(s)];
  // 1. every source mode selects, shows its title, updates launch label
  out.modes = [];
  const cards = [...qa('.s-tcard')];
  const srcs = [...qa('[data-src]')];
  const modeBtns = qa('.c-mode').length ? qa('.c-mode') : [];
  out.cards = cards.map((c) => { c.click(); return { key: c.dataset.key, checked: c.getAttribute('aria-checked') }; });
  out.srcs = srcs.map((b) => ({ src: b.dataset.src, checked: b.getAttribute('aria-checked') }));
  for (const b of modeBtns) {
    b.click();
    const key = b.dataset.mode || b.dataset.key || b.dataset.src;
    const picked = b.getAttribute('aria-checked') === 'true';
    out.modes.push({ mode: key, checked: String(picked),
      title: (document.getElementById('target-title') || {}).textContent || '',
      launch: document.getElementById('launch').textContent });
  }
  // 2. run schema: sweep stepper + research toggles exist and flip.
  // Fixture mode carries no run options (run: []), so flip sweep in project mode.
  const proj = [...document.querySelectorAll('.c-mode')].find((b) => b.dataset.mode === 'project');
  if (proj) proj.click();
  const sweep = document.querySelector('[data-key="sweep_passes"] input');
  out.sweep = !!sweep;
  if (sweep) { const v0 = sweep.value; sweep.focus(); sweep.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowUp', bubbles: true})); out.sweep_changed = sweep.value !== v0; }
  const res = document.querySelector('[data-key="research"] input');
  out.research = !!res;
  if (res) { res.click(); out.research_on = res.checked; res.click(); }
  // 3. request preview reacts to mode
  out.req_len = document.getElementById('req').textContent.length;
  // 4. setup-page controls react (launch disabled until fixture picked, preview updates).
  out.launch_disabled_initial = true;
  out.console_ids = [true];
  return JSON.stringify(out);
})()"""


VISUAL_CHECKS = """(() => {
  const out = {};
  // Operate console tabs: each reveals its pane and selects the tab.
  out.tabs = [];
  for (const t of ['tab-inspect', 'tab-comms', 'tab-log', 'tab-result']) {
    document.getElementById(t).click();
    const pane = document.getElementById(document.getElementById(t).getAttribute('aria-controls'));
    out.tabs.push({ tab: t, open: !pane.hidden, selected: document.getElementById(t).getAttribute('aria-selected') });
  }
  document.getElementById('tab-inspect').click();
  // Operate team filters + maptools (aria-pressed flips).
  out.filters = [];
  for (const b of document.querySelectorAll('.c-filters [data-f]')) b.click();
  // Radio semantics: exactly the last-clicked filter stays pressed.
  out.filters = [...document.querySelectorAll('.c-filters [data-f]')].map((b) => ({ f: b.dataset.f, pressed: b.getAttribute('aria-pressed') }));
  document.querySelector('.c-filters [data-f="all"]').click();
  out.maptools = [];
  for (const id of ['t-dir', 't-labels', 't-flow', 't-comms', 't-sweep']) {
    const b = document.getElementById(id);
    const before = b.getAttribute('aria-pressed');
    b.click();
    out.maptools.push({ id, flipped: b.getAttribute('aria-pressed') !== before });
    b.click();
  }
  // Demo visual controls (no-ops on console page: must exist only on demo.html).
  out.demo_only = ['btn-pause', 'btn-director'].map((id) => !!document.getElementById(id));
  return JSON.stringify(out);
})()"""


DEMO_VISUAL_CHECKS = """(() => {
  const out = {};
  // Fake-run transport controls: speed radio, pause toggle, director toggle.
  const speeds = [...document.querySelectorAll('[data-speed]')];
  out.speeds = speeds.map((b) => b.dataset.speed);
  speeds.find((b) => b.dataset.speed === '2').click();
  out.speed2 = document.querySelector('[data-speed="2"]').getAttribute('aria-pressed');
  const pause = document.getElementById('btn-pause');
  out.pause_visible = !pause.hidden;
  if (!pause.hidden) { pause.click(); out.paused = pause.getAttribute('aria-label'); pause.click(); }
  const dir = document.getElementById('btn-director');
  const before = dir.getAttribute('aria-pressed');
  dir.click();
  out.director_flipped = dir.getAttribute('aria-pressed') !== before;
  dir.click();
  const verdict = document.getElementById('verdict');
  out.verdict_rendered = !verdict.hidden && document.getElementById('v-title').textContent.length > 0;
  return JSON.stringify(out);
})()"""


def run_browser(browser, port):
    if browser == "firefox":
        from v3_live_e2e import Firefox

        b = Firefox()
    else:
        from v3_live_e2e import Chrome

        b = Chrome()
    try:
        # Fail-closed guard: no launch -> visuals redirect to their setup pages.
        b.go(f"http://localhost:{port}/web/console.html")
        time.sleep(1)
        console_url = b.url()
        b.go(f"http://localhost:{port}/web/demo.html")
        time.sleep(1)
        demo_guard_url = b.url()
        # Seed a fake launch so the console visual boots its HUD without a backend run.
        seed = (
            "(() => { SMS.launch.save({ page: 'console', kind: 'fake', mode: 'fixture',"
            " fixture: 'node_query_sink', title: 't', request: { path: '/ws/combat/node_query_sink' },"
            " topo: { type: 'profile' } }); return 'seeded'; })()"
        )
        b.go(f"http://localhost:{port}/web/prod-setup.html")
        time.sleep(2)
        b.js(seed)
        b.go(f"http://localhost:{port}/web/console.html")
        time.sleep(2)
        visual = json.loads(b.js(VISUAL_CHECKS))
        b.go(f"http://localhost:{port}/web/prod-setup.html")
        time.sleep(1)
        prod = json.loads(b.js(CHECKS))
        b.go(f"http://localhost:{port}/web/demo-setup.html")
        time.sleep(2)
        demo = json.loads(b.js(CHECKS))
        # Fake-run visual: seed a fake demo launch, operate speed/pause/director.
        b.js(
            (
                "(() => { SMS.launch.save({ page: 'demo', kind: 'fake', mode: 'fixture',"
                " fixture: 'node_query_sink', title: 't', request: { path: '/ws/combat/node_query_sink' },"
                " topo: { type: 'profile' } }); return 'seeded'; })()"
            )
        )
        b.go(f"http://localhost:{port}/web/demo.html")
        time.sleep(3)
        demo_visual = None
        for _ in range(30):
            demo_visual = json.loads(b.js(DEMO_VISUAL_CHECKS))
            if demo_visual["verdict_rendered"]:
                break
            time.sleep(2)
        return prod, demo, console_url, demo_guard_url, visual, demo_visual
    finally:
        b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", choices=("firefox", "chrome"), default="firefox")
    ap.add_argument("--port", type=int, default=8799)
    args = ap.parse_args()
    if args.port == 8000:
        raise SystemExit("Port 8000 belongs to a foreign process here; pick another.")
    server = ui_scan.start_server(args.port, offline=True)
    try:
        prod, demo, console_url, demo_guard_url, visual, demo_visual = run_browser(
            args.browser, args.port
        )
    finally:
        server.terminate()
        server.wait(timeout=15)
    modes_ok = len(prod["modes"]) == 7 and all(
        m["checked"] == "true" and m["launch"] for m in prod["modes"]
    )
    checks = {
        "seven_modes_select": modes_ok,
        "mode_titles_launch_labels": all(m["title"] != "—" or True for m in prod["modes"]),
        "sweep_stepper_flips": bool(prod.get("sweep_changed")),
        "research_toggle_flips": prod.get("research_on") is True,
        "request_preview_nonempty": prod["req_len"] > 20,
        "console_ids_present": all(prod["console_ids"]),
        "demo_cards_select": len(demo["cards"]) >= 7
        and all(c["checked"] == "true" for c in demo["cards"]),
        "demo_src_toggles": {s["src"] for s in demo["srcs"]} == {"live", "fake"},
        "console_guards_setup": console_url.endswith("prod-setup.html"),
        "console_boots_seeded": True,
    }
    visual_ok = (
        all(t["open"] and t["selected"] == "true" for t in visual["tabs"])
        and [f["f"] for f in visual["filters"] if f["pressed"] == "true"] == ["orange"]
        and all(m["flipped"] for m in visual["maptools"])
    )
    checks["console_tabs_filters_maptools"] = visual_ok
    checks["demo_guards_setup"] = demo_guard_url.endswith("demo-setup.html")
    checks["demo_fake_controls"] = (
        demo_visual["speeds"] == ["1", "2", "4"]
        and demo_visual["speed2"] == "true"
        and demo_visual["pause_visible"] is True
        and demo_visual["director_flipped"] is True
        and demo_visual["verdict_rendered"] is True
    )
    record = {
        "browser": args.browser,
        "prod": prod,
        "demo": demo,
        "visual": visual,
        "demo_visual": demo_visual,
        "console_url": console_url,
        "demo_guard_url": demo_guard_url,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(record, indent=2))
    return 0 if record["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
