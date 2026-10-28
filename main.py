# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Local UI and CLI for the same PurpleBox workflow."""

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
from docker_manager import (
    DockerSandboxManager,
    build_base_images,
    docker_status,
    remove_stale_resources,
)
from registry import BASE_DIR, TARGETS_REGISTRY
from workflow import execute_purple_workflow

NOTICE = (
    "Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use."
)
LICENSE_URL = "https://polyformproject.org/licenses/noncommercial/1.0.0"


def create_app(config: PurpleBoxConfig | None = None) -> FastAPI:
    application = FastAPI(title="PurpleBox", version="0.1.0", docs_url=None, redoc_url=None)
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
                "red_model": settings.red_team_model,
                "blue_model": settings.blue_team_model,
                "docker": await asyncio.to_thread(docker_status, settings),
                "busy": application.state.scan_lock.locked(),
            }
        except ConfigurationError as exc:
            return JSONResponse(
                {"status": "configuration_error", "message": str(exc)}, status_code=503
            )

    @application.websocket("/ws/combat/{target_key}")
    async def combat(socket: WebSocket, target_key: str):
        # Host validation plus exact same-origin validation prevents drive-by browser scans.
        expected_origin = (
            f"{'https' if socket.url.scheme == 'wss' else 'http'}://{socket.headers.get('host')}"
        )
        if socket.headers.get("origin") != expected_origin or target_key not in TARGETS_REGISTRY:
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
            run = asyncio.create_task(execute_purple_workflow(target_key, emit, config=config))
            disconnect = asyncio.create_task(disconnected())
            try:
                done, _ = await asyncio.wait({run, disconnect}, return_when=asyncio.FIRST_COMPLETED)
                if run in done:
                    result = await run
                    await socket.send_json({"type": "result", **result.model_dump()})
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

    return application


app = create_app()


async def cli_runner(target_key: str, output_dir: Path | None = None) -> int:
    async def emit(team: str, message: str):
        print(f"[{team.upper():6}] {message}", flush=True)

    result = await execute_purple_workflow(target_key, emit)
    if output_dir is not None:
        # A fresh per-run directory prevents accidental overwriting of previous results.
        run_dir = output_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        run_dir.mkdir(parents=True, exist_ok=False)
        report = {"notice": NOTICE, "license_url": LICENSE_URL, **result.model_dump()}
        (run_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if result.diff:
            (run_dir / "candidate.patch").write_text(result.diff, encoding="utf-8")
        print(f"[SYSTEM] Report: {run_dir / 'report.json'}")
    return 0 if result.success else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PurpleBox — local Muse boundary verification scaffold"
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
        "--cleanup", action="store_true", help="Remove leftover PurpleBox session resources"
    )
    commands.add_argument("--serve", action="store_true", help="Serve the local dashboard")
    commands.add_argument("--scan", choices=list(TARGETS_REGISTRY), help="Scan one bundled fixture")
    commands.add_argument(
        "--list-targets", action="store_true", help="List bundled fixtures without Docker or a key"
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--output-dir", type=Path, help="Save scan JSON and candidate diff to a new run directory"
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.output_dir is not None and not args.scan:
        parser.error("--output-dir requires --scan")
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
            return asyncio.run(cli_runner(args.scan, args.output_dir))
        uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port)
        return 0
    except KeyboardInterrupt:
        print("Interrupted; cleanup was requested.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(
            f"PurpleBox could not start ({type(exc).__name__}). Check configuration and Docker availability.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
