# WebUI Surface Notes — keyless smoke on :8797 (2026-11-02)

Server: throwaway `main.py --serve --port 8797`, no key. Untouched :8795.
Browser: headless Chrome 156 present → live console capture done (not static-only).

## Routes

| Route | Code | Verdict |
|---|---|---|
| `GET /` | 307 → `/web/index.html` | PASS |
| `/api/health` | 200, `inference_ready:false`, keyless ok | PASS |
| `/api/targets` | 200, 5 fixtures (node_query_sink, node_chain_link, php_command_sink, mysql_insecure_conf, binary_argv_echo) | PASS |
| `/web/*.html` (6/6: index, demo, demo-setup, prod-setup, console, visualizer) | 200 | PASS |
| index.html assets (43 js + 8 css + favicon) | all 200 | PASS |
| all-page asset sweep (313 refs) | 0 missing | PASS |
| `/web/assets/title-card.svg` | 200 | PASS |

## demo.html elements

- `#nar-toggle` present, `aria-pressed="false"` default — PASS
- `#demo-title-card` img present with `onerror="this.remove()"` — PASS (markup), see CSP note below

## WebSockets (exact same-origin `http://127.0.0.1:8797` required by design; `http://localhost` and `http://evil.com` correctly 403)

| Endpoint | Result |
|---|---|
| `/ws/demo` | PASS — snapshot frame (615c) |
| `/ws/combat/{target_key}` (e.g. `/ws/combat/node_query_sink`) | PASS — snapshot frame. NOTE: bare `/ws/combat` 403s — no such route, key is mandatory |
| `/ws/project` | PASS — snapshot frame |
| `/ws/binary` | PASS — snapshot frame |
| `/ws/system` | PASS — explicit `{"type":"invalid",...}` frame, then close 1008 (not silent 404) |

## Console errors (headless Chrome, 8s virtual-time budget per page)

- index, console, demo-setup, prod-setup, visualizer: CLEAN (no CONSOLE errors)
- **demo.html: 1 CSP violation — CRITICAL/FINDING:** inline `onerror` handler on `#demo-title-card` blocked by server CSP (`script-src 'self'`):
  `Executing inline event handler violates ... 'script-src 'self'' ... source: .../web/demo.html (0)`.
  Only inline handler in any page (`grep on*=`: single hit, demo.html:74).
  Impact is latent today (title-card.svg 200s, so onerror never fires) but the fallback is dead code under the shipped CSP — either move to `addEventListener` or add a hash. Server header comes from main.py:731.

## Parity gap (expected — confirmed)

No setup page surfaces cycles/intel/vault/ops/showcase as visible UI:
- demo-setup: target picker, event source, run settings only
- prod-setup: target, operational mode/run controls, proposed-controls details only
- `topo-showcase.js` is included as a script on pages but exposes no setup-page UI; console.html has an `Intel` filter button + hidden `#r-cycles` div (arena filter, not a setup control). No cycles/intel/vault/ops/showcase controls in either setup page.
