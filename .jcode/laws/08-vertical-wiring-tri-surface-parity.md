# LAW 8 (mirror of repo-root LAWS.md — canonical source stays at root per LAW 0)

### LAW 8 — Full-stack vertical wiring and tri-surface parity (no orphaned backend)

(A) No orphaned backend logic: a feature DOES NOT EXIST until it is wired
`Core Logic -> API/IPC/WebSocket Event Bus -> Web UI + TUI + CLI`. Backend
function + unit test alone is a fatal violation.
(B) Tri-surface parity: every capability, parameter, or telemetry output must
be synchronized across all three surfaces — Web UI (real controls, live state,
DOM rendering), TUI (keybindings/views, state-loop updates), CLI (flags,
help text, structured stdout/exit codes).
(C) Dead-control forbiddance: never leave an un-wired button, dummy toggle,
ignored flag, or unconnected event listener. Every control triggers a real
execution path and reflects real live state.
(D) Live streaming: multi-step Muse calls MUST emit granular progress,
model-active states, and intermediate results over the event bus/WebSocket,
rendered in real time on all three surfaces — never a silent black box.
(E) Build + runtime verification: full build with zero errors, exact payload
field-name match across backend/WebSocket/CLI/UI (no camelCase vs snake_case
drift), and an integration/smoke run through the interface boundary. Unit
tests alone never mark a task complete.

