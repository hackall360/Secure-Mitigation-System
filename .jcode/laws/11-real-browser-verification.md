# LAW 11 (mirror of repo-root LAWS.md — canonical source stays at root per LAW 0)

### LAW 11 — Real-browser verification (Firefox + Chrome), old-vs-new mapping

Unit tests and screenshots of a single state never prove a UI change works.
Whenever you change anything user-visible (Web UI markup, styles, motion,
controls, copy, event wiring), you MUST:

1. Drive a REAL browser — Firefox AND Chrome via the headless harness
   (`.jcode/tools/ui_scan.py --browser firefox|chrome`), not a DOM stub, not
   a static screenshot review.
2. Map old-vs-new: capture the affected flow on the BASE version (pre-change)
   and on YOUR version (post-change) — same fixture, same steps — and compare
   element-by-element: is every added control visible, reachable, and
   operable in both browsers?
3. Operate it, don't just load it: click the new control, run the flow it
   triggers, and confirm the downstream effect (WS event sent, state
   transition rendered, result displayed). Loading the page is not testing.
4. If anything added is not visible, not usable, or does not work correctly
   in either browser, stop and fix it in the same pass — never ship a
   verified-on-one-browser UI.
5. Keep the evidence: shot paths + offline E2E JSON (exit codes, diff,
   cleanup) in your report, per LAW 5 live-paths proof.

The existing offline Firefox E2E (`ui_scan.py node_query_sink --offline`)
is the floor, not the ceiling: extend it to the flow you touched (green
build, project mode, new widgets) and run the browser matrix.

