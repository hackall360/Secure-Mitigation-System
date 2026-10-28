# ADR 002: CLI / dashboard / TUI parity via `sms_cli.py` presenter

Date: 2026-10-28 · Status: accepted

## Context

`main.py --scan` printed ad-hoc formatting while the dashboard rendered the
same result fields (facts, usage, health) differently, and the TUI added a
third dialect. Drift risk: exit codes and fact labels disagreeing across
surfaces.

## Decision

`sms_cli.py` owns non-interactive presentation (ANSI colors, stderr spinner,
fact/usage/health tables); `tui.py` is a read-only curses view over the same
`main`/`workflow` results; the dashboard keeps its own DOM layer (`app.js` +
`panels.js` + `fx.js`) but shares field semantics. Tables carry facts and exit
codes only, never probe payloads (LAW 4).

## Consequences

Pro: one source for CLI facts; dashboard map in
[reference/DASHBOARD.md](../reference/DASHBOARD.md) pins hook semantics. Con:
dashboard strings still maintained separately — parity is by convention, not
by import.
