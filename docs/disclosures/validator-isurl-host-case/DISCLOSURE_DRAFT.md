# PRIVATE DISCLOSURE DRAFT — DO NOT SEND (human-only action)

Candidate: `validator-isurl-host-case` (validator.js `isURL` string host allow/block
case-sensitivity). Status: `READY_FOR_RESPONSIBLE_DISCLOSURE` (local evidence only).

## Summary
`isURL(url, {host_blacklist: [...]})` / `{host_whitelist: [...]}` compare the URL
host against string list entries case-SENSITIVELY (`checkHost`: strict `===` /
case-sensitive RegExp). DNS hostnames are case-INsensitive (RFC 1035 §3.1; WHATWG URL
lowercases hosts — verified `new URL('http://EVIL.COM/').host === 'evil.com'`). An
attacker who uppercases any letter of a listed host bypasses a lowercase string
blocklist entry (and is wrongly denied by a lowercase whitelist entry). Sibling
`isEmail` in the SAME package already lowercases (`lower_domain`) before `checkHost`;
`isURL` does not — inconsistent handling, one-line-class fix.

## Affected version / commit
- Package: `validator` (npm), version 13.15.35, MIT license.
- Pinned commit: `9ff342479591ca5a43cb30000195bcf55c1bbed9` (master @ 2026-09-11).
- File: `src/lib/isURL.js` lines ~248 (`host_whitelist`) and ~262 (`host_blacklist`).

## Local reproduction (air-gapped Docker, no network)
1. Clone at the pinned commit (local only).
2. Build the babel-free spliced harness (`phase1/splice_harness.mjs`: strips ESM,
   inlines `assertString/checkHost/includesString/merge/isFQDN/isIP`, no install).
3. Run the battery (`phase1/battery_validator_case.mjs`):
   - `isURL('http://EVIL.COM/', {host_blacklist: ['evil.com']})` → `true` (want `false`)
   - `isURL('http://Evil.Com/', {host_blacklist: ['evil.com']})` → `true` (want `false`)
   - `isURL('http://TRUSTED.COM/', {host_whitelist: ['trusted.com']})` → `false` (want `true`)
   - Regex `/evil\.com/i` control blocks (proves string-compare-specific).
   - Benign + dangerous-scheme behavior unchanged.
4. Sandbox proof: exit 0 (VULNERABLE, 3 bypasses) on the unpatched tree;
   exit 1 (blocked) with the patch; benign suite exit 0. Logs:
   `phase0/validator-repro-log.txt`, `phase0/validator-patched-log.txt`.
5. Full-matrix: 4 URL cases × 4 list shapes — only `RegExp/i` blocks uppercase.

## Impact
Any application gating server-side fetch, redirect, or embed on
`isURL(url, {host_blacklist: ['evil.com']})` (or allowlisting with lowercase
strings) is bypassed by requesting `http://EVIL.COM/` — DNS resolves identically.
Severity honestly SMALL in isolation (requires the app to rely on string host lists
for a security boundary AND an attacker who can influence the URL's case), but the
API sells these options exactly as allow/block guards. Class precedent: CVE-2026-18660
(Eclipse Jetty, same CWE-178 case-sensitive-host-list class, CVSS 8.8 High) shows the
shape is taken seriously elsewhere.

## Suggested patch (minimal, in `docs/disclosures/validator-isurl-host-case/isurl-host-case.patch`)
```diff
   if (options.host_whitelist) {
-    return checkHost(host, options.host_whitelist);
+    return checkHost(host.toLowerCase(), options.host_whitelist);
   }
-  if (options.host_blacklist && checkHost(host, options.host_blacklist)) {
+  if (options.host_blacklist && checkHost(host.toLowerCase(), options.host_blacklist)) {
     return false;
   }
```
Mirrors `isEmail`'s existing `lower_domain` handling. Verified: battery flips exit
0→1, benign suite stays exit 0, packaged `validators.test.js` semantics unaffected
(no babel here to run it — flagged as the one verification the maintainer should
repeat with `npm test`).

## Suggested mitigation (for users, until patched)
Use case-insensitive RegExp entries (`/evil\.com/i`) instead of plain strings in
`host_whitelist` / `host_blacklist`, or lowercase the host before calling `isURL`.

## Timeline placeholder (NOT initiated — human only)
- [ ] Human reviews this draft + evidence.
- [ ] Human decides channel (private security advisory / SECURITY.md contact).
- [ ] Human sends; record date sent here.
- [ ] Maintainer response date: —
- [ ] Fix release version: —
- [ ] Public disclosure date (post-fix + agreed window): —

## Evidence index
- Battery + harness: run-dir `phase1/` (`battery_validator_case.mjs`, `splice_harness.mjs`).
- Sandbox logs: run-dir `phase0/validator-repro-log.txt` (exit 0), `phase0/validator-patched-log.txt` (exit 1).
- Patch: `isurl-host-case.patch` (this directory).
- Novelty: `novelty_search.md` (this directory) — no NVD/OSV/GHSA/issue match; nearest
  neighbors CVE-2025-56200 (protocol delimiter, different mechanism) and issue #887
  (2018 default-case regression, different site) both distinguished.
