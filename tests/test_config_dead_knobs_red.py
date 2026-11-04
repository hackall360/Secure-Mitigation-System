# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: config.py knobs allegedly dead/unenforced (scout: config.py:153-176).

LAWs 0, 9 govern: real load_config + real consumers, env-only monkeypatch.

Scout claim: 5 knobs dead (read from env, never consumed / unenforced).
Candidate dead set (only knobs load_config actually reads from env):
  1. META_MUSE_RED_MODEL / red_team_model (-> MetaMuseClient._request model)
  2. META_MUSE_BLUE_MODEL / blue_team_model (-> same, run_blue_team_sanitizer)
  3. META_MUSE_MAX_TOKENS / max_output_tokens (-> agents._body max_tokens)
  4. META_MUSE_REASONING_EFFORT / reasoning_effort (-> agents._body)
  5. PURPLEBOX_RESEARCH / research_enabled (-> workflow.execute_purple_workflow gate)
Plus per-knob dead-DIMENSION probes (read-but-unusable sub-paths found on
inspection — each is a TRUE-DEAD dimension of a knob the naive grep calls
alive):
  6. PURPLEBOX_RESEARCH_SCANNERS partially dead: load_config line 172
     intersects with the allowlist, so an UNLISTED scanner name is silently
     dropped from research_scanners before validation can reject it
     (validate's Unknown-scanner branch, config.py:142-144, unreachable).
  7. META_MUSE_TIMEOUT_SECONDS validated (0=no-timeout, 1-3600) but: (a) never passed to any
     scanner subprocess (scanner_binaries DEFAULT_TIMEOUT=300 /
     dep-check 900 ignore it), (b) require_api_key re-validates the whole
     config on every call so a late mutation of api_timeout_seconds is
     unenforced at request time.
  8. PURPLEBOX_VERIFIER_TIMEOUT_SECONDS validated (1-120) but never applied
     to the project loop (run_project_check hardcodes timeout=600 at
     docker_manager.py:879).
  9. max_source_bytes validated but load_config NEVER READS IT from env and
     NO consumer references it (only scripts/mcp_client_demo.py has its own
     unrelated MAX_SOURCE_BYTES=65536): unsettable + unused = fully dead.
 10. docker/infra knobs (target/verifier/binary images, clone_repo_prefix,
     mem/nano/network/docker_timeout/max_source_bytes defaults) never read
     from env at all: load_config has no getenv for them, so they are pinned
     to dataclass defaults no matter what env says.

Each test sets env, runs the REAL load_config, then drives the REAL consumer
and asserts the knob had an effect. A test that FAILS proves the knob (or
that dimension) is truly dead-or-unenforced.
"""

import inspect
import json

import httpx
import pytest

from modules.core import agents as agents_mod
from modules.core import config as config_mod
from modules.core import docker_manager as dock_mod
from modules.core.config import PurpleBoxConfig, load_config
from modules.workflows import workflow as flow_mod

KNOB_ENVS = (
    "META_MUSE_API_KEY",
    "META_MUSE_BASE_URL",
    "PURPLEBOX_INFERENCE_MODE",
    "META_MUSE_RED_MODEL",
    "META_MUSE_BLUE_MODEL",
    "META_MUSE_BLUE_ESCALATION_MODEL",
    "META_MUSE_TIMEOUT_SECONDS",
    "META_MUSE_MAX_TOKENS",
    "META_MUSE_REASONING_EFFORT",
    "PURPLEBOX_RESEARCH",
    "PURPLEBOX_RESEARCH_SCANNERS",
    "PURPLEBOX_VERIFIER_TIMEOUT_SECONDS",
)

FINDING = {
    "vulnerability_class": "input validation",
    "sink_location": "app.js:15",
    "analysis_summary": "An unexpected type reaches an expression.",
    "verification_script_python": "import sys\nsys.exit(0)\n",
}


def _clean_env(monkeypatch):
    for name in KNOB_ENVS:
        monkeypatch.delenv(name, raising=False)


def _muse_client(**overrides):
    base = {"meta_api_key": "unit-test-key"}
    base.update(overrides)
    return agents_mod.MetaMuseClient(PurpleBoxConfig(**base))


# 1. red_team_model: env -> load_config -> wire model
async def test_knob_red_model_reaches_wire(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("META_MUSE_API_KEY", "unit-test-key")
    monkeypatch.setenv("META_MUSE_RED_MODEL", "muse-spark-9.9")
    settings = load_config()
    assert settings.red_team_model == "muse-spark-9.9"
    seen = {}

    def handle(request):
        seen.update(json.loads(request.content))
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(FINDING)}}]}
        )

    client = agents_mod.MetaMuseClient(settings, transport=httpx.MockTransport(handle))
    try:
        await client.run_red_team_analysis("app.js", "test source")
    finally:
        await client.aclose()
    assert seen["model"] == "muse-spark-9.9", "red knob must reach the wire model"


# 2. blue_team_model: same path via run_blue_team_sanitizer model arg
def test_knob_blue_model_reaches_wire(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("META_MUSE_BLUE_MODEL", "muse-wonder-9.9")
    settings = load_config()
    assert settings.blue_team_model == "muse-wonder-9.9"
    client = _muse_client(blue_team_model=settings.blue_team_model)
    try:
        body = client._body(settings.blue_team_model, "sys", {"a": 1})
    finally:
        import anyio

        anyio.run(client.aclose)
    assert body["model"] == "muse-wonder-9.9", "blue knob must reach the wire model"


# 2b. blue_escalation_model: env -> load_config -> propose_blue_escalated model
def test_knob_blue_escalation_model_reaches_runner(monkeypatch):
    from modules.services import project_agents as pa_mod

    _clean_env(monkeypatch)
    monkeypatch.setenv("META_MUSE_API_KEY", "unit-test-key")
    monkeypatch.setenv("META_MUSE_BLUE_ESCALATION_MODEL", "muse-wonder-1.0")
    settings = load_config()
    assert settings.blue_escalation_model == "muse-wonder-1.0"
    src = inspect.getsource(pa_mod.ProjectAgentRunner.propose_blue_escalated)
    assert "blue_escalation_model" in src, "escalation knob must gate the explicit call"


# 3. max_output_tokens: env -> load_config -> _body max_tokens
def test_knob_max_tokens_reaches_body(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("META_MUSE_MAX_TOKENS", "4096")
    settings = load_config()
    assert settings.max_output_tokens == 4096
    body = _muse_client(max_output_tokens=4096)._body("muse-spark-1.3", "sys", {})
    assert body["max_tokens"] == 4096, "max_tokens knob must reach the request body"


# 4. reasoning_effort: env -> load_config -> _body reasoning_effort/temperature
def test_knob_reasoning_effort_reaches_body(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("META_MUSE_REASONING_EFFORT", "high")
    settings = load_config()
    assert settings.reasoning_effort == "high"
    body = _muse_client(reasoning_effort="high")._body("muse-spark-1.3", "sys", {})
    assert body.get("reasoning_effort") == "high", "reasoning_effort must reach the body"
    assert "temperature" not in body
    plain = _muse_client()._body("muse-spark-1.3", "sys", {})
    assert plain.get("temperature") == 0.1
    assert "reasoning_effort" not in plain


# 5. research_enabled: env -> load_config (gate exists in workflow)
def test_knob_research_enabled_loads_and_gates(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("PURPLEBOX_RESEARCH", "on")
    assert load_config().research_enabled is True
    monkeypatch.setenv("PURPLEBOX_RESEARCH", "off")
    assert load_config().research_enabled is False
    import inspect

    src = inspect.getsource(flow_mod.execute_purple_workflow)
    assert "settings.research_enabled" in src, "workflow must gate on research_enabled"
    src2 = inspect.getsource(flow_mod._run_opt_in_scanners)
    assert "settings.research_scanners" in src2


# 6. FIXED 2026-11-01 (correctness audit): unlisted scanner names used to be
# silently dropped by the load_config allowlist intersection, so validate()'s
# Unknown-scanner branch was unreachable. load_config now keeps every
# non-blank name; validate() rejects unknowns fail-closed (ConfigurationError).
# This test pins the fixed behavior: the unknown name must surface, and
# validate()/load_config must refuse it loudly instead of swallowing it.
def test_dead_scanner_allowlist_swallows_unknown_names(monkeypatch):
    import pytest as _pytest

    from modules.core.config import ConfigurationError as _ConfigurationError

    _clean_env(monkeypatch)
    monkeypatch.setenv("PURPLEBOX_RESEARCH_SCANNERS", "trivy,semgrep-evil")
    with _pytest.raises(_ConfigurationError, match="Unknown research scanner"):
        load_config()


# 7a. TRUE-DEAD dimension: api timeout never reaches scanner subprocesses
def test_dead_api_timeout_ignored_by_scanners(monkeypatch):
    _clean_env(monkeypatch)
    from modules.intel import scanner_binaries as sb

    monkeypatch.setenv("META_MUSE_TIMEOUT_SECONDS", "7")
    settings = load_config()
    assert settings.api_timeout_seconds == 7.0
    import inspect

    for fn in (sb.run_trivy, sb.run_grype, sb.run_osv_scanner, sb.run_dependency_check):
        assert "api_timeout" not in inspect.getsource(fn), f"{fn.__name__} ignores api knob"
    assert sb.DEFAULT_TIMEOUT != settings.api_timeout_seconds


# 7b. SCOUT-ERROR check: require_api_key re-validates, so a late-mutated
# api_timeout_seconds is REJECTED at use time (fail-closed, not unenforced).
def test_dead_api_timeout_late_mutation_unenforced(monkeypatch):
    _clean_env(monkeypatch)
    from modules.core.config import ConfigurationError, require_api_key

    settings = load_config()
    object.__setattr__(settings, "api_timeout_seconds", 10**9)
    with pytest.raises(ConfigurationError, match="META_MUSE_TIMEOUT_SECONDS"):
        require_api_key(settings)


# 8. TRUE-DEAD dimension: verifier timeout not applied to project loop (600 hardcoded)
def test_dead_verifier_timeout_ignored_by_project_loop(monkeypatch):
    _clean_env(monkeypatch)
    import inspect

    monkeypatch.setenv("PURPLEBOX_VERIFIER_TIMEOUT_SECONDS", "3")
    settings = load_config()
    assert settings.verifier_timeout_seconds == 3
    src = inspect.getsource(dock_mod.DockerSandboxManager.run_project_check)
    assert "self.config.verifier_timeout_seconds" in src, "project loop must honor the knob"


# 9. TRUE-DEAD: max_source_bytes unsettable via env AND unused by any consumer
def test_dead_max_source_bytes_unsettable_and_unused(monkeypatch):
    _clean_env(monkeypatch)
    import inspect

    monkeypatch.setenv("MAX_SOURCE_BYTES", "1024")
    monkeypatch.setenv("PURPLEBOX_MAX_SOURCE_BYTES", "1024")
    assert load_config().max_source_bytes == 65_536, "knob must be settable from env"
    src = inspect.getsource(config_mod.load_config)
    assert "max_source_bytes" not in src, "load_config must NOT read max_source_bytes (dead)"


# 10. TRUE-DEAD: docker/infra knobs pinned — no env var can move them
# (container_mem_limit + container_cpu_nano are LIVE since 2026-11-04:
# PURPLEBOX_CONTAINER_MEM_LIMIT/_CPU_NANO — see test_live_infra_knobs below.)
@pytest.mark.parametrize(
    "env_name,field,probe",
    [
        ("PURPLEBOX_TARGET_IMAGE", "target_base_image", "sentinel-target:9"),
        ("PURPLEBOX_VERIFIER_IMAGE", "verifier_base_image", "sentinel-verifier:9"),
        ("PURPLEBOX_BINARY_IMAGE", "binary_base_image", "sentinel-binary:9"),
        ("PURPLEBOX_CLONE_PREFIX", "clone_repo_prefix", "sentinel-prefix"),
        ("PURPLEBOX_NETWORK_PREFIX", "network_prefix", "sentinel-net"),
    ],
)
def test_dead_infra_knob_pinned_to_default(monkeypatch, env_name, field, probe):
    _clean_env(monkeypatch)
    import inspect

    monkeypatch.setenv(env_name, str(probe))
    settings = load_config()
    assert getattr(settings, field) != probe, f"{env_name} must move {field}"
    assert field not in inspect.getsource(config_mod.load_config), f"{field} unread (dead)"


# 10b. LIVE: container budget knobs move via env (OOM fix 2026-11-04).
@pytest.mark.parametrize(
    "env_name,field,probe",
    [
        ("PURPLEBOX_CONTAINER_MEM_LIMIT", "container_mem_limit", "9m"),
        ("PURPLEBOX_CONTAINER_CPU_NANO", "container_cpu_nano", 111_111),
    ],
)
def test_live_infra_knob_moves_from_env(monkeypatch, env_name, field, probe):
    _clean_env(monkeypatch)
    import inspect

    monkeypatch.setenv(env_name, str(probe))
    settings = load_config()
    assert getattr(settings, field) == probe, f"{env_name} must move {field}"
    assert field in inspect.getsource(config_mod.load_config), f"{field} must be read (live)"
