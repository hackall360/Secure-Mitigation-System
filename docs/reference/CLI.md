# CLI reference

Generated from `main.py` argparse (`main()`), 2026-10-28. Run
`python3 main.py --help` for the live text.

## Commands (mutually exclusive, one required)

| Flag | Help |
|---|---|
| `--init-images` | Build the two base images (requires Docker) |
| `--rebuild-images` | Force a fresh rebuild of both base images |
| `--docker-status` | Report Docker daemon and image readiness |
| `--cleanup` | Remove leftover session resources |
| `--serve` | Serve the local dashboard |
| `--scan {fixture}` | Scan one bundled fixture |
| `--project PATH` | Scan a local source directory without modifying it |
| `--list-targets` | List bundled fixtures without Docker or a key |
| `--health` | Report readiness (models, profiles, Docker) without Docker or a key |
| `--ai-demo` | AI-built demo mode: Muse designs a novel vulnerable demo, then red/blue exercise it in Docker |

## Modifiers

| Flag | Default | Help |
|---|---|---|
| `--port` | 8000 | Dashboard port |
| `--image` | — | Already-loaded runtime image with offline dependencies |
| `--command` | — | Target argv as JSON, e.g. `["python3", "app.py"]` |
| `--test-command` | — | Trusted regression argv as JSON |
| `--contract` | "" | Expected behavior and sanitization-only patch constraints |
| `--scan-profile {profile,c custom}` | custom | Project scan intensity, independent of `--profile` models |
| `--cycles N` | — | Explicit custom red/blue cycles, 1 to 20 (legacy default: 1) |
| `--red-agents N` | 5 | Red agent team size, 1 to 12 |
| `--blue-agents N` | 5 | Blue agent team size, 1 to 12 |
| `--context-budget N` | 32768 | Bounded per-call source context budget |
| `--allow-remote-inference` | off | Consent to send source/evidence to hosted Muse endpoint |
| `--profile {economy,balanced,quality,custom}` | — | Model profile for `--scan` (default: configured models) |
| `--cve-scan` | off | Deep static+CVE scan (OSV lookup) instead of probe/patch verification |
| `--deep-assessment` | off | Muse triage of static signals and CVE context |
| `--offline-cve` | off | Skip OSV network lookup; static signals only |
| `--fast-lane` | off | CVE disclosure fast lane: static + OSV only, deterministic order, no Muse/NVD (requires `--project` with `--cve-scan`) |
| `--build-brief TEXT` | "" | What the AI demo should build (bounded to 500 chars) |
| `--vulns TEXT` | "" | Requested demo flaws: CVE IDs, named types, or free text |
| `--intel-theme TEXT` | input validation SQL injection XSS deserialization | Threat-intel themes for AI demo generation |
| `--intel-offline` | off | Generate AI demo without live NVD lookup |
| `--demo-size {small,standard}` | standard | Greenhouse demo size: small (fewer routes) or standard (full set) |
| `--flaw-count N` | — | Bound the requested demo flaws to 1..8 (default: keep them all; clamps; ai-demo only) |
| `--demo-seed N` | — | Variation nonce for AI demo generation (ai-demo only) |
| `--config PATH` | — | TOML or JSON file with an `[sms]` table of CLI defaults |

CVE JSON output now carries `reach_score` + `reach_evidence` per vulnerability.

Related: [MODULES.md](MODULES.md) (`sms_cli.py` presenter), [guides/PROJECTS.md](../guides/PROJECTS.md) (project intake).
