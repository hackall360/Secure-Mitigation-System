# OMNI-INGEST Closed-Loop Guidance Matrix (FINAL pre-submission verification)

Target: all subsystems at zero delta. Gate = green suite + live proof.
Note: canonical laws live at repo-root `LAWS.md` (not `.jcode/laws/`, which
does not exist); all LAW references below cite the root file.

| ID | Subsystem | S_current | Delta | Action vector | Gate |
|----|-----------|-----------|-------|---------------|------|
| A | Repo purity & secrets | VERIFIED: .env gitignored, no live sk-ant values tracked, example.env sanitized (empty key), PolyForm headers on all touched files, README free of .jcode/debug | ZERO | none — evidence above | [x] |
| B | Infra & air-gap | VERIFIED: init-images clean, 5-image matrix present (polyglot 40min old), execution paths network_mode=none + internal=True isolated networks, provisioner LAW-2-by-construction documented (no shared live container) | ZERO (provisioner E2E fetch not yet exercised against a live network — fetch steps degrade to notes by design) | none blocking — init-images log above | [x] |
| C | Cross-surface parity | VERIFIED: 5-pass verdicts identical across WS/CLI/TUI/MCP (parity pins); WebGL palette FIXED — Bloodsniffer + Blacklight entries added (were falling back to Warlord), roster pin extended to 7 red | ZERO | palette.js + deep_scan roster pin | [x] |
| D | Zero-regression + intake E2E | VERIFIED: C repo -> eco=c/tools=(make,gcc)/argv=[make]; Rust repo -> eco=rust/argv=[cargo test]; live gcc segfault proof (exit 139), rustc/go/C all execute in polyglot; full gate re-run below | ZERO | live proofs above + gate | [x] |
