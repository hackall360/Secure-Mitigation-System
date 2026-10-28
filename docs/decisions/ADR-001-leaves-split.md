# ADR 001: Split shared helpers into `sms_*` leaf modules

Date: 2026-10-28 · Status: accepted

## Context

`research.py`, `workflow.py`, `project_workflow.py`, scanner wrappers, and
agents each re-implemented the same small disciplines: paced HTTP with
backoff/caps, payload budgeting, text bounding, record shaping, scanner-field
picks, dict-level redaction, async emit plumbing.

## Decision

Extract one stdlib-only leaf per discipline (`sms_async`, `sms_budget`,
`sms_http`, `sms_records`, `sms_redact`, `sms_scan_parse`, `sms_text`).
Leaves import nothing from the app; callers import leaves. No behavior change,
only deduplication.

## Consequences

Pro: single home for each discipline, easier LAW 4 audit (redaction in one
place). Con: more files to index — see [reference/MODULES.md](../reference/MODULES.md).
