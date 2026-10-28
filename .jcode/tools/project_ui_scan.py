#!/usr/bin/env python3
# Serve a generated project and loopback Muse HTTP test endpoint for real-browser Docker acceptance.
# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Test-only server. No API credentials or external inference. Stop after browser acceptance."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ruff: noqa: E402
import httpx
import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse
from project_scan import ORIGINAL, create_project, fake_transport

import main
from config import PurpleBoxConfig
from project_workflow import execute_project_workflow


def serve(port: int, output: Path):
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="browser-project-", dir=output) as directory:
        project = Path(directory)
        create_project(project)
        config = PurpleBoxConfig(
            inference_mode="local", meta_base_url=f"http://127.0.0.1:{port}/v1"
        )

        async def record(spec, emit, **kwargs):
            result = await execute_project_workflow(spec, emit, **kwargs)
            assert (project / "src/boundaries.py").read_text() == ORIGINAL
            report = output / "browser-report.json"
            report.write_text(json.dumps(result.model_dump(), indent=2) + "\n")
            report.chmod(0o600)
            return result

        main.execute_project_workflow = record
        app = main.create_app(config)

        @app.post("/v1/chat/completions")
        async def deterministic_muse(request: Request):
            body = await request.body()
            response = fake_transport(httpx.Request("POST", str(request.url), content=body))
            return JSONResponse(response.json())

        print(
            json.dumps(
                {
                    "url": f"http://localhost:{port}/",
                    "path": str(project),
                    "image": config.target_base_image,
                    "command": ["python3", "app.py"],
                    "test_command": ["python3", "test_contract.py"],
                    "contract": "HTTP service at target-service:8080. Preserve lookup 101=Alice, 102=Bob, 999 empty and echo decimal input. Only sanitize input.",
                    "cycles": 2,
                    "context_budget": 32768,
                }
            ),
            flush=True,
        )
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def main_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8798)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "reports" / "browser-project-acceptance"
    )
    args = parser.parse_args()
    serve(args.port, args.output_dir.resolve())


if __name__ == "__main__":
    main_cli()
