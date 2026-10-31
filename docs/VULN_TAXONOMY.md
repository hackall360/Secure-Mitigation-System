# Vulnerability Taxonomy (seed v0 — refined every forge cycle)

Machine-readable companion: `docs/vuln_taxonomy.json` (same classes, same ids).
These entries seed Green/Red/Blue prompt grounding. Each cycle must add a
subclass, refine a subclass with evidence, or prove a cross-language variant.

## T1 SQL string-concat sink (CWE-89)

- Subclass T1a: Python `sqlite3` f-string/`+` WHERE clause.
- Taint: HTTP query param → raw string → `db.execute("... " + raw)`.
- Red shape: `id=101` benign vs `id=101 OR 1=1`-family tautology; expect row-count change.
- Blue pattern: parameterize (`?` placeholder); never quote-wrap raw input.
- Priors: none yet.

## T2 Dynamic-expression eval sink (CWE-95)

- Subclass T2a: Python `eval(raw, {"__builtins__": {}}, {})` on query param.
- Taint: HTTP query param → `eval`.
- Red shape: arithmetic probe (`7*6` → `42`) proves code execution boundary.
- Blue pattern: strict allowlist (`isdecimal` → `int(raw)`); reject otherwise.
- Priors: none yet.

## T3 OS-command argument sink (CWE-78)

- Subclass T3a: PHP host argument into local diagnostic command.
- Taint: CLI/request arg → shell string → command run.
- Red shape: `;`/`&&`/backtick metacharacter reflection in command output.
- Blue pattern: exact allowlist of hosts / `escapeshellarg`; reject metachars.
- Priors: none yet.

## T4 Path traversal read (CWE-22)

- Subclass T4a (planned Cycle 1): Python file-serve endpoint joining unsanitized
  `name` param; `../` escapes docroot to a planted secret file.
- Taint: query param → `os.path.join(docroot, name)` → file read.
- Red shape: benign `name=welcome.txt` vs `name=../../secret.txt`.
- Blue pattern: resolve + constrain under docroot (`commonpath` check); reject escapes.

## T5 Logic-abuse gate → sink chain (CWE-285 + CWE-95)

- Subclass T5a: role-grant endpoint (Link A) gates dynamic query (Link B);
  single-step probe exits 1, chained single-payload probe exits 0.
- Proven by: `targets/node_chain_link` (Wave 14, gate 725).
- Red shape: unified payload fusing both weaknesses in ONE script (Wave-28 rule).
- Blue pattern: server-side authorization on Link B independent of client role claim.

## T6 Reflected XSS sink (CWE-79)

- Subclass T6a: stdlib SSTI-analog proven in Wild Crucible #3 (Wave 30).
- Red shape: marker reflection unescaped in response body.
- Blue pattern: contextual escaping + allowlist; verify marker neutralized.

## T7 Client-claimed role gate → SQLi sink chain (CWE-639 + CWE-89)

- Subclass T7a (proven forge Cycle 4, 2026-10-31): `/grant?role=` Link A sets
  a client-controlled role cookie; cookie-gated `/order?id=` Link B runs
  string-concat SQL. ONE unified Red script (grant admin, reuse cookie,
  tautology) exits 0 pre-patch; Blue parameterizes Link B (`?` placeholder)
  → Red exit 1, regressions 0.
- Taint: query param → cookie → string-concat `db.execute`.
- Red shape: `role=admin` grant + `id=1 OR 1=1` tautology → all rows leak.
- Blue pattern: parameterize Link B sink (tautology neutralizes to empty);
  server-side Link A authorization is follow-up hardening.
- Priors: red `4a9146b18ac3`, blue `b09cb5a8f3ee` (vault, forge-c4).
