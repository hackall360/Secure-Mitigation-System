# Wave 5 additions

Follow-on to [WAVE2.md](WAVE2.md): the GHSA `cve_id` lookup fix, the KEV
signal with the 16MB cap discipline, the reachability likelihood tie-break
band invariant, the explicit `differential_passed` normal-contract gate,
and the fast-lane actionability tiering key.

## GHSA `cve_id` lookup fix (`research.py:207`, wired in `research.py:425`)

`ghsa_lookup_by_cve(cve_id, limit=5)` queries the GitHub Advisory DB by CVE
id (`?cve_id=`) instead of abusing the package search path. `cve_records`
previously called `ghsa_search(cve)` and filtered on id match
(`research.py:425` before); it now calls `ghsa_lookup_by_cve(cve)` with the
same `[:2]` id-match filter, so advisories whose package slug does not
contain the CVE id are still found.

Carried fields per advisory (`research.py:207-271`):

- EPSS dict passthrough into `extra.epss_percentage`/`epss_percentile`.
- CVSS severities with v4 preferred over v3 into `cvss` plus
  `extra.cvss_version`/`cvss_vector` (vector string appended to the summary
  in brackets, bounded to 128 chars).
- `_ghsa_first_patched_version` (`research.py:187`): reads top-level
  `first_patched_version` (str or `{identifier}` dict), else nested under
  `vulnerabilities[]`; returns `""` when absent.

Fail-closed parsing: invalid CVE id shape returns `[]`; non-list payloads,
non-dict advisories, and transport `RuntimeError` all degrade to `[]`, never
raise.

## KEV signal + 16MB cap discipline (`research.py:341-421`)

`kev_lookup(cve_id)` (`research.py:349`) flags CISA known-exploited CVEs:

- fetches `KEV_CATALOG_URL` (`research.py:341`) and linear-scans
  `vulnerabilities[]` for a `cveID` match; returns a `source="kev"` record
  with `extra.kev_listed=True`, `due_date`, and `ransomware` campaign flag.
- `cve_records` fans out to it per id alongside CIRCL/OSV/EPSS/GHSA
  (`research.py:421`); failures degrade to fewer records via the surrounding
  `try/except`, never raise.

Cap discipline: the KEV catalog exceeds the default 1 MiB fetch cap (1.8 MiB
live), so the call passes `max_bytes=MAX_MAX_BYTES` (16 MiB ceiling,
`research.py:357`). A further-grown catalog degrades to `None` via
`RuntimeError`, never raised.

## Reachability tie-break band invariant (`deep_scan.py:290-370`)

`reachability_score` keeps its WAVE2 base (+10 record identity, +40 fixed
versions, +40 sink adjacency) and adds two likelihood tie-breaks
(`deep_scan.py:357-370`):

- +5 when `summary.get("kev_listed") is True` (`KEV listed: known
  exploited (+5)`).
- +5 when `float(summary.get("epss_percentile", 0)) >= 0.9`, with
  `TypeError`/`ValueError` falling back to 0.0.

Band invariant: when a record has neither fixed versions nor sink adjacency
(`not has_fix and not has_sink`), the score is clamped to at most 30
(`score = min(score, 30)`, `deep_scan.py:369-370`) before the final
`min(score, 100)`. Likelihood signals can order records within a band but
never promote a fix-less, sink-less record above 30. Evidence names each
signal, presence and absence alike, so a band-capped score still explains
which grounding was missing.

## Explicit `differential_passed` field (`project_workflow.py:127,744`)

`CycleEvidence.differential_passed: bool = False`
(`project_workflow.py:127`) records the normal-contract differential gate
as data instead of an implicit conjunction:

- `differential_passed(baseline_exit, patched_exit)`
  (`project_workflow.py:744-754`) is a pure function over recorded exits:
  `True` only when both are exactly 0. `None` (evidence not observed) fails
  closed to `False`. No Docker runs.
- `differential_class(exit_code)` (`project_workflow.py:755`) labels one
  exit for audit records (`pass`/`fail`/`missing`).
- `execute_project_workflow` sets `evidence.differential_passed` from the
  baseline and patched regression exits (`project_workflow.py:1164`) and
  conjoins it into the retain verdict (`project_workflow.py:1221`). The
  gate is equivalent to the already-required baseline-exit-0 raise plus
  patched-exit-0 check, so it changes no verdict — it only records the
  check explicitly on the evidence.

## Fast-lane tiering key (`cve_workflow.py:234-243`)

WAVE2 fast lane sorted vulnerabilities by id for deterministic disclosure.
Wave 5 replaces the id sort with SSVC-style actionability tiering
(`cve_workflow.py:234-243`):

```python
(-(s.get("reach_score") or 0), not bool(s.get("fixed_versions")), s.get("id") or "")
```

Reachable first, then fix-available, then id as the final deterministic
tie-break. The rest of the fast lane is unchanged: forces
`include_deep_assessment=False` and `include_nvd=False`, caps
`max_osv_details` to `min(given, 10)`, prefixes `Fast lane: `.
