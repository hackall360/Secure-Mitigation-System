# Novelty search — validator.js isURL string host allow/block case-sensitivity (pinned 9ff34247, v13.15.35, MIT)

Date: 2026-10-31T18:21Z. All queries READ-ONLY (search APIs, advisory DBs, repo issues). No posts, no filings, no contact.

## Q1 — Web: validator.js isURL host whitelist/blacklist case bypass
- Query: `validator.js isURL host whitelist blacklist case sensitive bypass CVE`
- Date: 2026-10-31. Engine: DuckDuckGo (Jcode websearch).
- Results: (1) OpenCVE vendor pages (index, no case finding); (2) NVD CVE-2025-56200;
  (3) SentinelOne CVE-2025-56200 write-up; (4-5) GitLab/GitHub advisories GHSA-9965-vmph-33xx;
  (6-7) CVE-2026-18660 Eclipse Jetty case-sensitive host whitelist (DIFFERENT project —
  Jetty, not validator.js; same bug CLASS CWE-178/alias CWE-918 SSRF, High 8.8 — cited
  as class precedent, not a match); (8) ionix CVE-2026-18660 write-up.
- Verdict: NO match for validator.js host-list case-sensitivity.

## Q2 — OSV (api.osv.dev, keyless): advisories affecting validator@13.15.15
- Query: `POST /v1/query {package: {name: validator, ecosystem: npm}, version: 13.15.15}`
- Date: 2026-10-31. Result: 2 vulns —
  (a) GHSA-9965-vmph-33xx (CVE-2025-56200): `isURL` uses `://` as protocol delimiter
  while browsers use `:` → protocol/domain validation bypass → XSS/Open Redirect.
  Patched in 13.15.20. Our pinned commit 9ff34247 POSTDATES 13.15.20 and the audited
  `src/lib/isURL.js` already contains the regex protocol-match fix (`protocol_match`,
  auth-vs-protocol disambiguation, encoded-content check) — DIFFERENT mechanism from
  our host-list case finding (host allow/block options, not protocol parsing).
  (b) GHSA-vghf-hv5q-vc2g: `isLength` Unicode variation selectors (pre-13.15.22) —
  different function entirely.
- Verdict: NO match (neither record describes host allow/block case-sensitivity).

## Q3 — NVD: CVE-2025-56200 detail (GHSA page fetch)
- Fetched `https://github.com/advisories/GHSA-9965-vmph-33xx` 2026-10-31: Moderate 6.1,
  CWE-79, affected `< 13.15.20`, patched `13.15.20`, refs to gist PoCs + issues #2600/#2608
  + commit `cbef508`. All about the protocol-delimiter differential.
- Verdict: NO match for our shape.

## Q4 — GitHub repo issues (api.github.com, keyless, read-only)
- `search/issues repo:validatorjs/validator.js "host whitelist case"` → 3 hits, all
  unrelated (#2867 isEmail docs, #2536 release, #789 typings).
- `search/issues "isURL host case insensitive"` → 1 hit: **#887 (closed 2018-09-01)**
  `isUrl - Host and scheme should be case insensitive`: reporter asked for
  case-insensitive DEFAULT validation (`HTTPS://TEST.COM` rejected with default
  options). Maintainer `chriso`: "regression introduced by f9be99f", closed next day.
  That fix made DEFAULT scheme/host validation accept uppercase (verified live today:
  `isURL('HTTPS://WWW.YAHOO.COM')` → `true`). It did NOT touch `host_whitelist` /
  `host_blacklist` `checkHost` comparisons — our finding's exact site. #887 is a
  false-negative complaint about defaults, ours is a false-negative/positive about
  the allow/block options. Related but NOT the same finding.
- `search/issues "isURL uppercase host"` → 1 hit (#789 typings, unrelated).
  `search/issues "isURL bypass whitelist"` → 0 hits.
- Verdict: NO match; #887 logged as the closest related (and distinguished).

## Q5 — In-tree precedent + docs
- `src/lib/isEmail.js:98-104` lowercases (`lower_domain`) before `checkHost` for BOTH
  lists; `src/lib/isURL.js:248-264` does not lowercase anywhere (grep confirms zero
  `toLowerCase` on the host path). `THREAT_MODEL.md`/`SECURITY.md` consulted for a
  documented case policy — none found for host lists.
- Verdict: supports novelty (inconsistent handling inside the same package).

## Conclusion
No NVD/OSV/GitHub-Advisory record and no repo issue describes case-sensitive string
`host_whitelist`/`host_blacklist` comparison in `isURL` at or near this commit.
CVE-2025-56200 (protocol delimiter) and issue #887 (default-case regression, 2018)
are the two nearest neighbors and are BOTH distinguished on mechanism and site.
Level: `NOVELTY_CHECKED` (honest scope: keyless sources only — NVD web, OSV API,
GitHub Advisory mirror, repo issue search, in-tree docs; no commercial feeds).
