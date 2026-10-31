# LAW 10 (mirror of repo-root LAWS.md — canonical source stays at root per LAW 0)

### LAW 10 — Zero regression, blast radius, and swarm hygiene

(A) Baseline verification: run the suite + build/typecheck BEFORE modifying
anything. Never stack changes on a broken state without isolating and
reporting the pre-existing failure.
(B) Pre-flight call-graph + payload audit: before changing any signature,
structure, route, event payload, or CLI arg, search backend + Web UI + TUI +
CLI + tests for every caller/consumer, list the blast radius, update all call
sites atomically.
(C) Contract preservation: internal refactors keep public interfaces, return
types, event schemas, flags, and UI state contracts 100% backward-compatible
unless explicitly instructed otherwise.
(D) Chesterton's fence: never delete/simplify non-obvious logic, guards,
timeouts, or CSS because it looks redundant — trace callers + git history,
preserve the protection.
(E) Atomic verification loops: after every implementation step, run the
failing test (Red→Green) then the full suite + build + lint for affected
modules. On any regression, halt new work and fix it first.
(F) Empirical verification: never guess library/SDK signatures from memory;
check lockfiles (`pyproject.toml`, installed versions) first. No new
dependencies when stdlib/existing packages suffice.
(G) Anti-duplication: search before creating — extend canonical modules
rather than parallel duplicates.
(H) Root-cause diagnosis: read the full trace, state the cause in one
sentence, apply a targeted fix. Two failed attempts on one error → stop,
re-read the full flow, reassess.
(I) Bounded execution + teardown: every loop, listener, I/O call, and
subprocess gets a timeout, cancellation path, and deterministic teardown.
(J) Explicit failure: no empty excepts, no swallowed fetch/console errors,
no silent null fallbacks. Surface errors with actionable context on Web UI,
TUI, AND CLI.
(K) Zero omission: no partial files, no `// rest here` / `TODO: wire later`.
Every touched file complete, valid, executable.
(L) Minimal surgical diffs + adversarial self-audit: no cosmetic churn on
untouched lines; `git diff` every line as a hostile reviewer — fully wired,
tests failed-then-passed, zero regressions, zero dead code, zero debug
artifacts.

