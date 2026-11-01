# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Canonical feature-tag registry + per-module semver map (audit hooks only).

Post-refactor home: `library/tags.py`. Ported 2026-10-31 from the Oct-28
`feature/work-tags` tree (root `feature_tags.py`, commit da9f4fd), which
never shipped — no compat shim is kept. Backend paths were rewritten from
bare leaf names to their `library/<core|services|workflows|intel|shared>/`
homes per docs/REFACTOR_PLAN.md; `main.py`, `tui.py`, `sms_cli.py` and
`static/app.js` backends are unchanged (those paths were not moved).

PART A — every backend capability gets a machine-checkable tag:
tag-id -> {surfaces, backend symbol, DOM control id / CLI flag / TUI binding}.
`check_registry` walks the registry and asserts each tag has a live binding
on its claimed surface(s); it never renders or changes behavior.

Tag-id conventions: kebab-case capability names. `surfaces` is a subset of
{"cli", "web", "tui", "api"}. `backend` is "module:Symbol" (the canonical
definition site). `ui` is the DOM id the control/panel carries (and the
`data-feature` value in static/index.html). `cli` is the exact argparse flag
or None. `tui` is the exact key/action binding or None. A None binding means
the surface has no expression for that capability (recorded gaps from
GAP_CLI/GAP_API/GAP_MODES — still auditable, not silently dropped).

PART B — per-module semver: every modularized leaf plus the research,
demo-gen, and workflow majors carries its own `__version__` (`0.x.y`);
MODULE_VERSIONS mirrors them here. Bump rule mirrors LAW 12:
capability -> module minor, fix -> module patch. Top-level app version
stays LAW 12 (see TAGS_NOTES.md for the drafted law text).
"""

from __future__ import annotations

from pathlib import Path

ENTRY_KEYS = ("surfaces", "backend", "ui", "cli", "tui")


def _load_module(dotted: str):
    """Import through the canonical library package, never the shim.

    `modules.*` re-exports the real subpackage object, but a submodule
    imported as `modules.x.y` still executes a SECOND copy of the file.
    Tests that assert `is` identity of re-exported symbols (e.g. the
    sms_http back-compat aliases) must resolve both sides through one
    package or the copies diverge.
    """
    import importlib

    return importlib.import_module(dotted)


__version__ = "0.1.0"

FEATURE_TAGS: dict[str, dict[str, object]] = {
    # --- CLI lifecycle / server ops (GAP_CLI 1-5) ---
    "init-images": {
        "surfaces": ["cli", "api"],
        "backend": "library/core/docker_manager.py:ensure_base_images",
        "ui": None,
        "cli": "--init-images",
        "tui": None,
    },
    "rebuild-images": {
        "surfaces": ["cli", "api"],
        "backend": "library/core/docker_manager.py:build_base_images",
        "ui": None,
        "cli": "--rebuild-images",
        "tui": None,
    },
    "docker-status": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/core/docker_manager.py:docker_status",
        "ui": "chip-docker",
        "cli": "--docker-status",
        "tui": None,
    },
    "cleanup-stale": {
        "surfaces": ["cli", "api"],
        "backend": "library/core/docker_manager.py:remove_stale_resources",
        "ui": None,
        "cli": "--cleanup",
        "tui": None,
    },
    "quickstart": {
        "surfaces": ["api"],
        "backend": ".jcode/tools/dev.py:quickstart",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "serve-dashboard": {
        "surfaces": ["cli", "api"],
        "backend": "main.py:index",
        "ui": None,
        "cli": "--serve",
        "tui": None,
    },
    "tui-launch": {
        "surfaces": ["cli", "tui"],
        "backend": "tui.py:main",
        "ui": None,
        "cli": "--tui",
        "tui": "run_plain",
    },
    "server-port": {
        "surfaces": ["cli"],
        "backend": "main.py:main",
        "ui": None,
        "cli": "--port",
        "tui": None,
    },
    # --- Fixture scan (fixture path) ---
    "scan-fixture": {
        "surfaces": ["cli", "web", "tui", "api"],
        "backend": "library/workflows/workflow.py:execute_purple_workflow",
        "ui": "run-btn",
        "cli": "--scan",
        "tui": "start",
    },
    "stop-scan": {
        "surfaces": ["web", "tui", "api"],
        "backend": "main.py:run_socket",
        "ui": "stop-btn",
        "cli": None,
        "tui": "stop",
    },
    "ws-combat": {
        "surfaces": ["web", "api"],
        "backend": "main.py:combat",
        "ui": "target-list",
        "cli": None,
        "tui": None,
    },
    "fixture-picker": {
        "surfaces": ["web", "tui"],
        "backend": "library/core/registry.py:Target",
        "ui": "target-select",
        "cli": None,
        "tui": "select:0",
    },
    "list-targets": {
        "surfaces": ["cli", "web", "api"],
        "backend": "main.py:list_targets",
        "ui": "target-list",
        "cli": "--list-targets",
        "tui": None,
    },
    "health-report": {
        "surfaces": ["cli", "web", "api"],
        "backend": "main.py:health",
        "ui": "chip-key",
        "cli": "--health",
        "tui": None,
    },
    "orchestrator-chip": {
        "surfaces": ["web", "api"],
        "backend": "main.py:health",
        "ui": "chip-server",
        "cli": None,
        "tui": None,
    },
    "api-key-chip": {
        "surfaces": ["web", "api"],
        "backend": "main.py:health",
        "ui": "chip-key",
        "cli": None,
        "tui": None,
    },
    "mode-switch": {
        "surfaces": ["web"],
        "backend": "static/app.js:setSourceMode",
        "ui": "mode-demo",
        "cli": None,
        "tui": None,
    },
    "mode-demo-build": {
        "surfaces": ["web", "api"],
        "backend": "main.py:run_demo_build",
        "ui": "mode-demo-build",
        "cli": None,
        "tui": None,
    },
    "mode-project": {
        "surfaces": ["web", "api"],
        "backend": "main.py:project_combat",
        "ui": "mode-project",
        "cli": None,
        "tui": None,
    },
    # --- Project scan fields (ProjectSpec, all 11 wired) ---
    "project-path": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/services/projects.py:ProjectSpec",
        "ui": "project-path",
        "cli": "--project",
        "tui": None,
    },
    "project-image": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/services/projects.py:ProjectSpec",
        "ui": "project-image",
        "cli": "--image",
        "tui": None,
    },
    "project-command": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/services/projects.py:ProjectSpec",
        "ui": "project-command",
        "cli": "--command",
        "tui": None,
    },
    "project-test-command": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/services/projects.py:ProjectSpec",
        "ui": "project-test-command",
        "cli": "--test-command",
        "tui": None,
    },
    "project-contract": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/services/projects.py:ProjectSpec",
        "ui": "project-contract",
        "cli": "--contract",
        "tui": None,
    },
    "scan-intensity": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/core/scan_profiles.py:SCAN_PROFILES",
        "ui": "project-scan-profile",
        "cli": "--scan-profile",
        "tui": None,
    },
    "project-cycles": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/services/projects.py:ProjectSpec",
        "ui": "project-cycles",
        "cli": "--cycles",
        "tui": None,
    },
    "red-team-size": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/services/projects.py:ProjectSpec",
        "ui": "project-red-agents",
        "cli": "--red-agents",
        "tui": None,
    },
    "blue-team-size": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/services/projects.py:ProjectSpec",
        "ui": "project-blue-agents",
        "cli": "--blue-agents",
        "tui": None,
    },
    "context-budget": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/services/projects.py:ProjectSpec",
        "ui": "project-budget",
        "cli": "--context-budget",
        "tui": None,
    },
    "allow-remote": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/services/projects.py:ProjectSpec",
        "ui": "allow-remote",
        "cli": "--allow-remote-inference",
        "tui": None,
    },
    "ws-project": {
        "surfaces": ["web", "api"],
        "backend": "main.py:project_combat",
        "ui": "project-form",
        "cli": None,
        "tui": None,
    },
    "project-workflow": {
        "surfaces": ["cli", "api"],
        "backend": "library/workflows/project_workflow.py:execute_project_workflow",
        "ui": None,
        "cli": "--project",
        "tui": None,
    },
    "project-errors": {
        "surfaces": ["web"],
        "backend": "static/app.js:projectSpec",
        "ui": "project-errors",
        "cli": None,
        "tui": None,
    },
    # --- Green build (demo-gen intent + WS demo) ---
    "demo-build-brief": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/services/demo_gen.py:parse_build_intent",
        "ui": "demo-build-brief",
        "cli": "--build-brief",
        "tui": None,
    },
    "demo-vulns": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/services/demo_gen.py:parse_build_intent",
        "ui": "demo-vulns",
        "cli": "--vulns",
        "tui": None,
    },
    "demo-theme": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/services/demo_gen.py:parse_build_intent",
        "ui": "demo-theme",
        "cli": "--intel-theme",
        "tui": None,
    },
    "demo-generate": {
        "surfaces": ["cli", "api"],
        "backend": "library/services/demo_gen.py:generate_demo_project",
        "ui": None,
        "cli": "--ai-demo",
        "tui": None,
    },
    "demo-materialize": {
        "surfaces": ["api"],
        "backend": "library/services/demo_gen.py:materialize_demo_project",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "ws-demo": {
        "surfaces": ["web", "api"],
        "backend": "main.py:run_demo_build",
        "ui": "demo-build-config",
        "cli": None,
        "tui": None,
    },
    "demo-intel-offline": {
        "surfaces": ["cli", "api"],
        "backend": "main.py:run_demo_build",
        "ui": None,
        "cli": "--intel-offline",
        "tui": None,
    },
    "green-build-run": {
        "surfaces": ["web", "api"],
        "backend": "main.py:run_demo_build",
        "ui": "run-btn",
        "cli": None,
        "tui": None,
    },
    # --- GAP_MODES M1-M8 (missing widgets; backend-first-half exists) ---
    "demo-scan-profile": {
        "surfaces": ["cli"],
        "backend": "main.py:ai_demo_runner",
        "ui": None,
        "cli": "--scan-profile",
        "tui": None,
    },
    "demo-red-agents": {
        "surfaces": ["cli"],
        "backend": "main.py:ai_demo_runner",
        "ui": None,
        "cli": "--red-agents",
        "tui": None,
    },
    "demo-blue-agents": {
        "surfaces": ["cli"],
        "backend": "main.py:ai_demo_runner",
        "ui": None,
        "cli": "--blue-agents",
        "tui": None,
    },
    # --- Research sidecar + scanners (GAP notes: fixture/demo toggle gaps) ---
    "research-toggle": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/core/config.py:PurpleBoxConfig",
        "ui": "research-toggle",
        "cli": "--research",
        "tui": None,
    },
    "research-scanners": {
        "surfaces": ["cli", "web", "api"],
        "backend": "main.py:ai_demo_runner",
        "ui": "research-scanners-toggle",
        "cli": "--research-scanners",
        "tui": None,
    },
    "research-fixture": {
        "surfaces": ["api"],
        "backend": "library/workflows/workflow.py:_gather_research",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "research-project": {
        "surfaces": ["api"],
        "backend": "library/workflows/project_workflow.py:execute_project_workflow",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "osv-lookup": {
        "surfaces": ["api"],
        "backend": "library/intel/research.py:osv_lookup",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "osv-query": {
        "surfaces": ["api"],
        "backend": "library/intel/research.py:osv_query_package",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "circl-lookup": {
        "surfaces": ["api"],
        "backend": "library/intel/research.py:circl_lookup",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "circl-browse": {
        "surfaces": ["api"],
        "backend": "library/intel/research.py:circl_browse_product",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "ghsa-search": {
        "surfaces": ["api"],
        "backend": "library/intel/research.py:ghsa_search",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "epss-score": {
        "surfaces": ["api"],
        "backend": "library/intel/research.py:epss_score",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "cve-records": {
        "surfaces": ["api"],
        "backend": "library/intel/research.py:cve_records",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "web-notes": {
        "surfaces": ["api"],
        "backend": "library/intel/research.py:web_notes",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "research-sink": {
        "surfaces": ["api"],
        "backend": "library/intel/research.py:research_for_sink",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "nvd-intel": {
        "surfaces": ["api"],
        "backend": "library/intel/intel_search.py:intel_for_demo",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "red-research": {
        "surfaces": ["api"],
        "backend": "library/core/agents.py:run_red_research",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "blue-research": {
        "surfaces": ["api"],
        "backend": "library/core/agents.py:run_blue_research",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "scanner-trivy": {
        "surfaces": ["cli", "api"],
        "backend": "library/intel/scanner_binaries.py:run_trivy",
        "ui": None,
        "cli": "--research-scanners",
        "tui": None,
    },
    "scanner-grype": {
        "surfaces": ["cli", "api"],
        "backend": "library/intel/scanner_binaries.py:run_grype",
        "ui": None,
        "cli": "--research-scanners",
        "tui": None,
    },
    "scanner-osv": {
        "surfaces": ["cli", "api"],
        "backend": "library/intel/scanner_binaries.py:run_osv_scanner",
        "ui": None,
        "cli": "--research-scanners",
        "tui": None,
    },
    "scanner-depcheck": {
        "surfaces": ["cli", "api"],
        "backend": "library/intel/scanner_binaries.py:run_dependency_check",
        "ui": None,
        "cli": "--research-scanners",
        "tui": None,
    },
    "scanner-dtrack": {
        "surfaces": ["cli", "api"],
        "backend": "library/intel/scanner_dtrack.py:scan_packages",
        "ui": None,
        "cli": "--research-scanners",
        "tui": None,
    },
    # --- CVE / deep scan mode (GAP_CLI 6-8) ---
    "cve-scan": {
        "surfaces": ["cli", "api"],
        "backend": "library/workflows/cve_workflow.py:execute_cve_scan",
        "ui": None,
        "cli": "--cve-scan",
        "tui": None,
    },
    "deep-assessment": {
        "surfaces": ["cli", "api"],
        "backend": "library/workflows/deep_scan.py:muse_deep_assessment",
        "ui": None,
        "cli": "--deep-assessment",
        "tui": None,
    },
    "offline-cve": {
        "surfaces": ["cli", "api"],
        "backend": "main.py:cli_runner",
        "ui": None,
        "cli": "--offline-cve",
        "tui": None,
    },
    "static-scan": {
        "surfaces": ["api"],
        "backend": "library/workflows/deep_scan.py:run_static_scan",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    # --- Model profiles + config/output (GAP_CLI 9-10) ---
    "model-profile": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/core/profiles.py:apply_profile",
        "ui": "profile-list",
        "cli": "--profile",
        "tui": None,
    },
    "config-file": {
        "surfaces": ["cli"],
        "backend": "sms_cli.py:load_config_file",
        "ui": None,
        "cli": "--config",
        "tui": None,
    },
    "output-format": {
        "surfaces": ["cli", "web"],
        "backend": "sms_cli.py:format_facts",
        "ui": "download-btn",
        "cli": "--format",
        "tui": None,
    },
    "show-usage": {
        "surfaces": ["cli", "web"],
        "backend": "sms_cli.py:usage_table",
        "ui": "usage",
        "cli": "--show-usage",
        "tui": None,
    },
    "output-dir": {
        "surfaces": ["cli", "web"],
        "backend": "main.py:write_run_report",
        "ui": "download-btn",
        "cli": "--output-dir",
        "tui": None,
    },
    # --- Red/blue agent core ---
    "red-analysis": {
        "surfaces": ["api"],
        "backend": "library/core/agents.py:run_red_team_analysis",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "blue-sanitize": {
        "surfaces": ["api"],
        "backend": "library/core/agents.py:run_blue_team_sanitizer",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "red-prompt": {
        "surfaces": ["api"],
        "backend": "library/core/prompts.py:RED_TEAM_SYSTEM_PROMPT",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "blue-prompt": {
        "surfaces": ["api"],
        "backend": "library/core/prompts.py:BLUE_TEAM_SYSTEM_PROMPT",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "patch-guard": {
        "surfaces": ["api"],
        "backend": "library/core/patches.py:validate_patch",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "normal-checks": {
        "surfaces": ["api"],
        "backend": "library/core/checks.py:normal_behavior_script",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "probe-verdict": {
        "surfaces": ["api"],
        "backend": "library/core/docker_manager.py:VerificationResult",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    # --- sms_* leaf capabilities ---
    "async-blocking": {
        "surfaces": ["api"],
        "backend": "library/shared/sms_async.py:blocking",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "async-emit": {
        "surfaces": ["api"],
        "backend": "library/shared/sms_async.py:make_log",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "http-paced": {
        "surfaces": ["api"],
        "backend": "library/shared/sms_http.py:paced_request_json",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "redact-probe": {
        "surfaces": ["api"],
        "backend": "library/shared/sms_redact.py:redact_probe_output",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "redact-fixture": {
        "surfaces": ["api"],
        "backend": "library/shared/sms_redact.py:redact_fixture_result",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "redact-project": {
        "surfaces": ["api"],
        "backend": "library/shared/sms_redact.py:redact_project_result",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "record-sanitize": {
        "surfaces": ["api"],
        "backend": "library/shared/sms_records.py:sanitize_cve_id",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "record-dedupe": {
        "surfaces": ["api"],
        "backend": "library/shared/sms_records.py:dedupe_records",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "text-bound": {
        "surfaces": ["api"],
        "backend": "library/shared/sms_text.py:bounded",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "payload-budget": {
        "surfaces": ["api"],
        "backend": "library/shared/sms_budget.py:check_payload_budget",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "scan-parse": {
        "surfaces": ["api"],
        "backend": "library/shared/sms_scan_parse.py:cvss_best",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    # --- Web display panels (GAP_API 8-13 render side) ---
    "panel-pipeline": {
        "surfaces": ["web"],
        "backend": "static/app.js:setStage",
        "ui": "pipeline",
        "cli": None,
        "tui": None,
    },
    "panel-timeline": {
        "surfaces": ["web", "tui"],
        "backend": "static/app.js:advanceStage",
        "ui": "scan-timeline",
        "cli": None,
        "tui": "filter",
    },
    "panel-red": {
        "surfaces": ["web", "tui"],
        "backend": "static/app.js:writeLine",
        "ui": "red-log",
        "cli": None,
        "tui": "filter",
    },
    "panel-blue": {
        "surfaces": ["web", "tui"],
        "backend": "static/app.js:writeLine",
        "ui": "blue-log",
        "cli": None,
        "tui": "filter",
    },
    "panel-arena": {
        "surfaces": ["web"],
        "backend": "static/app.js:buildRoster",
        "ui": "red-roster",
        "cli": None,
        "tui": None,
    },
    "panel-arena-blue": {
        "surfaces": ["web"],
        "backend": "static/app.js:buildRoster",
        "ui": "blue-roster",
        "cli": None,
        "tui": None,
    },
    "panel-arena-green": {
        "surfaces": ["web"],
        "backend": "static/app.js:buildRoster",
        "ui": "green-roster",
        "cli": None,
        "tui": None,
    },
    "panel-comms": {
        "surfaces": ["web", "tui"],
        "backend": "library/services/chatter.py:chatter",
        "ui": "comms-log",
        "cli": None,
        "tui": "filter",
    },
    "panel-result": {
        "surfaces": ["web", "tui"],
        "backend": "static/app.js:showResult",
        "ui": "result-panel",
        "cli": None,
        "tui": "start",
    },
    "result-facts": {
        "surfaces": ["web"],
        "backend": "static/app.js:fact",
        "ui": "fact-baseline",
        "cli": None,
        "tui": None,
    },
    "result-usage": {
        "surfaces": ["web", "api"],
        "backend": "library/core/pricing.py:estimate_cost",
        "ui": "usage",
        "cli": None,
        "tui": None,
    },
    "result-cycles": {
        "surfaces": ["web", "api"],
        "backend": "static/app.js:renderCycles",
        "ui": "cycle-reports",
        "cli": None,
        "tui": None,
    },
    "result-diff": {
        "surfaces": ["web", "api"],
        "backend": "static/app.js:renderDiff",
        "ui": "diff",
        "cli": None,
        "tui": None,
    },
    "result-download": {
        "surfaces": ["web"],
        "backend": "static/app.js:download-btn",
        "ui": "download-btn",
        "cli": None,
        "tui": None,
    },
    "result-download-patch": {
        "surfaces": ["web"],
        "backend": "static/app.js:download-patch-btn",
        "ui": "download-patch-btn",
        "cli": None,
        "tui": None,
    },
    "result-copy-diff": {
        "surfaces": ["web"],
        "backend": "static/app.js:copy-diff",
        "ui": "copy-diff",
        "cli": None,
        "tui": None,
    },
    "panel-telemetry": {
        "surfaces": ["web", "tui"],
        "backend": "static/app.js:writeLine",
        "ui": "sys-log",
        "cli": None,
        "tui": "filter",
    },
    "telemetry-filters": {
        "surfaces": ["web", "tui"],
        "backend": "static/app.js:querySelectorAll",
        "ui": "sys-log",
        "cli": None,
        "tui": "filter",
    },
    "target-description": {
        "surfaces": ["web"],
        "backend": "static/app.js:renderTargets",
        "ui": "target-description",
        "cli": None,
        "tui": None,
    },
    "run-setup": {
        "surfaces": ["web"],
        "backend": "static/app.js:initialize",
        "ui": "setup",
        "cli": None,
        "tui": None,
    },
    # --- TUI-only bindings ---
    "tui-select": {
        "surfaces": ["tui"],
        "backend": "tui.py:parse_key",
        "ui": None,
        "cli": None,
        "tui": "select:0",
    },
    "tui-scroll": {
        "surfaces": ["tui"],
        "backend": "tui.py:parse_key",
        "ui": None,
        "cli": None,
        "tui": "scroll:up",
    },
    "tui-quit": {
        "surfaces": ["tui"],
        "backend": "tui.py:parse_key",
        "ui": None,
        "cli": None,
        "tui": "quit",
    },
    "tui-fixture": {
        "surfaces": ["cli", "tui"],
        "backend": "tui.py:run_plain",
        "ui": None,
        "cli": "--fixture",
        "tui": "select:0",
    },
    # --- Personas / chatter ---
    "red-persona": {
        "surfaces": ["api"],
        "backend": "library/core/personas.py:red_persona",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "blue-persona": {
        "surfaces": ["api"],
        "backend": "library/core/personas.py:blue_persona",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "team-chatter": {
        "surfaces": ["api"],
        "backend": "library/services/chatter.py:chatter",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    # --- Post-refactor capabilities (added 2026-10-31 remodel) ---
    "version-source": {
        "surfaces": ["api"],
        "backend": "library/core/version.py:APP_VERSION",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "mcp-stdio": {
        "surfaces": ["cli", "api"],
        "backend": "main.py:main",
        "ui": None,
        "cli": "--mcp",
        "tui": None,
    },
    "mcp-http": {
        "surfaces": ["web", "api"],
        "backend": "library/services/mcp_bridge.py:handle_mcp_request",
        "ui": "mcp-form",
        "cli": None,
        "tui": None,
    },
    "binary-target": {
        "surfaces": ["cli", "web", "api"],
        "backend": "library/workflows/binary_sweep.py:execute_binary_sweep",
        "ui": "binary-form",
        "cli": "--binary-target",
        "tui": None,
    },
    "sweep-passes": {
        "surfaces": ["cli"],
        "backend": "library/workflows/sweep.py:execute_sweep_scan",
        "ui": None,
        "cli": "--sweep-passes",
        "tui": None,
    },
    "chain-fixture": {
        "surfaces": ["api"],
        "backend": "library/core/registry.py:TARGETS_REGISTRY",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "vault-recall": {
        "surfaces": ["api"],
        "backend": "library/intel/sms_vault.py:query_vault",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "compression": {
        "surfaces": ["api"],
        "backend": "library/shared/sms_compress.py:compress_context",
        "ui": None,
        "cli": None,
        "tui": None,
    },
    "python-library-api": {
        "surfaces": ["api"],
        "backend": "library/services/sms_api.py:scan_source",
        "ui": None,
        "cli": None,
        "tui": None,
    },
}

# DOM-id -> extra JS needles proving a live wiring when the control is
# reached by delegation (class loop), container lookup, or dynamic render.
# Each needle was re-verified present in static/*.js on 2026-10-31
# (post-refactor tree); the base
# needles (quoted id, #id) already cover direct el('id') bindings.
WEB_DELEGATED_NEEDLES: dict[str, tuple[str, ...]] = {
    "mode-demo": ("button.dataset.mode",),
    "mode-demo-build": ("button.dataset.mode",),
    "mode-project": ("button.dataset.mode",),
    "target-list": (".target[data-key]",),
    "chip-key": ("chip-key",),
    "chip-docker": ("chip-docker",),
    "chip-server": ("chip-server",),
    "scan-timeline": ("getElementById('scan-timeline')",),
    "telemetry-filters": ("querySelectorAll('.filter')",),
}

MODULE_VERSIONS: dict[str, str] = {
    "library.shared.sms_async": "0.1.0",
    "library.shared.sms_http": "0.1.0",
    "library.shared.sms_redact": "0.1.0",
    "library.shared.sms_records": "0.1.0",
    "library.shared.sms_text": "0.1.0",
    "library.shared.sms_budget": "0.1.0",
    "library.shared.sms_scan_parse": "0.1.0",
    "library.intel.research": "0.1.0",
    "library.services.demo_gen": "0.1.0",
    "library.workflows.workflow": "0.1.0",
    "library.workflows.project_workflow": "0.1.0",
    "library.tags": "0.1.0",
    "library.core.version": "0.13.1",
}


def _binding_live(entry: dict[str, object], surface: str, root: Path) -> bool:
    backend = str(entry.get("backend") or "")
    if surface == "api":
        if ":" not in backend:
            return False
        module, symbol = backend.split(":", 1)
        if module == "static/app.js":
            js = (root / "static" / "app.js").read_text(encoding="utf-8")
            return symbol in js
        # Post-refactor: try root/<module> first. This covers both the
        # library/<area>/<leaf>.py form and the root-level main.py /
        # tui.py / sms_cli.py form.
        path = root / (module if module.endswith(".py") else module + ".py")
        if not path.exists():
            return False
        return symbol in path.read_text(encoding="utf-8")
    if surface == "cli":
        flag = str(entry.get("cli") or "")
        if not flag:
            return False
        for source in ("main.py", "tui.py", "sms_cli.py"):
            text = (root / source).read_text(encoding="utf-8")
            if flag in text:
                return True
        return False
    if surface == "web":
        dom_id = str(entry.get("ui") or "")
        if not dom_id:
            return False
        html = (root / "static" / "index.html").read_text(encoding="utf-8")
        if f'id="{dom_id}"' not in html:
            return False
        needles = [f"'{dom_id}'", f'"{dom_id}"', f"#{dom_id}"]
        needles.extend(WEB_DELEGATED_NEEDLES.get(dom_id, ()))
        for name in ("app.js", "panels.js", "fx.js"):
            try:
                js = (root / "static" / name).read_text(encoding="utf-8")
            except OSError:
                continue
            if any(n in js for n in needles):
                return True
        return False
    if surface == "tui":
        binding = str(entry.get("tui") or "")
        if not binding:
            return False
        text = (root / "tui.py").read_text(encoding="utf-8")
        if binding.startswith("select:") or binding.startswith("scroll:"):
            stem = binding.split(":")[0]
            return stem in text
        return binding in text
    return False


def check_registry(
    registry: dict[str, dict[str, object]] | None = None, root: Path | None = None
) -> dict[str, object]:
    """Walk the registry; report tags missing a live binding per surface.

    Returns {"covered": {tag: [surfaces]}, "uncovered": {tag: [surfaces]},
    "covered_count": int, "total": int}. Never raises on I/O: a missing
    worktree file counts as uncovered, not as a crash.
    """
    # tags.py lives in library/, so the repo root is parent.parent.
    base = root or Path(__file__).resolve().parent.parent
    table = registry if registry is not None else FEATURE_TAGS
    covered: dict[str, list[str]] = {}
    uncovered: dict[str, list[str]] = {}
    try:
        for tag_id, entry in table.items():
            missing = []
            for surface in entry.get("surfaces", []):
                try:
                    live = _binding_live(entry, str(surface), base)
                except OSError:
                    live = False
                if not live:
                    missing.append(str(surface))
            if missing:
                uncovered[tag_id] = missing
            else:
                covered[tag_id] = [str(s) for s in entry.get("surfaces", [])]
    except OSError:
        uncovered.setdefault("__registry__", []).append("api")
    return {
        "covered": covered,
        "uncovered": uncovered,
        "covered_count": len(covered),
        "total": len(table),
    }
