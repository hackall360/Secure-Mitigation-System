# LAW 9 (mirror of repo-root LAWS.md — canonical source stays at root per LAW 0)

### LAW 9 — Red-green-refactor: failing test first, no cheating, no mocks of the unit

(A) Failing test first: write/update the automated test defining the desired
behavior (including the API/interface contract) BEFORE implementation; run it
and verify it FAILS for the expected functional reason (not syntax/import). A
test that passes pre-change is invalid — rewrite it.
(B) Test immutability: never weaken, delete, comment out, skip, or loosen
assertions in the red test or any pre-existing test to get green. Change
implementation to satisfy tests, never tests to forgive broken code.
(C) Anti-mocking/anti-tautology: never mock the unit under test, mock
internal business logic, or hardcode `if input == "test": return expected`.
Exercise real execution paths, real transforms, real routers. Mocks only at
true third-party boundaries and must validate outgoing payload schemas.
(D) Falsifiable assertions: never `assert result is not None` / `status ==
200` where exact state, schema, and payload fields can be asserted. Assert
BOTH the exact positive transformation AND the absence of side effects.

LAW 9 restates and hardens LAW 5's "test fails without the fix, passes with
it": keep both, obey the stricter reading.

