# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""WebUI v3 intake/readiness contracts: server-side validation + v3 surface pins.

v2 pinned dashboard intake/readiness through a Node ``evaluate()`` harness
slicing functions out of ``static/app.js`` (``projectSpec``,
``updateScanProfile``, ``renderCycles``, ``summaryEvidence``, ``renderUsage``,
``writeComms``, ``buildRoster``, ``socketQuery``). Those functions do not
exist in ``web/js`` (only ``sms_api.py`` mentions ``renderUsage`` in a
docstring), so the Node harness goes away entirely.

Strategy per test family:

(a) Pure validation logic that still lives server-side is repointed at the
    server: context-budget bounds (``ProjectSpec`` 1024..131072), team sizes
    1..12, scan-profile cycles (``SCAN_PROFILES``), consent-gated remote
    inference (``ProjectWorkflowError`` unless local or consented), receipt
    sha chain fields, and the 5-scanner allowlist.
(b) v2-DOM tests with a v3 equivalent are converted to v3-surface
    assertions: schema defaults (``scan_profile`` ``extra_light``, 5 red /
    5 blue agents), markup (``prod-setup.html`` fixture cards + ``run-opts``),
    research toggles default off, demo build fields, and the 5-scanner encode
    string in ``schema.js``.
(c) The hostile-chatter escaping test becomes the v3 equivalent:
    ``CommsFeed`` textContent-only (no ``.innerHTML`` in ``comms-feed.js``)
    plus legend roster from the trusted ``palette.AGENTS`` list.

Do NOT invent product code. Every test fails first if its anchor is removed
(LAW 9B: sharp assertions).
"""

from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SCHEMA = WEB / "js" / "options" / "schema.js"


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


def _nodes(path: Path):
    parser = Elements()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.nodes


def _ids(path: Path):
    return [attrs["id"] for _, attrs in _nodes(path) if "id" in attrs]


def _schema() -> str:
    return SCHEMA.read_text(encoding="utf-8")


# --- (a) Server-side validation that still exists ---------------------------


def _valid_project_kwargs(**overrides):
    import os
    import tempfile

    base = {
        "path": os.path.realpath(tempfile.mkdtemp()),
        "image": "img:latest",
        "command": ["python3", "app.py"],
        "test_command": ["python3", "-m", "unittest"],
        "contract": "Behavior preserved.",
    }
    base.update(overrides)
    return base


def test_hosted_intake_requires_consent_and_local_intake_never_grants_it():
    """Remote inference stays gated: hosted + consent allows, local never sends."""
    from library.services.projects import ProjectSpec

    hosted_ok = ProjectSpec.model_validate(_valid_project_kwargs(allow_remote_inference=True))
    assert hosted_ok.allow_remote_inference is True
    local_refused = ProjectSpec.model_validate(_valid_project_kwargs(allow_remote_inference=False))
    assert local_refused.allow_remote_inference is False
    # The workflow enforces consent server-side for non-local inference.
    import inspect

    from library.workflows import project_workflow

    source = inspect.getsource(project_workflow)
    assert "Remote inference consent is required" in source


@pytest.mark.parametrize("budget", [1, 1023, 131073, 32768.5])
def test_context_budget_matches_backend_bounds(budget):
    """Context budgets outside 1024..131072 integers are rejected server-side."""
    from pydantic import ValidationError

    from library.services.projects import ProjectSpec

    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(_valid_project_kwargs(context_budget=budget))


def test_scan_intensity_derives_cycles_from_named_profiles():
    """Named profiles fix cycle counts; custom keeps the explicit value."""
    from library.core.scan_profiles import SCAN_PROFILES
    from library.services.projects import ProjectSpec

    assert SCAN_PROFILES["extra_light"].cycles == 1
    assert SCAN_PROFILES["ultra_heavy"].cycles == 12
    spec = ProjectSpec.model_validate(_valid_project_kwargs(scan_profile="extra_light", cycles=1))
    assert spec.cycles == 1
    custom = ProjectSpec.model_validate(_valid_project_kwargs(scan_profile="custom", cycles=9))
    assert custom.cycles == 9
    # A mismatched explicit cycle count against a named profile is rejected.
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(_valid_project_kwargs(scan_profile="extra_light", cycles=9))


def test_dashboard_markup_defaults_to_extra_light_and_five_agent_teams():
    """Prod setup ships fixture cards + run-opts; schema defaults to extra_light / 5v5."""
    schema = _schema()
    assert "def: 'extra_light'" in schema, "scan_profile must default to extra_light"
    assert schema.count("def: 5") >= 2, "red/blue agents must default to 5"
    html = (WEB / "prod-setup.html").read_text(encoding="utf-8")
    assert "fixture-list" in html, "prod setup must render fixture cards"
    assert "run-opts" in html, "prod setup must render run-opts controls"
    assert "src-opts" in html, "prod setup must render source options"
    ids = _ids(WEB / "prod-setup.html")
    assert "launch" in ids, "#launch must exist on prod setup"


def test_team_sizes_match_backend_bounds():
    """Team sizes outside 1..12 are rejected server-side."""
    from pydantic import ValidationError

    from library.services.projects import ProjectSpec

    for field, value in (("red_agents", 0), ("blue_agents", 13)):
        with pytest.raises(ValidationError):
            ProjectSpec.model_validate(_valid_project_kwargs(**{field: value}))


# --- (b) v3-surface equivalents --------------------------------------------


def test_dashboard_readiness_and_consent_visibility():
    """Setup pages gate Launch on readiness and label the consent switch."""
    setup = (WEB / "js" / "pages" / "setup-prod.js").read_text(encoding="utf-8")
    assert "$('launch').disabled = !link.ready" in setup, "Launch must stay disabled until ready"
    assert "allow_remote_inference" in setup or "Allow source to leave this host" in _schema()
    schema = _schema()
    after = schema.split("allow_remote_inference")[1][:200]
    assert "def: false" in after, "remote-inference consent must default off"
    assert "inferenceMode" in setup, "readiness must distinguish local vs hosted inference"


def test_project_summary_counts_cycle_evidence_without_inventing_checks():
    """Result pane renders pre/post/regression facts from the live payload."""
    view = (WEB / "js" / "ui" / "result-view.js").read_text(encoding="utf-8")
    assert "function summarize(" in view, "result-view.js must expose summarize(p)"
    assert "pre_probe_exit" in view and "post_probe_exit" in view
    assert "'Baseline'" in view and "'Regression'" in view
    assert "'Pre-patch probe'" in view and "'Post-patch probe'" in view
    assert "'Sweep'" in view, "sweep pass tally must render from pass_results"


def test_project_model_usage_identifies_blue_roles():
    """Usage list colors ``project_blue_*`` roles blue (same rule v2 pinned)."""
    view = (WEB / "js" / "ui" / "result-view.js").read_text(encoding="utf-8")
    assert "project_blue_" in view, "blue role prefix rule missing"
    assert "Blue" in view and "Red" in view
    assert "prompt_tokens" in view and "cost_usd" in view


def test_arena_comms_roster_withstand_hostile_chatter():
    """CommsFeed is textContent-only; the legend roster comes from trusted palette ids."""
    comms = (WEB / "js" / "ui" / "comms-feed.js").read_text(encoding="utf-8")
    assert ".innerHTML" not in comms, "CommsFeed must never assign innerHTML"
    assert "textContent" in (WEB / "js" / "ui" / "dom.js").read_text(encoding="utf-8")
    legend = (WEB / "js" / "ui" / "legend.js").read_text(encoding="utf-8")
    assert "teamAgents" in legend or "TEAM_ORDER" in legend, "legend must build from palette teams"
    for name in ("Breakwater", "Bastion"):
        assert name in (WEB / "js" / "core" / "palette.js").read_text(encoding="utf-8")


def test_dashboard_research_toggles_exist_and_default_off():
    """Research + scanner toggles exist in the schema and default off."""
    schema = _schema()
    research = schema[schema.index("research:") :]
    assert "def: false" in research[:400], "research must default off"
    scanners = schema[schema.index("research_scanners:") :]
    assert "def: false" in scanners[:600], "research_scanners must default off"
    assert "Docker evidence still decides" in schema


def test_demo_build_prompts_for_brief_and_vulns():
    """Demo build options carry the brief + vulns fields with guiding placeholders."""
    schema = _schema()
    assert "build_brief" in schema and "vulns" in schema
    assert "What should Greenhouse build" in schema
    assert "Vulnerabilities to implement" in schema
    setup_demo = (WEB / "js" / "pages" / "setup-demo.js").read_text(encoding="utf-8")
    assert "build_brief" in setup_demo and "vulns" in setup_demo


def test_demo_hardening_controls_exist():
    """demo_size/flaw_count/seed widgets ride the demo build options."""
    schema = _schema()
    for field in ("demo_size", "flaw_count", "seed"):
        assert field in schema, f"schema field {field!r} missing"
    setup_demo = (WEB / "js" / "pages" / "setup-demo.js").read_text(encoding="utf-8")
    assert "demo_size" in setup_demo and "flaw_count" in setup_demo
    html = (WEB / "demo-setup.html").read_text(encoding="utf-8")
    assert "demo-build-opts" in html, "demo setup must mount the build options form"


def test_w5r2_dashboard_scanner_five_set_matches_cli_allowlist():
    """Schema scanner encode lists the CLI 5-set; server allowlist matches."""
    schema = _schema()
    for scanner in ("trivy", "grype", "osv-scanner", "dependency-check", "dependency-track"):
        assert scanner in schema, f"schema scanner encode missing {scanner!r}"
    link = (WEB / "js" / "stream" / "link.js").read_text(encoding="utf-8")
    for scanner in ("trivy", "grype", "osv-scanner", "dependency-check", "dependency-track"):
        assert scanner in link, f"link.js query encode missing {scanner!r}"
    import inspect

    import main as app_module

    server = inspect.getsource(app_module)
    assert "dependency-track" in server, "server must carry the 5-scanner allowlist"
    # F-222: the allowlist is single-sourced from
    # ALLOWED_RESEARCH_SCANNERS, not copy-pasted per endpoint. The WS, MCP
    # stdio, cli_runner, and ai_demo paths all call _pick_research_scanners.
    assert server.count("_pick_research_scanners(") >= 4, (
        "every research path must use the single allowlist helper"
    )
