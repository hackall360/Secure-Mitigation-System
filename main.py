# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Local UI and CLI for the same Secure Mitigation System workflow."""

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from config import ConfigurationError, PurpleBoxConfig, load_config
from cve_workflow import execute_cve_scan
from docker_manager import (
    DockerSandboxManager,
    build_base_images,
    docker_status,
    remove_stale_resources,
)
from profiles import ProfileError, apply_profile, available_profiles, default_profile
from project_workflow import execute_project_workflow, redact_report_for_user
from projects import ProjectSpec
from registry import BASE_DIR, TARGETS_REGISTRY
from scan_profiles import SCAN_PROFILES
from workflow import execute_purple_workflow, redact_fixture_result_for_user

NOTICE = "Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use."
LICENSE_URL = "https://polyformproject.org/licenses/noncommercial/1.0.0"


def create_app(config: PurpleBoxConfig | None = None) -> FastAPI:
    application = FastAPI(
        title="Secure Mitigation System", version="0.1.0", docs_url=None, redoc_url=None
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
            target_key is not None and target_key not in TARGETS_REGISTRY
        ):
            await socket.close(code=1008)
            return
        # The profile is a fixed key, never a model ID. Unknown keys are refused before
        # any Docker or API work starts.
        try:
            scan_config = apply_profile(config or load_config(), socket.query_params.get("profile"))
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

        async def emit(team: str, message: str):
            await socket.send_json({"team": team, "msg": message, "type": "log"})

        async def disconnected():
            try:
                while True:
                    event = await socket.receive()
                    if event["type"] == "websocket.disconnect":
                        return
            except (WebSocketDisconnect, RuntimeError):
                return

        async with lock:
            if target_key is None:
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
            else:
                coroutine = execute_purple_workflow(target_key, emit, config=scan_config)
            run = asyncio.create_task(coroutine)
            disconnect = asyncio.create_task(disconnected())
            try:
                done, _ = await asyncio.wait({run, disconnect}, return_when=asyncio.FIRST_COMPLETED)
                if run in done:
                    result = await run
                    safe = result.model_dump()
                    try:
                        from project_workflow import redact_report_for_user as _redact_proj
                        from workflow import redact_fixture_result_for_user as _redact_fixt

                        if target_key is None:
                            safe = _redact_proj(result)
                        else:
                            safe = _redact_fixt(result)
                    except Exception:
                        pass
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

    return application


app = create_app()


async def ai_demo_runner(
    output_dir: Path,
    profile: str | None = None,
    *,
    scan_profile: str = "extra_light",
    red_agents: int = 5,
    blue_agents: int = 5,
    intel_theme: str = "input validation SQL injection XSS deserialization",
    intel_offline: bool = False,
) -> int:
    """AI-built demo mode: intel-grounded generation, then evidence-gated red/blue in Docker."""
    from agents import MetaMuseClient
    from config import load_config as _load
    from demo_gen import generate_demo_project, materialize_demo_project
    from intel_search import intel_for_demo
    from profiles import apply_profile as _apply

    settings = _apply(_load(), profile)

    async def emit(team: str, message: str):
        print(f"[{team.upper():6}] {message}", flush=True)

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
    muse = MetaMuseClient(settings)
    try:
        files = await generate_demo_project(muse, intel_context=intel, theme=" ".join(themes))
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
    # Enrich ProjectSpec with requested intensity/team sizes.
    from projects import ProjectSpec as _Spec

    spec = _Spec.model_validate(
        {
            **spec.model_dump(mode="json"),
            "scan_profile": scan_profile,
            "red_agents": red_agents,
            "blue_agents": blue_agents,
        }
    )
    return await cli_runner(None, output_dir, profile, project=spec)


async def cli_runner(
    target_key: str | None,
    output_dir: Path | None = None,
    profile: str | None = None,
    *,
    project: ProjectSpec | None = None,
    cve_scan: bool = False,
    deep_assessment: bool = False,
    offline_cve: bool = False,
) -> int:
    async def emit(team: str, message: str):
        print(f"[{team.upper():6}] {message}", flush=True)

    settings = apply_profile(load_config(), profile)
    print(
        f"[SYSTEM] Models: red {settings.red_team_model}, blue {settings.blue_team_model}",
        flush=True,
    )
    if project is not None and cve_scan:
        cve_result = await execute_cve_scan(
            project,
            emit,
            config=settings,
            include_osv=not offline_cve,
            include_deep_assessment=deep_assessment,
            include_nvd=True,
        )
        print(f"[SYSTEM] {cve_result.message}", flush=True)
        for vuln in cve_result.vulnerabilities[:20]:
            cves = ",".join(vuln.get("cves") or [vuln.get("id", "")])
            print(f"[CVE    ] {cves}: {(vuln.get('summary') or '')[:160]}", flush=True)
        if output_dir is not None:
            import uuid as _uuid
            from datetime import datetime as _dt
            from datetime import timezone as _tz

            run_dir = output_dir / f"{_dt.now(_tz.utc):%Y%m%dT%H%M%SZ}-{_uuid.uuid4().hex[:8]}"
            run_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
            report = {"notice": NOTICE, "license_url": LICENSE_URL, **cve_result.model_dump()}
            (run_dir / "report.json").write_text(
                __import__("json").dumps(report, indent=2) + "\n", encoding="utf-8"
            )
            (run_dir / "report.json").chmod(0o600)
            summary = _build_cve_summary_markdown(project, settings, cve_result)
            (run_dir / "SUMMARY.md").write_text(summary, encoding="utf-8")
            (run_dir / "SUMMARY.md").chmod(0o600)
            print(f"[SYSTEM] Report: {run_dir / 'report.json'}")
        return 0 if cve_result.success else 1
    if project is None:
        result = await execute_purple_workflow(target_key, emit, config=settings)
        user_report = redact_fixture_result_for_user(result)
    else:
        result = await execute_project_workflow(project, emit, config=settings)
        user_report = redact_report_for_user(result)
    for call in result.usage.calls:
        cost = "price unknown" if call.cost_usd is None else f"${call.cost_usd:.4f}"
        print(
            f"[USAGE ] {call.role or '?'} {call.model}: {call.prompt_tokens} in, "
            f"{call.completion_tokens} out ({call.reasoning_tokens} reasoning), "
            f"{call.seconds:.1f}s, {cost}",
            flush=True,
        )
    if result.usage.calls:
        total = "unknown" if result.cost_usd is None else f"${result.cost_usd:.4f}"
        print(f"[USAGE ] total {result.total_tokens} tokens, estimated cost {total}", flush=True)
    if output_dir is not None:
        # A fresh per-run directory prevents accidental overwriting of previous results.
        run_dir = output_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        run_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
        report = {"notice": NOTICE, "license_url": LICENSE_URL, **user_report}
        (run_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (run_dir / "report.json").chmod(0o600)
        if result.diff:
            (run_dir / "candidate.patch").write_text(result.diff, encoding="utf-8")
            (run_dir / "candidate.patch").chmod(0o600)
        summary = _build_summary_markdown(target_key, project, settings, result)
        (run_dir / "SUMMARY.md").write_text(summary, encoding="utf-8")
        (run_dir / "SUMMARY.md").chmod(0o600)
        print(f"[SYSTEM] Report: {run_dir / 'report.json'}")
    return 0 if result.success else 1


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
    if result.deep_assessment:
        lines.append("")
        lines.append("## Muse deep assessment (advisory)")
        lines.append(str(result.deep_assessment.get("assessment", ""))[:8000])
    if result.errors:
        lines.append("")
        lines.append("## Lookup warnings")
        for err in result.errors[:20]:
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
    lines.append(f"| total |  |  |  |  |  |  | {total_str} |")
    lines.append(f"Total tokens: {total_tokens}, estimated cost: {total_str}")
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
    lines.append("")
    lines.append(NOTICE)
    lines.append(LICENSE_URL)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Secure Mitigation System — local Muse boundary verification scaffold"
    )
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
    commands.add_argument("--scan", choices=list(TARGETS_REGISTRY), help="Scan one bundled fixture")
    commands.add_argument(
        "--project", type=Path, help="Scan a local source directory without modifying it"
    )
    commands.add_argument(
        "--list-targets", action="store_true", help="List bundled fixtures without Docker or a key"
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
        help="Run deep static+CVE scan (OSV lookup) instead of probe/patch verification",
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
        "--ai-demo",
        action="store_true",
        help="AI-built demo mode: Muse designs a novel vulnerable demo project from threat intel, then red/blue teams exercise it in Docker",
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
        "--output-dir", type=Path, help="Save scan JSON and candidate diff to a new run directory"
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.profile is not None and not (args.scan or args.project):
        parser.error("--profile requires --scan or --project")
    if args.output_dir is not None and not (args.scan or args.project):
        parser.error("--output-dir requires --scan or --project")
    if args.project and (not args.command or not args.test_command or not args.contract):
        parser.error("--project requires --command, --test-command, and --contract")
    if args.ai_demo and args.scan:
        parser.error("--ai-demo cannot be combined with --scan; it generates its own project")
    if not args.project and (
        args.image
        or args.command
        or args.test_command
        or args.contract
        or args.scan_profile != "custom"
        or args.cycles is not None
        or args.red_agents != 5
        or args.blue_agents != 5
        or args.context_budget != 32768
        or args.allow_remote_inference
        or args.cve_scan
        or args.deep_assessment
        or args.offline_cve
    ):
        parser.error("Project options require --project")
    try:
        if args.list_targets:
            for key, target in TARGETS_REGISTRY.items():
                print(f"{key}: {target.description}")
            return 0
        settings = load_config()
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
        if args.scan:
            return asyncio.run(cli_runner(args.scan, args.output_dir, args.profile))
        if args.ai_demo:
            return asyncio.run(
                ai_demo_runner(
                    args.output_dir or Path("reports"),
                    args.profile,
                    scan_profile=args.scan_profile,
                    red_agents=args.red_agents,
                    blue_agents=args.blue_agents,
                    intel_theme=args.intel_theme,
                    intel_offline=args.intel_offline,
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
            return asyncio.run(
                cli_runner(
                    None,
                    args.output_dir or Path("reports"),
                    args.profile,
                    project=spec,
                    cve_scan=args.cve_scan,
                    deep_assessment=args.deep_assessment,
                    offline_cve=args.offline_cve,
                )
            )
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
