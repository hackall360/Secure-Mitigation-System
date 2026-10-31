# LAW 12 (mirror of repo-root LAWS.md — canonical source stays at root per LAW 0)

### LAW 12 — Semver discipline (0.major.minor; first value rarely moves)

Every user-facing change progresses the version. Format `0.major.minor`:

- The FIRST value (`0`) moves only for a public/API-breaking epoch change —
  almost never. It stays `0` through ordinary development.
- The SECOND value (major) increments for new capabilities, new controls,
  new modes, new endpoints, or any behavior addition a judge could notice.
- The THIRD value (minor) increments for fixes, polish, copy, motion, and
  hardening with no new capability.
- Exactly one bump per shipped change set, decided by its highest change:
  any new capability present → major; fixes/polish only → minor.
- The version lives in the release line (`main`) and MUST be consistent
  everywhere it appears (dashboard footer/header, `--version`, health
  payload, docs) — no drift between surfaces (LAW 8 parity applies to the
  version string too).
- Record the bump and its reason in the ship commit message
  (e.g. `Ship: ... (0.4.1 — minor: ...)`).

Current version at time of writing: `0.1` (see `static/index.html`,
health payload). The next shipped change set moves it — minor if
fixes/polish only, major if any gap-wiring capability lands.
