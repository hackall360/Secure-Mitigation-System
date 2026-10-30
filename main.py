# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Local UI and CLI for the same Secure Mitigation System workflow."""

import argparse
import asyncio
import json
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from modules.core.config import ConfigurationError, PurpleBoxConfig, load_config
from modules.core.docker_manager import (
    DockerSandboxManager,
    build_base_images,
    docker_status,
    remove_stale_resources,
)
from modules.core.profiles import ProfileError, apply_profile, available_profiles, default_profile
from modules.core.registry import BASE_DIR, TARGETS_REGISTRY
from modules.core.scan_profiles import SCAN_PROFILES
from modules.services.mcp_bridge import (
    SNIPPET_TOOL_NAME,
    handle_mcp_request,
    jsonrpc_error,
    jsonrpc_result,
    structured_result,
    validate_snippet_arguments,
)
from modules.services.projects import ProjectSpec
from modules.workflows.cve_workflow import execute_cve_scan
from modules.workflows.project_workflow import execute_project_workflow, redact_report_for_user
from modules.workflows.sweep import execute_sweep_scan, redact_sweep_result_for_user
from modules.workflows.workflow import execute_purple_workflow, redact_fixture_result_for_user
from sms_cli import (
    LoadError,
    Spinner,
    fact_table,
    health_table,
    load_config_file,
    merge_config,
    status_color,
    usage_table,
)

NOTICE = "Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use."
LICENSE_URL = "https://polyformproject.org/licenses/noncommercial/1.0.0"

# Single source of truth for the release version (LAW 12: 0.major.minor).
# Every surface renders this: FastAPI metadata, /api/health, --version,
# dashboard footer. Bump per LAW 12 on every shipped change set.
APP_VERSION = "0.7.0"

# Exec-audience one-liners for Wave 2/5/8: every capability, its same-day
# value in plain English. Rendered as the --help epilog; sms_cli and tui
# mirror the same lines so all three surfaces agree. No new flags here,
# so LAW 8 (no dead flags) holds by construction.
CAPABILITIES_EPILOG = """Same-day value (Wave 2/5/8, all in the default scan, no extra flags):
  receipts: receipt.json proves what the sandbox actually ran (probe exits + patch hash).
  rationale: guard rationales show why each patch guard fired, in plain words.
  topping: fast-lane topping lists the most reachable + fixable CVE first (--fast-lane).
  mutations: mutation probes confirm the fix still holds under small input changes.
  freshness: freshness stamps show the intel was fetched live today, not cached.
  templates: template-shaped patches stay inside the small-edit guard budget.
  stale token: KEV/EPSS signals older than 1 day render as stale:<date> so old intel never outranks fresh.
  repeat-stability: repeat-stability re-runs the check so a flaky pass cannot verify."""


def _demo_build_failure(exc: BaseException) -> dict:
    """User-safe error report for a failed demo build (UI result-card shape)."""
    return {
        "status": "error",
        "message": f"Demo generation failed ({type(exc).__name__}): {exc}",
        "project": "ai-demo",
        "cycles": [],
        "cycle_reports": [],
        "cumulative_diff": "",
        "diff": "",
        "research_records": [],
        "usage": {"calls": []},
        "total_tokens": 0,
        "cost_usd": None,
        "cleanup_ok": True,
    }


async def execute_mcp_snippet_scan(arguments, emit, *, config=None):
    """Run an MCP snippet through the evidence-gated red/blue Docker loop.

    Registers the snippet as an ephemeral fixture target and delegates to
    execute_purple_workflow with the registry extended. Snippet source is
    injected via the same tar-into-stopped-container path as fixtures —
    never executed on the host. Docker evidence alone decides the verdict.
    """
    import modules.core.registry as _registry
    from modules.core import checks as _checks
    from modules.services.mcp_bridge import (
        mcp_registry_with_snippet,
        snippet_baseline_key,
        snippet_target_source,
    )
    from modules.workflows import workflow as _workflow_mod
    from modules.workflows.workflow import execute_purple_workflow as _run

    source = snippet_target_source(arguments)
    baseline_key = snippet_baseline_key(arguments)
    registry = mcp_registry_with_snippet(arguments)
    original = dict(_registry.TARGETS_REGISTRY)
    try:
        _registry.TARGETS_REGISTRY.clear()
        _registry.TARGETS_REGISTRY.update(registry)
        # Patch Target.read_source for the ephemeral key only: the snippet
        # has no file under targets/, so serve the submitted bytes. Patch
        # normal_behavior_script likewise: the snippet reuses its language
        # fixture's trusted baseline, so regression checks real behavior.
        real_read_source = _registry.Target.read_source
        real_baseline_script = _checks.normal_behavior_script

        def _patched(self):
            if self.key == "mcp_snippet":
                return source
            return real_read_source(self)

        def _patched_baseline(target_key: str) -> str:
            if target_key == "mcp_snippet":
                return real_baseline_script(baseline_key)
            return real_baseline_script(target_key)

        _registry.Target.read_source = _patched  # type: ignore[method-assign]
        _workflow_mod.normal_behavior_script = _patched_baseline  # type: ignore[method-assign]
        try:
            return await _run("mcp_snippet", emit, config=config)
        finally:
            _registry.Target.read_source = real_read_source  # type: ignore[method-assign]
            _workflow_mod.normal_behavior_script = real_baseline_script  # type: ignore[method-assign]
    finally:
        _registry.TARGETS_REGISTRY.clear()
        _registry.TARGETS_REGISTRY.update(original)


async def run_demo_build(
    emit,
    settings,
    *,
    theme: str = "",
    build_brief: str = "",
    vulns: str = "",
    intel_offline: bool = False,
    scan_profile: str = "extra_light",
    cycles: int | None = None,
    red_agents: int = 5,
    blue_agents: int = 5,
    context_budget: int = 32768,
    research: bool = False,
    research_scanners: tuple = (),
    demo_size: str = "standard",
    flaw_count: int | None = None,
    seed: int | None = None,
):
    """Green builder for the dashboard: generate a demo project, then red/blue it.

    Emits green team lines as Greenhouse works, then delegates to the project
    workflow for evidence-gated cycles. Returned dict is already user-redacted.
    `build_brief` is what the user wants built; `vulns` lists CVEs, named
    types, or free text to implement. Both flow into intent parsing + research.
    Scan intensity/team/budget mirror the CLI --ai-demo flags and the project
    form widgets (M1-M5): named profiles force cycle counts, custom allows
    explicit cycles, agent counts active on ultra_heavy only.
    """
    from modules.core.agents import AgentError, MetaMuseClient
    from modules.intel.intel_search import intel_for_demo
    from modules.services.demo_gen import (
        generate_demo_project,
        materialize_demo_project,
        parse_build_intent,
    )
    from modules.workflows.project_workflow import redact_report_for_user

    intent = parse_build_intent(build_brief=build_brief, vulns=vulns, theme=theme)
    themes = [w for w in (theme or "input validation SQL injection XSS").split() if w][:6]
    intel: list = []
    if not intel_offline:
        try:
            intel = await intel_for_demo(themes, per_theme=4)
            await emit("green", f"Greenhouse studied {len(intel)} threat-intel records.")
        except Exception as exc:
            await emit(
                "green",
                f"Greenhouse could not reach threat intel ({type(exc).__name__}); building from patterns.",
            )
        # CVE endpoint series: exact records + EPSS per requested id.
        if intent.cve_ids:
            try:
                from modules.intel.research import cve_records as _cve_records
                from modules.workflows.workflow import blocking as _blocking

                cve_hits = await _blocking(_cve_records, intent.cve_ids)
                intel = list(cve_hits) + list(intel)
                await emit(
                    "green",
                    f"Greenhouse pulled {len(cve_hits)} CVE records "
                    f"({', '.join(intent.cve_ids[:4])}).",
                )
            except Exception as exc:
                await emit(
                    "green",
                    f"Greenhouse CVE lookup unavailable ({type(exc).__name__}); themes only.",
                )
        # Web context: named types + free text via bot-tolerant JSON API.
        web_queries = list(intent.named_types) + list(intent.free_text)
        if web_queries:
            try:
                from modules.intel.research import web_notes as _web_notes
                from modules.workflows.workflow import blocking as _blocking2

                notes = await _blocking2(_web_notes, web_queries)
                intel = list(intel) + list(notes)
                await emit(
                    "green",
                    f"Greenhouse read {len(notes)} web notes ({', '.join(web_queries[:3])}).",
                )
            except Exception as exc:
                await emit(
                    "green",
                    f"Greenhouse web lookup unavailable ({type(exc).__name__}); skipping.",
                )
    else:
        await emit("green", "Greenhouse building from static flaw patterns (offline).")
    if intent.vulns or intent.build_brief:
        await emit(
            "green",
            f"Greenhouse brief: {intent.build_brief[:160] or 'showcase demo'}; "
            f"requested flaws: {', '.join(intent.vulns[:6]) or 'novel mix'}.",
        )
    muse = None
    try:
        try:
            muse = MetaMuseClient(settings)
            files = await generate_demo_project(
                muse,
                intel_context=intel,
                theme=" ".join(themes),
                build_brief=intent.build_brief,
                vulns=intent.vulns,
                size=demo_size,
                flaw_count=flaw_count,
                seed=seed,
            )
        except (AgentError, ValueError, TypeError, OSError) as exc:
            # Invalid generation output (bad syntax, unsafe content, budget
            # overflow) or a Muse transport/schema failure is a reportable
            # scan outcome, not a dead socket.
            await emit(
                "green",
                f"Greenhouse grew a wobbly demo ({type(exc).__name__}); retry the build.",
            )
            return _demo_build_failure(exc)
    finally:
        try:
            if muse is not None:
                await muse.aclose()
        except Exception:
            pass
    try:
        from modules.services.chatter import chatter as _chatter

        await emit("green", _chatter("green", n=len(files.flaw_notes), path="app.py"))
    except Exception:
        await emit("green", "Greenhouse planted a fresh demo with wobbly joints.")
    try:
        spec = materialize_demo_project(files)
    except (ValueError, TypeError, OSError) as exc:
        # A bad generation (invalid syntax, unsafe content) must surface as a
        # reportable scan outcome, never a dead socket with no result card.
        await emit(
            "green", f"Greenhouse grew a wobbly demo ({type(exc).__name__}); retry the build."
        )
        return _demo_build_failure(exc)
    await emit(
        "green",
        f"Greenhouse grew {spec.path.name}: {', '.join(files.cve_inspiration) or 'novel flaw mix'}. Red and blue, it is yours.",
    )
    # Intensity/team/budget (M1-M5): same stamping rule as the CLI ai_demo_runner —
    # named profiles force cycle counts, custom honors explicit cycles.
    from modules.services.projects import ProjectSpec as _Spec

    dump = spec.model_dump(mode="json")
    if scan_profile in SCAN_PROFILES:
        dump["scan_profile"] = scan_profile
        dump["cycles"] = SCAN_PROFILES[scan_profile].cycles
    if scan_profile == "custom" and cycles is not None:
        try:
            dump["cycles"] = max(1, min(20, int(cycles)))
        except (TypeError, ValueError):
            pass
    if scan_profile == "ultra_heavy":
        try:
            dump["red_agents"] = max(1, min(12, int(red_agents)))
            dump["blue_agents"] = max(1, min(12, int(blue_agents)))
        except (TypeError, ValueError):
            pass
    try:
        dump["context_budget"] = max(1024, min(131072, int(context_budget)))
    except (TypeError, ValueError):
        pass
    dump["allow_remote_inference"] = not intel_offline or settings.inference_mode == "local"
    spec = _Spec.model_validate(dump)
    result = await execute_project_workflow(spec, emit, config=settings)
    return redact_report_for_user(result)


def create_app(config: PurpleBoxConfig | None = None) -> FastAPI:
    @asynccontextmanager
    async def readiness_lifespan(application: FastAPI):
        try:
            settings = config or load_config()
            snapshot = _health_report(settings)
            print(
                "[SYSTEM] Secure Mitigation System ready: "
                f"inference={snapshot['inference_mode']} "
                f"(ready={snapshot['inference_ready']}), "
                f"docker={snapshot['docker']['state']}, "
                f"profile={snapshot['default_profile']}.",
                flush=True,
            )
        except Exception as exc:
            print(
                "[SYSTEM] Secure Mitigation System starting with unvalidated "
                f"configuration ({type(exc).__name__}); readiness via /api/health.",
                flush=True,
            )
        yield

    application = FastAPI(
        title="Secure Mitigation System",
        version=APP_VERSION,
        docs_url=None,
        redoc_url=None,
        lifespan=readiness_lifespan,
    )
    application.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"]
    )
    application.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    application.state.scan_lock = asyncio.Lock()

    @application.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.get("/")
    async def index():
        return FileResponse(BASE_DIR / "static" / "index.html")

    @application.get("/api/targets")
    async def list_targets():
        return {
            key: {
                "title": target.title,
                "filename": target.filename,
                "description": target.description,
            }
            for key, target in TARGETS_REGISTRY.items()
        }

    @application.get("/api/health")
    async def health():
        try:
            settings = config or load_config()
            settings.validate()
            return {
                "status": "ok",
                "version": APP_VERSION,
                "api_key_configured": bool(settings.meta_api_key),
                "inference_mode": settings.inference_mode,
                "inference_ready": settings.inference_mode == "local"
                or bool(settings.meta_api_key),
                "red_model": settings.red_team_model,
                "blue_model": settings.blue_team_model,
                "profiles": [
                    {
                        "key": p.key,
                        "label": p.label,
                        "description": p.description,
                        "red_model": p.red_model,
                        "blue_model": p.blue_model,
                    }
                    for p in available_profiles(settings).values()
                ],
                "default_profile": default_profile(settings),
                "scan_profiles": [
                    {
                        "key": profile.key,
                        "label": profile.label,
                        "cycles": profile.cycles,
                        "description": profile.description,
                    }
                    for profile in SCAN_PROFILES.values()
                ],
                "docker": await asyncio.to_thread(docker_status, settings),
                "busy": application.state.scan_lock.locked(),
            }
        except ConfigurationError as exc:
            return JSONResponse(
                {"status": "configuration_error", "message": str(exc)}, status_code=503
            )

    async def run_socket(socket: WebSocket, target_key: str | None = None):
        # Host validation plus exact same-origin validation prevents drive-by browser scans.
        expected_origin = (
            f"{'https' if socket.url.scheme == 'wss' else 'http'}://{socket.headers.get('host')}"
        )
        if socket.headers.get("origin") != expected_origin or (
            target_key is not None
            and target_key not in TARGETS_REGISTRY
            and target_key not in ("__demo__", "__binary__")
        ):
            await socket.close(code=1008)
            return
        # The profile is a fixed key, never a model ID. Unknown keys are refused before
        # any Docker or API work starts.
        try:
            scan_config = apply_profile(config or load_config(), socket.query_params.get("profile"))
            # Dashboard opt-in mirrors --research/--research-scanners: off unless
            # the query explicitly says on. Allowlist-validated like the env var.
            if socket.query_params.get("research") == "on":
                allowed = ("trivy", "grype", "osv-scanner", "dependency-check", "dependency-track")
                wanted = tuple(
                    sorted(
                        {
                            s.strip().lower()
                            for s in (socket.query_params.get("research_scanners") or "").split(",")
                            if s.strip().lower() in allowed
                        }
                    )
                )
                import dataclasses

                scan_config = dataclasses.replace(
                    scan_config, research_enabled=True, research_scanners=wanted
                )
            # Dashboard opt-in mirrors --sweep-passes: absent/single = legacy
            # single loop, 2/3 = multi-pass sweep. Anything else refuses.
            sweep_raw = socket.query_params.get("sweep_passes")
            if sweep_raw in (None, "", "1"):
                sweep_depth: int | None = None
            elif sweep_raw in ("2", "3"):
                sweep_depth = int(sweep_raw)
            else:
                await socket.close(code=1008)
                return
        except (ProfileError, ConfigurationError):
            await socket.close(code=1008)
            return
        await socket.accept()
        lock = application.state.scan_lock
        if lock.locked():
            await socket.send_json(
                {"team": "system", "msg": "Another scan is already running.", "type": "busy"}
            )
            await socket.close(code=1013)
            return

        from modules.services.chatter import socket_emit as _socket_emit

        emit = _socket_emit(socket)

        async def disconnected():
            try:
                while True:
                    event = await socket.receive()
                    if event["type"] == "websocket.disconnect":
                        return
            except (WebSocketDisconnect, RuntimeError):
                return

        async with lock:
            if target_key == "__binary__":
                try:
                    # Binary bytes travel in the first WS frame (base64), never
                    # in URLs, history, or access logs. 8 MiB intake cap + 33%
                    # base64 overhead bound the frame.
                    import base64

                    from modules.services.binary_intake import (
                        BinaryRejected as _BinaryRejected,
                    )
                    from modules.services.binary_intake import (
                        validate_binary_blob as _validate_blob,
                    )

                    raw = await asyncio.wait_for(socket.receive_text(), timeout=60)
                    if len(raw.encode("utf-8")) > 12_000_000:
                        raise ValueError("Binary request is too large.")
                    request = json.loads(raw)
                    blob = base64.b64decode(request.get("blob_b64", ""), validate=True)
                    filename = str(request.get("filename", "") or "")
                    contract = str(request.get("contract", "") or "")
                    binary_spec = _validate_blob(blob, filename=filename, contract=contract)
                except (ValueError, TimeoutError, WebSocketDisconnect, _BinaryRejected) as exc:
                    reason = (
                        str(exc)
                        if isinstance(exc, _BinaryRejected)
                        else (
                            "Invalid binary request. Send JSON with blob_b64, filename, and contract."
                        )
                    )
                    await socket.send_json({"type": "invalid", "team": "system", "msg": reason})
                    await socket.close(code=1008)
                    return
                from modules.workflows.binary_sweep import (
                    execute_binary_sweep as _execute_binary,
                )

                coroutine = _execute_binary(binary_spec, emit, config=scan_config)
            elif target_key is None:
                try:
                    # No paths or source are placed in URLs, browser history, or access logs.
                    raw = await asyncio.wait_for(socket.receive_text(), timeout=30)
                    if len(raw.encode("utf-8")) > 32_768:
                        raise ValueError("Project request is too large.")
                    spec = ProjectSpec.model_validate(json.loads(raw))
                except (ValueError, TimeoutError, WebSocketDisconnect):
                    await socket.send_json(
                        {
                            "type": "invalid",
                            "team": "system",
                            "msg": "Invalid project settings. Check the path, argv commands, cycle count, and context budget.",
                        }
                    )
                    await socket.close(code=1008)
                    return
                coroutine = execute_project_workflow(spec, emit, config=scan_config)
            elif target_key == "__demo__":
                try:
                    # Theme comes from the browser, bounded and sanitized here.
                    # No paths or source in URLs, history, or access logs.
                    raw = await asyncio.wait_for(socket.receive_text(), timeout=30)
                    request = json.loads(raw) if raw.strip() else {}
                    theme = str(request.get("theme", "") or "")[:200]
                    build_brief = str(request.get("build_brief", "") or "")[:500]
                    vulns = str(request.get("vulns", "") or "")[:500]
                    intel_offline = bool(request.get("intel_offline", False))
                    demo_scan_profile = str(request.get("scan_profile", "") or "")
                    if demo_scan_profile not in SCAN_PROFILES:
                        demo_scan_profile = "extra_light"
                    try:
                        demo_cycles = request.get("cycles", None)
                        demo_cycles = (
                            None if demo_cycles is None else max(1, min(20, int(demo_cycles)))
                        )
                    except (TypeError, ValueError):
                        demo_cycles = None
                    try:
                        demo_red = max(1, min(12, int(request.get("red_agents", 5))))
                        demo_blue = max(1, min(12, int(request.get("blue_agents", 5))))
                        demo_budget = max(
                            1024, min(131072, int(request.get("context_budget", 32768)))
                        )
                    except (TypeError, ValueError):
                        demo_red, demo_blue, demo_budget = 5, 5, 32768
                    demo_size = str(request.get("demo_size", "") or "")
                    if demo_size not in ("small", "standard"):
                        demo_size = "standard"
                    try:
                        _flaw = request.get("flaw_count", None)
                        demo_flaw_count = None if _flaw is None else max(1, min(8, int(_flaw)))
                    except (TypeError, ValueError):
                        demo_flaw_count = None
                    try:
                        _seed = request.get("seed", None)
                        demo_seed = None if _seed is None else int(_seed)
                    except (TypeError, ValueError):
                        demo_seed = None
                except (ValueError, TimeoutError, WebSocketDisconnect):
                    await socket.send_json(
                        {
                            "type": "invalid",
                            "team": "system",
                            "msg": "Invalid demo request. Send JSON with an optional theme string.",
                        }
                    )
                    await socket.close(code=1008)
                    return
                coroutine = run_demo_build(
                    emit,
                    scan_config,
                    theme=theme,
                    build_brief=build_brief,
                    vulns=vulns,
                    intel_offline=intel_offline,
                    scan_profile=demo_scan_profile,
                    cycles=demo_cycles,
                    red_agents=demo_red,
                    blue_agents=demo_blue,
                    context_budget=demo_budget,
                    demo_size=demo_size,
                    flaw_count=demo_flaw_count,
                    seed=demo_seed,
                )
            else:
                if target_key == "binary_argv_echo":
                    raise ValueError(
                        "binary_argv_echo is a compiled ELF fixture: use the Binary "
                        "sweep mode (/ws/binary) or --binary-target, not the fixture socket."
                    )
                if sweep_depth is not None:
                    coroutine = execute_sweep_scan(
                        target_key, emit, config=scan_config, max_passes=sweep_depth
                    )
                else:
                    coroutine = execute_purple_workflow(target_key, emit, config=scan_config)
            # Connect preamble: the UI renders plain log frames immediately,
            # so this hello + profile snapshot means it never sits blank
            # while Docker/Muse warm up. Profiles are fixed keys, never model
            # IDs; api keys never print. Fixture/demo only: invalid/busy
            # handlers and project first-frame flow are other owners.
            if target_key is not None:
                try:
                    profile_key = socket.query_params.get("profile") or default_profile(scan_config)
                    hello_msg = (
                        "Connected: "
                        f"{scan_config.red_team_model} vs {scan_config.blue_team_model} "
                        f"(profile {profile_key}"
                        + (", research on" if scan_config.research_enabled else "")
                        + ")."
                    )
                except Exception:
                    hello_msg = "Connected: Secure Mitigation System scan socket ready."
                await emit("system", hello_msg)
            run = asyncio.create_task(coroutine)
            disconnect = asyncio.create_task(disconnected())
            try:
                done, _ = await asyncio.wait({run, disconnect}, return_when=asyncio.FIRST_COMPLETED)
                if run in done:
                    result = await run
                    if target_key == "__demo__":
                        # run_demo_build returns an already-redacted dict.
                        await socket.send_json({"type": "result", **result})
                        return
                    safe = result.model_dump()
                    try:
                        from modules.workflows.binary_sweep import (
                            redact_binary_sweep_result_for_user as _redact_binary,
                        )
                        from modules.workflows.project_workflow import (
                            redact_report_for_user as _redact_proj,
                        )
                        from modules.workflows.sweep import (
                            SweepScanResult as _SweepResult,
                        )
                        from modules.workflows.workflow import (
                            redact_fixture_result_for_user as _redact_fixt,
                        )

                        if target_key is None:
                            safe = _redact_proj(result)
                        elif target_key == "__binary__":
                            safe = _redact_binary(result)
                        elif isinstance(result, _SweepResult):
                            safe = redact_sweep_result_for_user(result)
                        else:
                            safe = _redact_fixt(result)
                    except Exception:
                        # LAW 4 fail-closed: a redaction failure must never
                        # fall back to the unredacted dump (probe scripts and
                        # payloads stay in Docker). Report the error instead.
                        safe = {
                            "status": "error",
                            "message": "Report redaction failed; unredacted details withheld.",
                            "cleanup_ok": bool(getattr(result, "cleanup_ok", True)),
                        }
                    await socket.send_json({"type": "result", **safe})
            except (WebSocketDisconnect, RuntimeError):
                pass
            finally:
                for task in (run, disconnect):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(run, disconnect, return_exceptions=True)
                try:
                    await socket.close()
                except (RuntimeError, WebSocketDisconnect):
                    pass

    @application.websocket("/ws/combat/{target_key}")
    async def combat(socket: WebSocket, target_key: str):
        await run_socket(socket, target_key)

    @application.websocket("/ws/project")
    async def project_combat(socket: WebSocket):
        await run_socket(socket)

    @application.websocket("/ws/demo")
    async def demo_build(socket: WebSocket):
        """Green builder: Muse designs a novel demo project, then red/blue exercise it."""
        await run_socket(socket, target_key="__demo__")

    @application.websocket("/ws/binary")
    async def binary_combat(socket: WebSocket):
        """Binary sweep: validated ELF/Mach-O/PE bytes in the first frame, 3-pass loop."""
        await run_socket(socket, target_key="__binary__")

    @application.post("/mcp")
    async def mcp_endpoint(request: Request):
        """Model Context Protocol endpoint (Streamable HTTP, JSON-RPC).

        Exposes the submit_code_snippet tool: an external AI client sends a
        bounded source snippet, the existing red/blue Docker loop verifies
        it, and the VerdictReceipt + Docker exit codes come back as the
        structured result. Docker evidence alone decides every verdict.
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error."},
                },
                status_code=200,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32600, "message": "Invalid Request."},
                },
                status_code=200,
            )
        method = body.get("method")
        rpc_id = body.get("id")
        if method == "tools/call":
            params = body.get("params") or {}
            tool_name = params.get("name")
            if tool_name in ("sms_scan_source", "sms_scan_binary", "sms_query_vault_stats"):
                if tool_name == "sms_query_vault_stats":
                    from modules.services.sms_api import query_vault_stats

                    structured = {"stats": query_vault_stats()}
                    return JSONResponse(
                        jsonrpc_result(
                            rpc_id,
                            {
                                "content": [{"type": "text", "text": "vault stats"}],
                                "structuredContent": structured,
                            },
                        ),
                        status_code=200,
                    )
                try:
                    settings = config or load_config()
                    settings.validate()
                except ConfigurationError as exc:
                    return JSONResponse(
                        jsonrpc_error(rpc_id, -32000, f"Server not ready: {exc}."),
                        status_code=200,
                    )
                lock = application.state.scan_lock
                if lock.locked():
                    return JSONResponse(
                        jsonrpc_error(rpc_id, -32001, "Another scan is already running."),
                        status_code=200,
                    )
                live_arguments = params.get("arguments") or {}
                if tool_name == "sms_scan_source":
                    try:
                        target = str(live_arguments.get("target") or "")
                        if target not in TARGETS_REGISTRY:
                            raise ValueError(f"Unknown target: {target!r}.")
                        max_passes = int(live_arguments.get("max_passes") or 1)
                    except (ValueError, TypeError) as exc:
                        return JSONResponse(
                            jsonrpc_error(rpc_id, -32602, f"Invalid scan arguments: {exc}."),
                            status_code=200,
                        )

                    async def _emit_source(team: str, message: str) -> None:
                        messages_live.append(f"[{team}] {message}")

                    messages_live: list[str] = []
                    async with lock:
                        try:
                            from modules.services.sms_api import scan_source

                            live_result = await scan_source(
                                target, _emit_source, config=settings, max_passes=max_passes
                            )
                        except Exception as exc:
                            return JSONResponse(
                                jsonrpc_error(
                                    rpc_id, -32603, f"Source scan failed ({type(exc).__name__})."
                                ),
                                status_code=200,
                            )
                    structured = structured_result(live_result)
                    return _mcp_scan_response(rpc_id, structured)
                if tool_name == "sms_scan_binary":
                    import base64 as _base64

                    try:
                        blob = _base64.b64decode(
                            str(live_arguments.get("blob_b64") or ""), validate=True
                        )
                        from modules.services.binary_intake import validate_binary_blob

                        validate_binary_blob(
                            blob,
                            filename=str(live_arguments.get("filename") or "upload.bin"),
                            contract=str(live_arguments.get("contract") or ""),
                        )
                        max_passes_bin = int(live_arguments.get("max_passes") or 3)
                    except Exception as exc:
                        return JSONResponse(
                            jsonrpc_error(rpc_id, -32602, f"Invalid binary: {exc}."),
                            status_code=200,
                        )
                    import tempfile as _tempfile
                    from pathlib import Path as _Path

                    try:
                        with _tempfile.NamedTemporaryFile(delete=False) as tmp:
                            tmp.write(blob)
                            tmp_path = tmp.name

                        async def _emit_bin(team: str, message: str) -> None:
                            messages_bin.append(f"[{team}] {message}")

                        messages_bin: list[str] = []
                        from modules.services.sms_api import scan_binary as _scan_bin

                        async with lock:
                            live_bin = await _scan_bin(
                                tmp_path,
                                _emit_bin,
                                config=settings,
                                contract=str(live_arguments.get("contract") or ""),
                                max_passes=max_passes_bin,
                            )
                        _Path(tmp_path).unlink(missing_ok=True)
                    except Exception as exc:
                        return JSONResponse(
                            jsonrpc_error(
                                rpc_id, -32603, f"Binary scan failed ({type(exc).__name__})."
                            ),
                            status_code=200,
                        )
                    structured = structured_result(live_bin)
                    return _mcp_scan_response(rpc_id, structured)
            if params.get("name") != SNIPPET_TOOL_NAME:
                return JSONResponse(
                    jsonrpc_error(rpc_id, -32602, f"Unknown tool: {params.get('name')}."),
                    status_code=200,
                )
            try:
                arguments = validate_snippet_arguments(params.get("arguments") or {})
            except ValueError as exc:
                return JSONResponse(
                    jsonrpc_error(rpc_id, -32602, str(exc)),
                    status_code=200,
                )
            try:
                settings = config or load_config()
                settings.validate()
            except ConfigurationError as exc:
                return JSONResponse(
                    jsonrpc_error(rpc_id, -32000, f"Server not ready: {exc}."),
                    status_code=200,
                )
            lock = application.state.scan_lock
            if lock.locked():
                return JSONResponse(
                    jsonrpc_error(rpc_id, -32001, "Another scan is already running."),
                    status_code=200,
                )
            messages: list[str] = []

            async def _emit(team: str, message: str) -> None:
                messages.append(f"[{team}] {message}")

            async with lock:
                try:
                    result = await execute_mcp_snippet_scan(arguments, _emit, config=settings)
                except Exception as exc:
                    return JSONResponse(
                        jsonrpc_error(
                            rpc_id, -32603, f"Snippet scan failed ({type(exc).__name__})."
                        ),
                        status_code=200,
                    )
            structured = structured_result(result)
            return _mcp_scan_response(rpc_id, structured)
        return JSONResponse(handle_mcp_request(body), status_code=200)

    return application


def _mcp_scan_response(rpc_id: object, structured: dict) -> JSONResponse:
    """Shared /mcp structured scan envelope (content + structuredContent)."""
    return JSONResponse(
        jsonrpc_result(
            rpc_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"status={structured['status']} "
                            f"pre_probe_exit={structured['pre_probe_exit']} "
                            f"post_probe_exit={structured['post_probe_exit']}"
                        ),
                    }
                ],
                "structuredContent": structured,
            },
        ),
        status_code=200,
    )


app = create_app()


_SNIPPET_LANGUAGE_BY_SUFFIX = {
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".py": "python",
    ".php": "php",
}


async def mcp_snippet_runner(
    snippet_path: Path,
    *,
    language: str | None = None,
    contract: str = "",
    output_dir: Path | None = None,
    out_format: str = "table",
    show_usage: bool = False,
) -> int:
    """CLI form of submit_code_snippet: verify one file, print receipt JSON."""
    from modules.core.config import load_config as _load
    from modules.services.mcp_bridge import validate_snippet_arguments

    try:
        source = snippet_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Cannot read snippet file: {exc}.", file=sys.stderr)
        return 1
    resolved = language or _SNIPPET_LANGUAGE_BY_SUFFIX.get(snippet_path.suffix.lower(), "")
    if not resolved:
        print(
            "Cannot infer snippet language; pass --snippet-language javascript|python|php.",
            file=sys.stderr,
        )
        return 1
    try:
        arguments = validate_snippet_arguments(
            {
                "filename": snippet_path.name,
                "language": resolved,
                "source": source,
                "contract": contract or "Preserve normal behavior. Only harden untrusted inputs.",
            }
        )
    except ValueError as exc:
        print(f"Invalid snippet: {exc}", file=sys.stderr)
        return 1
    settings = _load()
    lines: list[str] = []

    async def _emit(team: str, message: str) -> None:
        lines.append(f"[{team}] {message}")

    result = await execute_mcp_snippet_scan(arguments, _emit, config=settings)
    for line in lines:
        print(line)
    if out_format == "json":
        print(json.dumps(structured_result(result), indent=2))
    else:
        print(fact_table(result))
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = output_dir / f"mcp-snippet-{stamp}"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "report.json").write_text(
            json.dumps(structured_result(result), indent=2), encoding="utf-8"
        )
        print(f"Saved MCP snippet report to {run_dir}/report.json")
    if show_usage:
        print(usage_table(result.usage))
    return 0 if getattr(result, "success", False) else 1


def mcp_stdio_runner() -> int:
    """MCP STDIO transport: JSON-RPC on stdin/stdout, one response per line.

    Synchronous tools (vault stats, receipt validation) answer inline via
    handle_mcp_request. Docker-running tools (submit_code_snippet,
    sms_scan_source, sms_scan_binary) execute the live loop and return the
    structured result. A `shutdown` notification ends the session.
    """
    import sys as _sys

    from modules.services.mcp_bridge import (
        SNIPPET_TOOL_NAME,
        handle_mcp_request,
        structured_result,
        validate_snippet_arguments,
    )

    for raw_line in _sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            body = json.loads(line)
        except ValueError:
            _sys.stdout.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": "Parse error."},
                    }
                )
                + "\n"
            )
            _sys.stdout.flush()
            continue
        if not isinstance(body, dict):
            _sys.stdout.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32600, "message": "Invalid Request."},
                    }
                )
                + "\n"
            )
            _sys.stdout.flush()
            continue
        if body.get("method") in ("shutdown", "notifications/exit"):
            break
        method = body.get("method")
        params = body.get("params") if isinstance(body.get("params"), dict) else {}
        name = params.get("name") if isinstance(params, dict) else None
        arguments = params.get("arguments") if isinstance(params, dict) else {}
        arguments = arguments if isinstance(arguments, dict) else {}
        if method == "tools/call" and name == SNIPPET_TOOL_NAME:
            try:
                snippet_args = validate_snippet_arguments(arguments)
            except ValueError as exc:
                _sys.stdout.write(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": body.get("id"),
                            "error": {"code": -32602, "message": str(exc)},
                        }
                    )
                    + "\n"
                )
                _sys.stdout.flush()
                continue

            async def _emit_snippet(team: str, message: str) -> None:
                sys.stderr.write(f"[{team}] {message}\n")

            try:
                from modules.core.config import load_config as _load

                result = asyncio.run(
                    execute_mcp_snippet_scan(snippet_args, _emit_snippet, config=_load())
                )
            except Exception as exc:
                _sys.stdout.write(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": body.get("id"),
                            "error": {
                                "code": -32603,
                                "message": f"Snippet scan failed ({type(exc).__name__}).",
                            },
                        }
                    )
                    + "\n"
                )
                _sys.stdout.flush()
                continue
            _sys.stdout.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": body.get("id"),
                        "result": {
                            "content": [{"type": "text", "text": "snippet scan complete"}],
                            "structuredContent": structured_result(result),
                        },
                    }
                )
                + "\n"
            )
            _sys.stdout.flush()
            continue
        if method == "tools/call" and name == "sms_scan_source":
            target = str(arguments.get("target") or "")
            try:
                max_passes = int(arguments.get("max_passes") or 1)
            except (TypeError, ValueError):
                max_passes = 1

            async def _emit_source(team: str, message: str) -> None:
                sys.stderr.write(f"[{team}] {message}\n")

            try:
                from modules.core.config import load_config as _load
                from modules.services.sms_api import scan_source

                result = asyncio.run(
                    scan_source(target, _emit_source, config=_load(), max_passes=max_passes)
                )
            except Exception as exc:
                _sys.stdout.write(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": body.get("id"),
                            "error": {
                                "code": -32603,
                                "message": f"Source scan failed ({type(exc).__name__}).",
                            },
                        }
                    )
                    + "\n"
                )
                _sys.stdout.flush()
                continue
            _sys.stdout.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": body.get("id"),
                        "result": {
                            "content": [{"type": "text", "text": "source scan complete"}],
                            "structuredContent": structured_result(result),
                        },
                    }
                )
                + "\n"
            )
            _sys.stdout.flush()
            continue
        if method == "tools/call" and name == "sms_scan_binary":
            import base64 as _base64
            import tempfile as _tempfile
            from pathlib import Path as _Path

            try:
                blob = _base64.b64decode(str(arguments.get("blob_b64") or ""), validate=True)
                from modules.services.binary_intake import validate_binary_blob

                validate_binary_blob(
                    blob,
                    filename=str(arguments.get("filename") or "upload.bin"),
                    contract=str(arguments.get("contract") or "Preserve normal behavior."),
                )
            except Exception as exc:
                _sys.stdout.write(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": body.get("id"),
                            "error": {"code": -32602, "message": f"Invalid binary: {exc}."},
                        }
                    )
                    + "\n"
                )
                _sys.stdout.flush()
                continue
            try:
                from modules.core.config import load_config as _load
                from modules.services.sms_api import scan_binary as _scan_binary_run

                with _tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(blob)
                    tmp_path = tmp.name

                async def _emit_binary(team: str, message: str) -> None:
                    sys.stderr.write(f"[{team}] {message}\n")

                try:
                    max_passes_raw = arguments.get("max_passes") or 3
                    max_passes_bin = int(max_passes_raw)
                except (TypeError, ValueError):
                    max_passes_bin = 3
                result = asyncio.run(
                    _scan_binary_run(
                        tmp_path,
                        _emit_binary,
                        config=_load(),
                        contract=str(arguments.get("contract") or ""),
                        max_passes=max_passes_bin,
                    )
                )
                _Path(tmp_path).unlink(missing_ok=True)
            except Exception as exc:
                _sys.stdout.write(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": body.get("id"),
                            "error": {
                                "code": -32603,
                                "message": f"Binary scan failed ({type(exc).__name__}).",
                            },
                        }
                    )
                    + "\n"
                )
                _sys.stdout.flush()
                continue
            _sys.stdout.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": body.get("id"),
                        "result": {
                            "content": [{"type": "text", "text": "binary scan complete"}],
                            "structuredContent": structured_result(result),
                        },
                    }
                )
                + "\n"
            )
            _sys.stdout.flush()
            continue
        response = handle_mcp_request(body)
        _sys.stdout.write(json.dumps(response) + "\n")
        _sys.stdout.flush()
    return 0


async def binary_sweep_runner(
    binary_path: Path,
    *,
    contract: str = "",
    max_passes: int = 3,
    output_dir: Path | None = None,
    out_format: str = "table",
    show_usage: bool = False,
) -> int:
    """CLI form of the binary 3-pass sweep: validate, sweep, print report JSON."""
    from modules.core.config import load_config as _load
    from modules.services.binary_intake import BinaryRejected, validate_binary_file
    from modules.workflows.binary_sweep import (
        execute_binary_sweep,
        redact_binary_sweep_result_for_user,
    )

    try:
        spec = validate_binary_file(
            str(binary_path),
            contract=contract or "Preserve normal behavior. Only harden untrusted inputs.",
        )
    except BinaryRejected as exc:
        print(f"Invalid binary target: {exc}", file=sys.stderr)
        return 1
    settings = _load()
    lines: list[str] = []

    async def _emit(team: str, message: str) -> None:
        lines.append(f"[{team}] {message}")

    result = await execute_binary_sweep(
        spec, _emit, config=settings, max_passes=max(1, min(3, max_passes))
    )
    for line in lines:
        print(line)
    report = redact_binary_sweep_result_for_user(result)
    if out_format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(fact_table(result))
        for passed in result.pass_results:
            sha = passed.receipt.patch_sha256[:12] if passed.receipt else "none"
            print(
                f"[PASS ] {passed.pass_id}: pre={passed.pre_exit_code} "
                f"post={passed.post_exit_code} cleared={passed.cleared} receipt={sha}"
            )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = output_dir / f"binary-sweep-{stamp}"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Saved binary sweep report to {run_dir}/report.json")
    if show_usage:
        print(usage_table(result.usage))
    return 0 if getattr(result, "success", False) else 1


async def ai_demo_runner(
    output_dir: Path,
    profile: str | None = None,
    *,
    scan_profile: str = "extra_light",
    cycles: int | None = None,
    red_agents: int = 5,
    blue_agents: int = 5,
    intel_theme: str = "input validation SQL injection XSS deserialization",
    intel_offline: bool = False,
    build_brief: str = "",
    vulns: str = "",
    research: bool = False,
    research_scanners: str = "",
    allow_remote_inference: bool = False,
    demo_size: str = "standard",
    flaw_count: int | None = None,
    demo_seed: int | None = None,
    out_format: str = "table",
    show_usage: bool = False,
) -> int:
    """AI-built demo mode: intel-grounded generation, then evidence-gated red/blue in Docker."""
    from modules.core.agents import MetaMuseClient
    from modules.core.config import load_config as _load
    from modules.core.profiles import apply_profile as _apply
    from modules.intel.intel_search import intel_for_demo
    from modules.services.demo_gen import generate_demo_project, materialize_demo_project

    settings = _apply(_load(), profile)
    if research:
        # Same 5-set allowlist as --scan/--project and the dashboard socket.
        allowed = {"trivy", "grype", "osv-scanner", "dependency-check", "dependency-track"}
        picked = tuple(sorted({s.strip().lower() for s in research_scanners.split(",")} & allowed))
        settings = settings.__class__(
            **{**settings.__dict__, "research_enabled": True, "research_scanners": picked}
        )
    if settings.inference_mode != "local" and not allow_remote_inference:
        # Consent parity: hosted Muse receives generated source, so the demo
        # stays offline (patterns only) unless consent is explicit — same rule
        # the dashboard enforces by coercing intel_offline without the checkbox.
        intel_offline = True
        print(
            "[SYSTEM] AI demo: hosted inference without --allow-remote-inference; "
            "building offline from static flaw patterns.",
            flush=True,
        )

    themes = [w for w in intel_theme.split() if w][:6]
    if intel_offline:
        intel: list = []
        print(
            "[SYSTEM] AI demo: offline mode, using static flaw patterns (no NVD lookup).",
            flush=True,
        )
    else:
        print(
            f"[SYSTEM] AI demo: gathering threat intel for themes: {', '.join(themes)}", flush=True
        )
        try:
            intel = await intel_for_demo(themes, per_theme=4)
            print(f"[SYSTEM] AI demo: {len(intel)} intel records for generation.", flush=True)
        except Exception as exc:
            print(
                f"[SYSTEM] AI demo: intel unavailable ({type(exc).__name__}); continuing offline.",
                flush=True,
            )
            intel = []
    print("[SYSTEM] AI demo: Muse designing a novel demo project (red-team driver).", flush=True)
    from modules.services.demo_gen import parse_build_intent as _parse

    _intent = _parse(build_brief=build_brief, vulns=vulns, theme=intel_theme)
    muse = MetaMuseClient(settings)
    try:
        files = await generate_demo_project(
            muse,
            intel_context=intel,
            theme=" ".join(themes),
            build_brief=_intent.build_brief,
            vulns=_intent.vulns,
            size=demo_size,
            flaw_count=flaw_count,
            seed=demo_seed,
        )
    finally:
        try:
            await muse.aclose()
        except Exception:
            pass
    print(
        f"[SYSTEM] AI demo: generated app.py ({len(files.app_py)} chars) inspired by {', '.join(files.cve_inspiration) or 'novel combinations'}.",
        flush=True,
    )
    spec = materialize_demo_project(files)
    try:
        from modules.services.chatter import chatter as _chatter

        print(f"[GREEN] {_chatter('green', n=len(files.flaw_notes), path='app.py')}", flush=True)
    except Exception:
        pass
    # Enrich ProjectSpec with requested intensity/team sizes.
    # Same stamping rule as run_demo_build (M1-M5): named profiles force
    # cycle counts, custom honors explicit cycles (clamped 1..20).
    from modules.services.projects import ProjectSpec as _Spec

    _dump = dict(spec.model_dump(mode="json"))
    _stamp_profile = scan_profile if scan_profile in SCAN_PROFILES else "custom"
    _dump["scan_profile"] = _stamp_profile
    if _stamp_profile != "custom":
        _dump["cycles"] = SCAN_PROFILES[_stamp_profile].cycles
    elif cycles is not None:
        try:
            _dump["cycles"] = max(1, min(20, int(cycles)))
        except (TypeError, ValueError):
            pass
    _dump["red_agents"] = red_agents
    _dump["blue_agents"] = blue_agents
    _dump["allow_remote_inference"] = allow_remote_inference or settings.inference_mode == "local"
    spec = _Spec.model_validate(_dump)
    return await cli_runner(
        None,
        output_dir,
        profile,
        research,
        research_scanners,
        project=spec,
        out_format=out_format,
        show_usage=show_usage,
    )


async def cli_runner(
    target_key: str | None,
    output_dir: Path | None = None,
    profile: str | None = None,
    research: bool = False,
    research_scanners: str = "",
    *,
    project: ProjectSpec | None = None,
    cve_scan: bool = False,
    deep_assessment: bool = False,
    offline_cve: bool = False,
    fast_lane: bool = False,
    out_format: str = "table",
    show_usage: bool = False,
    sweep_passes: int | None = None,
) -> int:
    use_color: bool | None = None
    json_mode = out_format == "json"

    def _out(message: str):
        # --format json keeps stdout machine-pure (report only); all chatter
        # goes to stderr. Table mode keeps the legacy stdout stream.
        print(message, flush=True, file=sys.stderr if json_mode else sys.stdout)

    def emit_progress(team: str, message: str):
        print(f"[{team.upper():6}] {message}", flush=True, file=sys.stderr)

    async def emit(team: str, message: str):
        emit_progress(team, message)

    settings = apply_profile(load_config(), profile)
    if research:
        allowed = {"trivy", "grype", "osv-scanner", "dependency-check", "dependency-track"}
        picked = tuple(sorted({s.strip().lower() for s in research_scanners.split(",")} & allowed))
        settings = settings.__class__(
            **{**settings.__dict__, "research_enabled": True, "research_scanners": picked}
        )
    _out(f"[SYSTEM] Models: red {settings.red_team_model}, blue {settings.blue_team_model}")
    if project is not None and cve_scan:
        cve_result = await execute_cve_scan(
            project,
            emit,
            config=settings,
            include_osv=not offline_cve,
            include_deep_assessment=deep_assessment,
            include_nvd=True,
            fast_lane=fast_lane,
        )
        _out(f"[SYSTEM] {cve_result.message}")
        for vuln in cve_result.vulnerabilities[:20]:
            cves = ",".join(vuln.get("cves") or [vuln.get("id", "")])
            _out(f"[CVE    ] {cves}: {(vuln.get('summary') or '')[:160]}")
            # Wave 2 item 3: topping evidence on the live terminal path.
            try:
                score = vuln.get("reach_score")
                if score is not None:
                    kev = " KEV" if vuln.get("kev_listed") else ""
                    epss = vuln.get("epss_percentile")
                    epss_s = f" EPSS {float(epss):.2f}" if isinstance(epss, (int, float)) else ""
                    fixed = vuln.get("fixed_versions") or []
                    fix_s = f" fix {fixed[0]}" if fixed else ""
                    _out(f"[TOP    ] {cves}: reach {score}{kev}{epss_s}{fix_s}")
            except Exception:
                pass
        if output_dir is not None:
            report = {"notice": NOTICE, "license_url": LICENSE_URL, **cve_result.model_dump()}
            summary = _build_cve_summary_markdown(project, settings, cve_result)
            run_dir = write_run_report(output_dir, report, summary)
            print(f"[SYSTEM] Report: {run_dir / 'report.json'}")
        return 0 if cve_result.success else 1
    if project is None:
        with Spinner("Verifying fixture boundary"):
            if sweep_passes is not None:
                result = await execute_sweep_scan(
                    target_key,
                    emit,
                    config=settings,
                    max_passes=max(1, min(3, sweep_passes)),
                )
                user_report = redact_sweep_result_for_user(result)
            else:
                result = await execute_purple_workflow(target_key, emit, config=settings)
                user_report = redact_fixture_result_for_user(result)
    else:
        with Spinner("Verifying project boundary"):
            result = await execute_project_workflow(project, emit, config=settings)
        user_report = redact_report_for_user(result)
    if out_format == "json":
        # LAW 4: only the redacted report reaches stdout; probe scripts stay in Docker.
        print(json.dumps(user_report, indent=2, default=str))
    else:
        _out(fact_table(result, use_color=use_color))
        if show_usage or result.usage.calls:
            _out(usage_table(result, use_color=use_color))
        _out(f"Status: {status_color(str(result.status), use_color)}")
    for call in result.usage.calls:
        cost = "price unknown" if call.cost_usd is None else f"${call.cost_usd:.4f}"
        # Per-call transparency: which Muse model is active, which phase
        # (usage role) it served, and how it reasons — token counts from the
        # usage payload plus the reasoning share of its output tokens.
        output_tokens = max(int(getattr(call, "completion_tokens", 0) or 0), 0)
        reasoning_tokens = max(int(getattr(call, "reasoning_tokens", 0) or 0), 0)
        reasoning_share = reasoning_tokens / output_tokens if output_tokens > 0 else 0.0
        print(
            f"[USAGE ] {call.role or '?'} {call.model}: {call.prompt_tokens} in, "
            f"{call.completion_tokens} out ({call.reasoning_tokens} reasoning, "
            f"{reasoning_share:.0%} of output), "
            f"{call.seconds:.1f}s, {cost} "
            f"[model {call.model} active on {call.role or '?'} phase]",
            flush=True,
            file=sys.stderr,
        )
    if result.usage.calls:
        cost_value = getattr(result, "cost_usd", getattr(result, "total_cost_usd", None))
        total = "unknown" if cost_value is None else f"${cost_value:.4f}"
        total_tokens = getattr(result, "total_tokens", 0)
        print(
            f"[USAGE ] total {total_tokens} tokens, estimated cost {total}",
            flush=True,
            file=sys.stderr,
        )
    if output_dir is not None:
        report = {"notice": NOTICE, "license_url": LICENSE_URL, **user_report}
        summary = _build_summary_markdown(target_key, project, settings, result)
        run_dir = write_run_report(output_dir, report, summary, diff=result.diff or "")
        print(f"[SYSTEM] Report: {run_dir / 'report.json'}")
    return 0 if result.success else 1


def _extract_wave2_receipt(report: dict) -> dict | None:
    """Item 1 (+ project cycles) receipt payload for receipt.json.

    REAL fields first: top-level ``receipt`` (VerdictReceipt dump), then
    every ``cycle_reports``/``cycles`` entry ``receipt`` (CycleReceipt dump).
    Legacy ``verdict_receipt`` fallback last. Defensive: dict-or-None only.
    First-cycle behavior unchanged (receipt.json holds the first receipt);
    use extract_cycle_receipts for the full per-cycle export.
    """
    receipts = extract_cycle_receipts(report)
    return receipts[0] if receipts else None


def extract_cycle_receipts(report: dict) -> list[dict]:
    """Export ALL cycle receipts (Wave 8 item 4); first-cycle order preserved."""
    if not isinstance(report, dict):
        return []
    try:
        candidates: list = [report.get("receipt"), report.get("verdict_receipt")]
        for key in ("cycle_reports", "cycles"):
            items = report.get(key)
            if isinstance(items, (list, tuple)):
                for item in items:
                    if isinstance(item, dict):
                        candidates.append(item.get("receipt"))
        receipts: list[dict] = []
        for candidate in candidates:
            if hasattr(candidate, "model_dump"):
                try:
                    candidate = candidate.model_dump()
                except Exception:
                    continue
            if isinstance(candidate, dict) and candidate:
                receipts.append({str(k)[:64]: v for k, v in list(candidate.items())[:32]})
        return receipts
    except Exception:
        return []


def write_run_report(output_dir: Path, report: dict, summary: str, diff: str = "") -> Path:
    """Persist one scan run: fresh 0700 run dir, 0600 report.json/SUMMARY.md (+candidate.patch)."""
    # A fresh per-run directory prevents accidental overwriting of previous results.
    run_dir = output_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    (run_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (run_dir / "report.json").chmod(0o600)
    # Wave 2 item 1: export the machine-readable verdict receipt alongside the
    # candidate patch so same-day reviewers can audit it (never a verdict input).
    receipt = _extract_wave2_receipt(report) if isinstance(report, dict) else None
    if receipt:
        (run_dir / "receipt.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )
        (run_dir / "receipt.json").chmod(0o600)
    if diff:
        (run_dir / "candidate.patch").write_text(diff, encoding="utf-8")
        (run_dir / "candidate.patch").chmod(0o600)
    (run_dir / "SUMMARY.md").write_text(summary, encoding="utf-8")
    (run_dir / "SUMMARY.md").chmod(0o600)
    return run_dir


def _build_cve_summary_markdown(project, settings, result) -> str:
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    try:
        stamp = _dt.now(_tz.utc).isoformat()
    except Exception:
        stamp = "unknown time"
    lines: list[str] = []
    lines.append("# Secure Mitigation System — Deep CVE Scan Summary")
    lines.append("")
    lines.append(f"- Target: `{getattr(project, 'path', project)}`")
    lines.append(f"- Timestamp (UTC): {stamp}")
    lines.append(f"- Static signals: {len(result.static_findings)}")
    lines.append(f"- Dependencies: {len(result.dependencies)}")
    lines.append(f"- CVE records: {len(result.vulnerabilities)}")
    lines.append("")
    lines.append("## Static signals (triage hypotheses, not confirmed)")
    for finding in result.static_findings[:100]:
        lines.append(
            f"- [{finding.get('severity')}] {finding.get('rule_id')} {finding.get('path')}:{finding.get('line')} {finding.get('title')} ({finding.get('cwe')})"
        )
    lines.append("")
    lines.append("## Dependencies")
    for dep in result.dependencies[:100]:
        lines.append(f"- {dep.get('ecosystem')}:{dep.get('name')}@{dep.get('version')}")
    lines.append("")
    lines.append("## CVE records")
    for vuln in result.vulnerabilities[:50]:
        cves = ", ".join(vuln.get("cves") or [vuln.get("id", "")])
        sev = "; ".join(f"{s.get('type')}:{s.get('score')}" for s in (vuln.get("severity") or []))
        fixed = ", ".join(vuln.get("fixed_versions") or [])
        lines.append(f"- {cves} — {(vuln.get('summary') or '')[:200]}")
        if sev:
            lines.append(f"  Severity: {sev}")
        if fixed:
            lines.append(f"  Fixed in: {fixed}")
    # Wave 2 item 3: auditable fast-lane queue order (reach/KEV/EPSS topping).
    try:
        ranked = list(result.vulnerabilities or [])[:10]
        topping = [v for v in ranked if isinstance(v, dict) and v.get("reach_score") is not None]
        if topping:
            lines.append("")
            lines.append("## Fast-lane topping (reach + fixability order)")
            for vuln in topping:
                cves = ", ".join(vuln.get("cves") or [vuln.get("id", "")])
                score = vuln.get("reach_score")
                fixed = ", ".join(vuln.get("fixed_versions") or [])
                kev = " KEV-listed" if vuln.get("kev_listed") else ""
                epss = vuln.get("epss_percentile")
                epss_str = f" EPSS {float(epss):.2f}" if isinstance(epss, (int, float)) else ""
                lines.append(f"- {cves} — reach {score}{kev}{epss_str}")
                if fixed:
                    lines.append(f"  Fixed in: {fixed}")
                for ev in (vuln.get("reach_evidence") or [])[:4]:
                    lines.append(f"  evidence: {str(ev)[:160]}")
    except Exception:
        pass
    deep_assessment = getattr(result, "deep_assessment", None)
    if deep_assessment:
        lines.append("")
        lines.append("## Muse deep assessment (advisory)")
        try:
            assessment = deep_assessment.get("assessment", "")
        except AttributeError:
            assessment = str(deep_assessment)
        lines.append(str(assessment)[:8000])
    errors = getattr(result, "errors", None) or []
    if errors:
        lines.append("")
        lines.append("## Lookup warnings")
        for err in errors[:20]:
            lines.append(f"- {err}")
    lines.append("")
    lines.append(NOTICE)
    lines.append(LICENSE_URL)
    lines.append("")
    return "\n".join(lines)


def _build_summary_markdown(target_key: str | None, project, settings, result) -> str:
    name = (
        target_key
        or getattr(project, "path", None)
        or getattr(result, "target", None)
        or getattr(result, "project", "scan")
    )
    try:
        stamp = datetime.now(timezone.utc).isoformat()
    except Exception:
        stamp = "unknown time"
    lines: list[str] = []
    lines.append("# Secure Mitigation System — Scan Summary")
    lines.append("")
    lines.append(f"- Target/Project: `{name}`")
    lines.append(f"- Timestamp (UTC): {stamp}")
    lines.append(f"- Models: red `{settings.red_team_model}`, blue `{settings.blue_team_model}`")
    status = getattr(result, "status", "unknown")
    lines.append(f"- Status: `{status}`")
    cleanup_ok = getattr(result, "cleanup_ok", None)
    if callable(cleanup_ok):
        try:
            cleanup_ok = result.cleanup_ok
        except Exception:
            cleanup_ok = None
    lines.append(f"- Cleanup verified: `{bool(cleanup_ok)}`")
    baseline = getattr(result, "baseline_passed", None)
    regression = getattr(result, "regression_passed", None)
    if baseline is not None or regression is not None:
        lines.append(
            f"- Checks: baseline `{'passed' if baseline else 'failed'}` / "
            f"regression `{'passed' if regression else 'failed'}`"
        )
    cycle_reports = getattr(result, "cycle_reports", None) or []
    if cycle_reports:
        counts: dict[str, int] = {}
        for cycle in cycle_reports:
            key = str(getattr(cycle, "status", "unknown"))
            counts[key] = counts.get(key, 0) + 1
        breakdown = ", ".join(f"{num} {name}" for name, num in sorted(counts.items()))
        lines.append(f"- Cycles: `{len(cycle_reports)}` total ({breakdown})")
    lines.append("")
    lines.append("## Token and cost breakdown")
    lines.append("")
    lines.append("| Role | Model | Prompt | Cached | Completion | Reasoning | Seconds | Cost USD |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
    usage = getattr(result, "usage", None)
    calls = getattr(usage, "calls", []) if usage is not None else []
    for call in calls:
        role = getattr(call, "role", "") or "?"
        model = getattr(call, "model", "")
        prompt = getattr(call, "prompt_tokens", 0)
        cached = getattr(call, "cached_tokens", 0)
        completion = getattr(call, "completion_tokens", 0)
        reasoning = getattr(call, "reasoning_tokens", 0)
        seconds = getattr(call, "seconds", 0.0)
        cost = getattr(call, "cost_usd", None)
        cost_str = "unknown" if cost is None else f"{cost:.4f}"
        lines.append(
            f"| {role} | {model} | {prompt} | {cached} | {completion} | {reasoning} | {seconds:.1f} | {cost_str} |"
        )
    total_tokens = getattr(result, "total_tokens", 0)
    total_cost = getattr(result, "cost_usd", getattr(result, "total_cost_usd", None))
    total_str = "unknown" if total_cost is None else f"${total_cost:.4f}"
    total_seconds = sum(float(getattr(call, "seconds", 0.0) or 0.0) for call in calls)
    lines.append(f"| total |  |  |  |  |  | {total_seconds:.1f} | {total_str} |")
    lines.append(
        f"Total tokens: {total_tokens}, model latency: {total_seconds:.1f}s, "
        f"estimated cost: {total_str}"
    )
    lines.append("")
    lines.append("## Red team findings")
    lines.append("")
    finding = getattr(result, "finding", None)
    if finding is not None:
        lines.append(f"- Vulnerability: {getattr(finding, 'vulnerability_class', '')}")
        lines.append(f"- Sink: {getattr(finding, 'sink_location', '')}")
        lines.append(f"- Analysis: {getattr(finding, 'analysis_summary', '')}")
    else:
        # Project workflow cycle reports
        cycles = getattr(result, "cycle_reports", []) or []
        if cycles:
            for c in cycles:
                status_c = getattr(c, "status", "")
                msg = getattr(c, "message", "")
                cycle_no = getattr(c, "cycle", "?")
                pass_no = getattr(c, "pass_number", "?")
                lines.append(f"- Cycle {cycle_no} pass {pass_no}: {status_c} — {msg}")
        else:
            lines.append("- No structured findings recorded.")
    pre = getattr(result, "pre_exit_code", None)
    post = getattr(result, "post_exit_code", None)
    if pre is not None or post is not None:
        lines.append(f"- Pre/post probe exit codes: {pre} / {post}")
        lines.append(
            "- Before/after: `0` boundary reached, `1` blocked, other/inconclusive needs review"
        )
    lines.append("")
    lines.append("## Blue team sanitization")
    lines.append("")
    patch = getattr(result, "patch", None)
    if patch is not None:
        lines.append(f"- Strategy: {getattr(patch, 'sanitization_strategy', '')}")
    else:
        lines.append("- Strategy: see cycle reports for retained/rolled-back replacements.")
    diff = getattr(result, "diff", None) or getattr(result, "cumulative_diff", "")
    if diff:
        lines.append("")
        lines.append("```diff")
        lines.append(diff[:20000])
        lines.append("```")
    else:
        lines.append("- No candidate diff retained.")
    # Wave 2 items 1/2/4: receipt + guard rationales + mutation probes.
    try:
        from sms_cli import format_wave2_facts as _w2v2_facts

        wave2 = _w2v2_facts(result)
    except Exception:
        wave2 = {}
    if wave2.get("receipt") not in (None, "Not reported", ""):
        lines.append("")
        lines.append("## Verdict receipt")
        lines.append("")
        lines.append(f"- {wave2['receipt']}")
    if wave2.get("guard_rationales") not in (None, "Not reported", ""):
        lines.append("")
        lines.append("## Guard rationales")
        lines.append("")
        lines.append(f"- {wave2['guard_rationales']}")
    if wave2.get("mutations") not in (None, "Not reported", ""):
        lines.append("")
        lines.append("## Mutation probes")
        lines.append("")
        lines.append(f"- {wave2['mutations']}")
    lines.append("")
    lines.append(NOTICE)
    lines.append(LICENSE_URL)
    lines.append("")
    return "\n".join(lines)


def _health_report(settings: PurpleBoxConfig) -> dict:
    """Readiness snapshot for --health (table or redacted JSON). Never raises."""
    try:
        settings.validate()
    except ConfigurationError as exc:
        return {"status": "configuration_error", "message": str(exc)}
    try:
        profiles = {
            key: {
                "label": profile.label,
                "description": profile.description,
                "red_model": profile.red_model,
                "blue_model": profile.blue_model,
            }
            for key, profile in available_profiles(settings).items()
        }
    except Exception:
        profiles = {}
    try:
        scan_profiles = [
            {
                "key": profile.key,
                "label": profile.label,
                "cycles": profile.cycles,
                "description": profile.description,
            }
            for profile in SCAN_PROFILES.values()
        ]
    except Exception:
        scan_profiles = []
    try:
        docker_report = docker_status(settings)
    except Exception:
        docker_report = {"state": "unavailable", "missing_images": [], "leftover_containers": 0}
    return {
        "status": "ok",
        "version": APP_VERSION,
        "api_key_configured": bool(settings.meta_api_key),
        "inference_mode": settings.inference_mode,
        "inference_ready": settings.inference_mode == "local" or bool(settings.meta_api_key),
        "red_model": settings.red_team_model,
        "blue_model": settings.blue_team_model,
        "profiles": profiles,
        "default_profile": default_profile(settings),
        "scan_profiles": scan_profiles,
        "docker": docker_report,
        "busy": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Secure Mitigation System — local Muse boundary verification scaffold",
        epilog=CAPABILITIES_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument(
        "--init-images", action="store_true", help="Build the two base images (requires Docker)"
    )
    commands.add_argument(
        "--rebuild-images", action="store_true", help="Force a fresh rebuild of both base images"
    )
    commands.add_argument(
        "--docker-status", action="store_true", help="Report Docker daemon and image readiness"
    )
    commands.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove leftover Secure Mitigation System session resources",
    )
    commands.add_argument("--serve", action="store_true", help="Serve the local dashboard")
    commands.add_argument(
        "--tui",
        action="store_true",
        help="Live terminal UI: panes, pipeline, result card (curses; degrades to plain text without a TTY); h shows Wave 2/5/8 same-day value, receipt/guard/mutation tokens inline",
    )
    commands.add_argument(
        "--scan",
        choices=list(TARGETS_REGISTRY),
        help="Scan one bundled fixture; result card shows receipt, guard rationales, mutation probes",
    )
    commands.add_argument(
        "--project",
        type=Path,
        help="Scan a local source directory without modifying it; patches stay template-shaped inside the small-edit guard",
    )
    commands.add_argument(
        "--list-targets", action="store_true", help="List bundled fixtures without Docker or a key"
    )
    commands.add_argument(
        "--health",
        action="store_true",
        help="Report readiness (models, profiles, Docker) without Docker or a key",
    )
    commands.add_argument(
        "--ai-demo",
        action="store_true",
        help="AI-built demo mode: Muse designs a novel vulnerable demo project from threat intel, then red/blue teams exercise it in Docker",
    )
    commands.add_argument(
        "--mcp-snippet",
        type=Path,
        help="Verify one source snippet file through the red/blue Docker loop and print the VerdictReceipt JSON (MCP submit_code_snippet over CLI)",
    )
    commands.add_argument(
        "--mcp",
        action="store_true",
        help="MCP STDIO transport: read JSON-RPC requests on stdin, write responses on stdout (tools: submit_code_snippet, sms_scan_source, sms_scan_binary, sms_query_vault_stats, sms_verify_receipt)",
    )
    commands.add_argument(
        "--binary-target",
        type=Path,
        help="Sweep one compiled binary (ELF/Mach-O/PE) through the trusted harness and 3-pass Docker loop; prints the mitigation report JSON",
    )
    parser.add_argument(
        "--snippet-language",
        choices=["javascript", "python", "php"],
        default=None,
        help="Snippet language for --mcp-snippet (default: inferred from file extension)",
    )
    parser.add_argument(
        "--sweep-passes",
        type=int,
        default=None,
        help="Multi-pass sweep depth for --scan: run the first N red/blue passes (1=standard, 2=+deep, 3=+threat-actor; default 1, single finding loop)",
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--image", help="Already-loaded runtime image containing offline dependencies"
    )
    parser.add_argument("--command", help='Target argv as JSON, e.g. ["python3", "app.py"]')
    parser.add_argument(
        "--test-command", help='Trusted regression argv as JSON, e.g. ["python3", "-m", "unittest"]'
    )
    parser.add_argument(
        "--contract", default="", help="Expected behavior and sanitization-only patch constraints"
    )
    parser.add_argument(
        "--scan-profile",
        choices=[*SCAN_PROFILES, "custom"],
        default="custom",
        help="Project scan intensity, independent of --profile models (default: custom)",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=None,
        help="Explicit custom red/blue cycles, 1 to 20 (legacy default: 1)",
    )
    parser.add_argument(
        "--red-agents", type=int, default=5, help="Red agent team size, 1 to 12 (default: 5)"
    )
    parser.add_argument(
        "--blue-agents", type=int, default=5, help="Blue agent team size, 1 to 12 (default: 5)"
    )
    parser.add_argument(
        "--context-budget", type=int, default=32768, help="Bounded per-call source context budget"
    )
    parser.add_argument(
        "--allow-remote-inference",
        action="store_true",
        help="Consent to send project source/evidence to the configured hosted Muse endpoint",
    )
    parser.add_argument(
        "--profile",
        choices=["economy", "balanced", "quality", "custom"],
        help="Model profile for --scan (default: configured models)",
    )
    parser.add_argument(
        "--cve-scan",
        action="store_true",
        help="Run deep static+CVE scan (OSV lookup) instead of probe/patch verification; KEV/EPSS carry freshness stamps",
    )
    parser.add_argument(
        "--deep-assessment",
        action="store_true",
        help="Add Muse triage of static signals and CVE context (requires key/local inference)",
    )
    parser.add_argument(
        "--offline-cve",
        action="store_true",
        help="Skip OSV network lookup; static signals only",
    )
    parser.add_argument(
        "--fast-lane",
        action="store_true",
        help="CVE disclosure fast lane: static + OSV only, deterministic order, no Muse/NVD; topping lists most reachable+fixable first, signals older than 1 day show as stale",
    )
    parser.add_argument(
        "--build-brief",
        default="",
        help="What the AI demo should build (bounded to 500 chars; flows into intent parsing)",
    )
    parser.add_argument(
        "--vulns",
        default="",
        help="Requested demo flaws: CVE IDs, named types, or free text (comma-separated)",
    )
    parser.add_argument(
        "--intel-theme",
        default="input validation SQL injection XSS deserialization",
        help="Threat-intel themes for AI demo generation (space-separated NVD keywords)",
    )
    parser.add_argument(
        "--intel-offline",
        action="store_true",
        help="Generate AI demo without live NVD lookup (uses static flaw patterns)",
    )
    parser.add_argument(
        "--demo-size",
        choices=["small", "standard"],
        default="standard",
        help="Greenhouse demo size: small (fewer routes) or standard (full set)",
    )
    parser.add_argument(
        "--flaw-count",
        type=int,
        default=None,
        help="Bound the requested demo flaws to 1..8 (default: keep them all; clamps)",
    )
    parser.add_argument(
        "--demo-seed",
        type=int,
        default=None,
        help="Variation nonce for AI demo generation (reproducibility hint)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="TOML or JSON file with an [sms] table of CLI defaults "
        "(flag > config > env > default; unknown keys error)",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Non-interactive output shape: human-readable tables (default) or redacted JSON; tables show guard rationales and mutation probes",
    )
    parser.add_argument(
        "--show-usage",
        action="store_true",
        help="Always print the token/cost table even when no model calls were made",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Save scan JSON and candidate diff to a new run directory (includes receipt.json sandbox proof)",
    )
    parser.add_argument(
        "--research",
        action="store_true",
        help="Opt-in research sidecars for --scan: red/blue Muse research agents "
        "grounded in keyless public intel (OSV/CIRCL/GHSA/EPSS). Off by default; "
        "extra model calls, no sandbox contact, Docker evidence still decides.",
    )
    parser.add_argument(
        "--research-scanners",
        default="",
        help="Comma-separated local scanners to run as extra research grounding "
        "(trivy,grype,osv-scanner,dependency-check,dependency-track). Requires "
        "--research; binaries run on the host, each absent tool is skipped.",
    )
    args = parser.parse_args()
    # --config defaults (flag > config > env > default), unknown keys error.
    file_values: dict = {}
    if args.config is not None:
        try:
            file_values = load_config_file(args.config)
        except LoadError as exc:
            parser.error(str(exc))
    defaults = {
        "profile": None,
        "scan_profile": "custom",
        "cycles": None,
        "red_agents": 5,
        "blue_agents": 5,
        "context_budget": 32768,
        "intel_theme": "input validation SQL injection XSS deserialization",
        "intel_offline": False,
        "build_brief": "",
        "vulns": "",
        "demo_size": "standard",
        "flaw_count": None,
        "demo_seed": None,
        "research": False,
        "research_scanners": "",
        "allow_remote_inference": False,
        "offline_cve": False,
        "deep_assessment": False,
        "fast_lane": False,
        "output_dir": None,
        "port": 8000,
        "format": "table",
    }
    flag_values: dict = {}
    for key in defaults:
        value = getattr(args, key)
        if value != defaults[key]:
            flag_values[key] = value
    merged = merge_config(None, file_values, flag_values)
    for key, value in merged.items():
        if key == "output_dir" and value is not None:
            value = Path(value)
        setattr(args, key, value)
    out_format = args.format
    with_config = f" (config: {args.config})" if args.config is not None else ""
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.profile is not None and not (args.scan or args.project or args.ai_demo):
        parser.error("--profile requires --scan, --project, or --ai-demo")
    if args.output_dir is not None and not (
        args.scan or args.project or args.ai_demo or args.binary_target
    ):
        parser.error("--output-dir requires --scan, --project, --ai-demo, or --binary-target")
    # --research/--research-scanners run on every scan surface: fixture, project, ai-demo.
    if args.research and not (args.scan or args.project or args.ai_demo):
        parser.error("--research requires --scan, --project, or --ai-demo")
    if args.research_scanners and not args.research:
        parser.error("--research-scanners requires --research")
    if args.project and (not args.command or not args.test_command or not args.contract):
        parser.error("--project requires --command, --test-command, and --contract")
    if args.ai_demo and args.scan:
        parser.error("--ai-demo cannot be combined with --scan; it generates its own project")
    if args.build_brief and not args.ai_demo:
        parser.error("--build-brief requires --ai-demo")
    if args.vulns and not args.ai_demo:
        parser.error("--vulns requires --ai-demo")
    if args.intel_theme != defaults["intel_theme"] and not args.ai_demo:
        parser.error("--intel-theme requires --ai-demo")
    if args.intel_offline and not args.ai_demo:
        parser.error("--intel-offline requires --ai-demo")
    if args.demo_size != defaults["demo_size"] and not args.ai_demo:
        parser.error("--demo-size requires --ai-demo")
    if args.flaw_count is not None and not args.ai_demo:
        parser.error("--flaw-count requires --ai-demo")
    if args.demo_seed is not None and not args.ai_demo:
        parser.error("--demo-seed requires --ai-demo")
    if args.sweep_passes is not None and not args.scan:
        parser.error("--sweep-passes requires --scan")
    if args.sweep_passes is not None and not 1 <= args.sweep_passes <= 3:
        parser.error("--sweep-passes must be between 1 and 3")
    # Intensity validation: hard errors for invalid bounds, warnings for heavy-but-valid.
    if args.cycles is not None and not 1 <= args.cycles <= 20:
        parser.error("--cycles must be between 1 and 20")
    if not 1 <= args.red_agents <= 12:
        parser.error("--red-agents must be between 1 and 12")
    if not 1 <= args.blue_agents <= 12:
        parser.error("--blue-agents must be between 1 and 12")
    if not 1024 <= args.context_budget <= 131072:
        parser.error("--context-budget must be between 1024 and 131072")
    intensity_warnings: list[str] = []
    if args.red_agents + args.blue_agents >= 20:
        intensity_warnings.append(
            f"warning: {args.red_agents + args.blue_agents} total agents "
            "(red + blue) will make many model calls; expect cost and latency."
        )
    if args.context_budget >= 65536:
        intensity_warnings.append(
            f"warning: --context-budget {args.context_budget} is large; "
            "expect higher token usage per call."
        )
    if args.red_agents >= 10 or args.blue_agents >= 10:
        intensity_warnings.append(
            "warning: team size >= 10 is heavy; consider a named scan profile."
        )
    if (
        not args.project
        and not args.ai_demo
        and not args.mcp_snippet
        and not args.mcp
        and not args.binary_target
        and (
            args.image
            or args.command
            or args.test_command
            or args.contract
            or args.scan_profile != "custom"
            or args.cycles is not None
            or args.allow_remote_inference
            or args.cve_scan
            or args.deep_assessment
            or args.offline_cve
            or args.fast_lane
        )
    ):
        parser.error("Project options require --project (ai-demo carries its own intensity flags)")
    try:
        if args.list_targets:
            for key, target in TARGETS_REGISTRY.items():
                print(f"{key}: {target.description}")
            return 0
        settings = load_config()
        if args.health:
            report = _health_report(settings)
            if out_format == "json":
                # LAW 4: readiness booleans only; keys and model internals never print.
                safe = {
                    "status": report["status"],
                    "version": report.get("version", APP_VERSION),
                    "inference_mode": report["inference_mode"],
                    "inference_ready": report["inference_ready"],
                    "api_key_configured": report["api_key_configured"],
                    "red_model": report["red_model"],
                    "blue_model": report["blue_model"],
                    "profiles": report["profiles"],
                    "scan_profiles": report["scan_profiles"],
                    "docker": report["docker"],
                    "busy": report["busy"],
                }
                print(json.dumps(safe, indent=2))
            else:
                print(health_table(report))
            return 0 if report["status"] == "ok" else 1
        for warning in intensity_warnings:
            print(warning, file=sys.stderr)
        if file_values:
            print(
                f"[SYSTEM] Loaded CLI defaults from {args.config}{with_config and ''}", flush=True
            )
        if args.init_images:
            with DockerSandboxManager(settings) as manager:
                manager.ensure_base_images()
            print("Base images ready.")
            return 0
        if args.rebuild_images:
            for tag in build_base_images(settings):
                print(f"Rebuilt {tag}")
            return 0
        if args.docker_status:
            report = docker_status(settings)
            print(json.dumps(report, indent=2))
            return 0 if report["state"] == "ready" else 1
        if args.cleanup:
            removed = remove_stale_resources(settings)
            print("Removed " + ", ".join(f"{count} {kind}" for kind, count in removed.items()))
            return 0
        if args.serve:
            uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port, ws_max_size=65536)
            return 0
        if args.tui:
            from tui import main as _tui_main

            return _tui_main([])
        if args.mcp:
            return mcp_stdio_runner()
        if args.mcp_snippet:
            return asyncio.run(
                mcp_snippet_runner(
                    args.mcp_snippet,
                    language=args.snippet_language,
                    contract=args.contract,
                    output_dir=args.output_dir,
                    out_format=out_format,
                    show_usage=args.show_usage,
                )
            )
        if args.binary_target:
            candidate = Path(str(args.binary_target))
            if candidate.name == "binary_argv_echo" and not candidate.exists():
                bundled = Path(__file__).resolve().parent / "targets" / "binary_argv_echo" / "echo"
                if bundled.exists():
                    args.binary_target = bundled
            return asyncio.run(
                binary_sweep_runner(
                    args.binary_target,
                    contract=args.contract,
                    max_passes=3,
                    output_dir=args.output_dir,
                    out_format=out_format,
                    show_usage=args.show_usage,
                )
            )
        if args.scan:
            return asyncio.run(
                cli_runner(
                    args.scan,
                    args.output_dir,
                    args.profile,
                    args.research,
                    args.research_scanners,
                    out_format=out_format,
                    show_usage=args.show_usage,
                    sweep_passes=args.sweep_passes,
                )
            )
        if args.ai_demo:
            return asyncio.run(
                ai_demo_runner(
                    args.output_dir or Path("reports"),
                    args.profile,
                    scan_profile=args.scan_profile,
                    cycles=args.cycles,
                    red_agents=args.red_agents,
                    blue_agents=args.blue_agents,
                    intel_theme=args.intel_theme,
                    intel_offline=args.intel_offline,
                    build_brief=args.build_brief,
                    vulns=args.vulns,
                    research=args.research,
                    research_scanners=args.research_scanners,
                    allow_remote_inference=args.allow_remote_inference,
                    demo_size=args.demo_size,
                    flaw_count=(
                        None if args.flaw_count is None else max(1, min(8, args.flaw_count))
                    ),
                    demo_seed=args.demo_seed,
                    out_format=out_format,
                    show_usage=args.show_usage,
                )
            )
        if args.project:
            try:
                project_values = {
                    "path": str(args.project.absolute()),
                    "image": args.image or settings.target_base_image,
                    "command": json.loads(args.command),
                    "test_command": json.loads(args.test_command),
                    "contract": args.contract,
                    "scan_profile": args.scan_profile,
                    "red_agents": args.red_agents,
                    "blue_agents": args.blue_agents,
                    "context_budget": args.context_budget,
                    "allow_remote_inference": args.allow_remote_inference,
                }
                if args.cycles is not None:
                    project_values["cycles"] = args.cycles
                elif args.scan_profile == "custom":
                    project_values["cycles"] = 1
                spec = ProjectSpec.model_validate(project_values)
            except ValueError:
                parser.error(
                    "Invalid project settings. Use JSON argv arrays and valid cycle/context limits."
                )
            # Consent parity with the dashboard: hosted inference moves project
            # source to Muse, so --allow-remote-inference is required. The
            # dashboard enforces the same rule via the allow-remote checkbox.
            # Spec validation runs first so argparse errors (exit 2) precede
            # the runtime consent failure (exit 1).
            if settings.inference_mode != "local" and not args.allow_remote_inference:
                from modules.workflows.project_workflow import ProjectWorkflowError as _ConsentError

                raise _ConsentError(
                    "Remote inference consent is required before project source "
                    "can be sent to Muse. Re-run with --allow-remote-inference."
                )
            return asyncio.run(
                cli_runner(
                    None,
                    args.output_dir or Path("reports"),
                    args.profile,
                    args.research,
                    args.research_scanners,
                    project=spec,
                    cve_scan=args.cve_scan,
                    deep_assessment=args.deep_assessment,
                    offline_cve=args.offline_cve,
                    fast_lane=args.fast_lane,
                    out_format=out_format,
                    show_usage=args.show_usage,
                )
            )
        # No command given: serve, same as --serve (kept so bare `python main.py` still opens the dashboard).
        uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port, ws_max_size=65536)
        return 0
    except KeyboardInterrupt:
        print("Interrupted; cleanup was requested.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(
            f"Secure Mitigation System could not start ({type(exc).__name__}). Check configuration and Docker availability.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
