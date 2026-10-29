# Secure Mitigation System: Autonomous Input-Sanitization & Boundary Verification System
**Technical Specification & AI Agent Bootstrap Document (`SPEC.md`)**

---

## 1. Hackathon Context & Strategic Overview

### 1.1 Event Metadata
* **Event:** Meta Global AI Developer Hackathon (Hosted by Meta & Cerebral Valley)
* **Track:** Indie Developer Track (Evaluated on creativity, technical ambition, and functional execution)
* **Themes Addressed:**
  * *Push the Frontier:* Giving autonomous software engineering systems isolated sandbox verification capabilities.
  * *Build for Your World:* Automating security hygiene and input sanitization without breaking existing application logic.
* **Submission Deadline:** November 4, 2026 at 9:00 PM ET
* **Required Deliverables:**
  1. Working local application (Web UI + CLI).
  2. 2 to 3 minute split-screen demonstration video showing live adversarial verification and sanitization patching.
  3. Public or shared repository containing setup instructions and this specification.
  4. Concise project write-up detailing the problem, target users, and how Meta's Muse models power the workflow.

### 1.2 Product Scope & "Trojan Horse" Boundaries
Secure Mitigation System is a local, containerized Purple-Team orchestration engine designed for solo developers to detect known input-handling weaknesses in local project folders, verify input reachability in an isolated sandbox, and apply surgical **input-sanitization patches**.

To protect commercial intellectual property while delivering a high-impact hackathon demonstration, the system enforces strict architectural boundaries:
1. **Sanitization-Only Patching:** The Blue Team agent is strictly prohibited from refactoring application architecture, changing database schemas, or rewriting business logic. It may only introduce input validation, type casting, allowlist filtering, context-appropriate escaping, parameterized query wrappers, or hardened configuration directives immediately upstream of a vulnerable sink.
2. **Meta Muse Exclusive Inference:** The inference layer exclusively targets Meta's Muse model family (`muse-spark`, `muse-wonder`, `muse-code`) via the Meta Model API (or Meta open-weights endpoints hosted on Baseten/Modal). It requires a valid `META_MUSE_API_KEY` to execute.
3. **Local Single-Node Execution:** The system runs locally via FastAPI (serving a real-time WebSocket split-screen UI) and a companion CLI. It intentionally omits distributed task queues, multi-repo context compression, and CI/CD webhook automation.

---

## 2. Licensing & IP Protection Strategy

### 2.1 License Selection
This repository is governed under the **PolyForm Noncommercial License 1.0.0** (or alternatively **AGPL-3.0-only** if an OSI-approved license is required during submission review).

### 2.2 Summary of License Terms (Non-Verbatim)
* **Permitted Use:** Individual developers, students, academic researchers, and hackathon judges may freely run, inspect, modify, and redistribute the software strictly for personal, educational, or noncommercial research purposes.
* **Commercial Prohibition:** No commercial entity may deploy this codebase in production, offer it as a managed service, or integrate it into internal commercial pipelines without obtaining a separate commercial license from the author.
* **Required Notice:** Every file and distribution must retain the copyright attribution line (`Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.`) and a link to the canonical license URL (`https://polyformproject.org/licenses/noncommercial/1.0.0`).

---

## 3. Container Architecture: Cloneable Base Images & Strict Isolation

To achieve sub-second spin-up times and strict separation between the **Target Service** and the **Verification Runner**, Secure Mitigation System uses pre-built, cloneable local Docker images connected over an ephemeral, air-gapped internal bridge network.

```
+-----------------------------------------------------------------------+
| Host Machine (FastAPI Orchestrator + Meta Muse API Client)            |
|                                                                       |
|  1. Clones pre-built images via Copy-on-Write / Snapshot              |
|  2. Injects target source & verification script via tar archive API   |
|  3. Collects stdout/stderr & streams live traces over WebSockets      |
+-------------------+-----------------------------------+---------------+
                    |                                   |
                    v                                   v
+-----------------------------------------------------------------------+
| Isolated Ephemeral Docker Bridge Network (internal=True, No Internet) |
|                                                                       |
|  +---------------------------------+  +----------------------------+  |
|  | Target Service Container        |  | Verification Container     |  |
|  | Image: purplebox-target-base    |  | Image: secure-mitigation-verifier  |  |
|  | Role: Runs target app (PHP,     |  | Role: Executes safe input  |  |
|  |       Node.js, or MySQL config) |< |       boundary checks      |  |
|  | Caps: DROP ALL, no-new-privs    |  | Caps: DROP ALL, read-only  |  |
|  | RAM: 256MB | CPU: 0.5 Core      |  | RAM: 128MB | CPU: 0.5 Core |  |
|  +---------------------------------+  +----------------------------+  |
+-----------------------------------------------------------------------+
```

### 3.1 Minimal Overhead & Fast Cloning Mechanics
* **Pre-Warmed Golden Images:** During initial setup (`python main.py --init-images`), Docker builds two ultra-lightweight Alpine-based base images (`purplebox-target-base:latest` and `purplebox-verifier-base:latest`).
* **Copy-on-Write Instantiation:** Instead of running `docker build` on every scan, the orchestrator spawns containers directly from the pre-warmed images and injects the target directory into memory using Docker's `put_archive` API (tar stream into `/workspace`).
* **Snapshot Cloning (`container.commit`):** Once a target container is initialized with dependencies, the orchestrator calls `container.commit(repository="purplebox-clone-cache", tag=target_id)` so subsequent post-patch verification runs start instantaneously from the warm snapshot without re-initializing runtimes.
* **Hard Resource Caps:** Every container enforces `mem_limit="256m"`, `memswap_limit="256m"`, `nano_cpus=500_000_000` (0.5 CPU), `pids_limit=64`, `cap_drop=["ALL"]`, and `security_opt=["no-new-privileges:true"]`.
* **Air-Gapped Network:** Both containers attach to a custom Docker bridge network created with `internal=True`. Containers can communicate with each other via container DNS (`http://target-service:8080`), but neither container can reach the host network or the public internet.

---

## 4. Target Repository Structure

When an AI agent expands this specification into a full project, it must maintain the following directory layout:

```text
purplebox/
├── AGENT.md
├── SPEC.md
├── LICENSE.md
├── README.md
├── requirements.txt
├── config.py
├── prompts.py
├── docker_manager.py
├── agents.py
├── main.py
├── static/
│   └── index.html
└── targets/
    ├── node_query_sink/
    │   └── app.js
    ├── php_command_sink/
    │   └── index.php
    └── mysql_insecure_conf/
        └── my.cnf
```

---

## 5. Software Development Flow & AI Agent Guidelines

Any AI coding agent operating on this repository must obey the following engineering rules:

1. **Complete File Generation (Zero Placeholders):** Never output partial files, truncated snippets, or comments such as `// ... rest of code here` or `# TODO: implement later`. Every file written or modified must be 100% complete, syntactically valid, and immediately runnable.
2. **Strict Model Lock:** Do not add fallback providers for OpenAI, Anthropic, or local Ollama models in the application runtime. All runtime LLM calls must pass through the configured Meta Muse API client and fail fast if `META_MUSE_API_KEY` is missing.
3. **Sanitization Diff Discipline:** When refining the Blue Team agent, validate that the returned patched code preserves all original function signatures, route paths, and return structures. Reject patches that delete routes or stub out functionality.
4. **Deterministic Container Cleanup:** Every container and custom bridge network created during a scan session must be wrapped in `try / finally` blocks ensuring `container.remove(force=True)` and `network.remove()` execute even if an exception occurs.

---

## 6. `AGENT.md` Generation Specification

If an AI agent is instructed to initialize the workspace or generate `AGENT.md` files, it must create a root `AGENT.md` (and optional sub-directory `AGENT.md` files inside `targets/`) using the exact template below:

```markdown
# AGENT.md - Secure Mitigation System Workspace Instructions

## Role & Objective
You are an autonomous software engineering agent maintaining **Secure Mitigation System**, a containerized vulnerability verification and input-sanitization system built for the Meta Global AI Developer Hackathon.

## Mandatory Coding Standards
1. **No Partial Code Blocks:** Always write complete files from top to bottom. Never use ellipses (`...`) or placeholder comments to skip unchanged code.
2. **Meta Muse API Only:** Use the `MetaMuseClient` in `agents.py` for all model calls (`muse-spark`, `muse-wonder`, `muse-code`). Never hardcode API keys; always read `META_MUSE_API_KEY` from the environment.
3. **Sanitization Scope Only:** Blue Team prompts and patch validators must only add input sanitization, parameterization, or configuration hardening. Never alter business logic.
4. **Container Hygiene:** Always use `DockerSandboxManager` in `docker_manager.py` to spin up separated `target` and `verifier` containers from pre-built base images on an `internal=True` bridge network.

## Commands
* Initialize Pre-Built Base Images: `python main.py --init-images`
* Start Web UI Server: `python main.py --serve --port 8000`
* Run CLI Scan on Target: `python main.py --scan node_query_sink`
```

---

## 7. Complete Starter Codebase

Below are the complete, runnable core files that form the backbone of Secure Mitigation System.

### 7.1 `requirements.txt`
```text
fastapi==0.115.0
uvicorn==0.30.6
docker==7.1.0
websockets==13.1
openai==1.51.0
pydantic==2.9.2
```

### 7.2 `config.py`
```python
import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class PurpleBoxConfig:
    meta_api_key: str
    meta_base_url: str
    red_team_model: str
    blue_team_model: str
    target_base_image: str
    verifier_base_image: str
    clone_repo_prefix: str
    container_mem_limit: str
    container_cpu_nano: int
    network_prefix: str


def load_config() -> PurpleBoxConfig:
    api_key = os.environ.get("META_MUSE_API_KEY", "").strip()
    base_url = os.environ.get(
        "META_MUSE_BASE_URL", "[https://api.meta.ai/v1](https://api.meta.ai/v1)"
    ).strip()
    red_model = os.environ.get("META_MUSE_RED_MODEL", "muse-spark").strip()
    blue_model = os.environ.get("META_MUSE_BLUE_MODEL", "muse-code").strip()

    return PurpleBoxConfig(
        meta_api_key=api_key,
        meta_base_url=base_url,
        red_team_model=red_model,
        blue_team_model=blue_model,
        target_base_image="purplebox-target-base:latest",
        verifier_base_image="purplebox-verifier-base:latest",
        clone_repo_prefix="purplebox-clone-cache",
        container_mem_limit="256m",
        container_cpu_nano=500_000_000,
        network_prefix="purplebox_isolated_net",
    )


def require_api_key(config: PurpleBoxConfig) -> None:
    if not config.meta_api_key:
        sys.stderr.write(
            "[FATAL] META_MUSE_API_KEY environment variable is required.\n"
            "Secure Mitigation System exclusively runs on Meta Muse models.\n"
        )
        raise RuntimeError("Missing META_MUSE_API_KEY environment variable.")
```

### 7.3 `prompts.py`
```python
RED_TEAM_SYSTEM_PROMPT = """You are the Secure Mitigation System Red Team Boundary Verification Agent, powered by Meta Muse.
Your job is to inspect target source code or configuration files for known input-handling vulnerabilities (such as unsanitized query interpolation, unvalidated command arguments, path traversal sinks, or insecure configuration flags).

STRICT OPERATIONAL RULES:
1. Analyze the provided source file and identify the exact line(s) where untrusted input reaches a sensitive sink without sanitization.
2. Design a safe, non-destructive Python boundary verification script (`verify.py`) that will run inside an isolated Verification Container (`verifier-env`) on an internal bridge network.
3. The verification script must send a benign diagnostic boundary marker (for example, testing whether special syntax characters or unexpected types cause an unhandled error, diagnostic reflection, or unsafe state) to `http://target-service:8080` (or inspect the mounted config).
4. The verification script MUST exit with return code `0` if the vulnerability/unsanitized boundary is confirmed reachable, and exit with return code `1` if the input is properly sanitized or blocked.
5. Output strictly valid JSON matching this schema:
{
  "vulnerability_class": "string",
  "sink_location": "string",
  "analysis_summary": "string",
  "verification_script_python": "string"
}
Do not wrap the JSON in markdown fences or include any text outside the JSON object."""

BLUE_TEAM_SYSTEM_PROMPT = """You are the Secure Mitigation System Blue Team Input-Sanitization Agent, powered by Meta Muse.
Your job is to patch vulnerable source code or configuration files strictly by adding input sanitization, boundary validation, parameterization, or safe configuration defaults.

STRICT OPERATIONAL RULES:
1. DO NOT rewrite the application architecture, rename endpoints, remove features, or alter normal business logic.
2. Apply minimal, surgical sanitization (such as regex allowlists, strict type conversion, parameterized query placeholders, HTML/shell escaping, or secure configuration directives) immediately prior to the vulnerable sink identified by the Red Team Agent.
3. Ensure that valid, normal user inputs continue to function identically to the original code, while malformed or untrusted boundary inputs are cleanly rejected (e.g., returning HTTP 400) or neutralized.
4. Always return the COMPLETE patched file from top to bottom. Never use placeholders or comments like '// rest of code'.
5. Output strictly valid JSON matching this schema:
{
  "sanitization_strategy": "string",
  "diff_summary": "string",
  "patched_file_content": "string"
}
Do not wrap the JSON in markdown fences or include any text outside the JSON object."""
```

### 7.4 `docker_manager.py`
```python
import io
import tarfile
import time
import uuid
import docker
from docker.errors import ImageNotFound, APIError
from typing import Tuple, Optional
from config import PurpleBoxConfig

TARGET_BASE_DOCKERFILE = """
FROM python:3.12-alpine
RUN apk add --no-cache nodejs npm php83 php83-cli curl
WORKDIR /workspace
CMD ["sh", "-c", "sleep 3600"]
"""

VERIFIER_BASE_DOCKERFILE = """
FROM python:3.12-alpine
RUN pip install --no-cache-dir urllib3
WORKDIR /verifier
CMD ["sh", "-c", "sleep 3600"]
"""


class DockerSandboxManager:
    def __init__(self, config: PurpleBoxConfig):
        self.config = config
        self.client = docker.from_env()

    def ensure_base_images(self) -> None:
        self._build_if_missing(self.config.target_base_image, TARGET_BASE_DOCKERFILE)
        self._build_if_missing(self.config.verifier_base_image, VERIFIER_BASE_DOCKERFILE)

    def _build_if_missing(self, tag: str, dockerfile_str: str) -> None:
        try:
            self.client.images.get(tag)
        except ImageNotFound:
            fileobj = io.BytesIO(dockerfile_str.encode("utf-8"))
            self.client.images.build(fileobj=fileobj, tag=tag, rm=True)

    @staticmethod
    def _create_tar_bytes(filename: str, content: str) -> bytes:
        tar_stream = io.BytesIO()
        data = content.encode("utf-8")
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            tar_info = tarfile.TarInfo(name=filename)
            tar_info.size = len(data)
            tar_info.mtime = int(time.time())
            tar.addfile(tar_info, io.BytesIO(data))
        tar_stream.seek(0)
        return tar_stream.read()

    def create_isolated_network(self) -> docker.models.networks.Network:
        net_name = f"{self.config.network_prefix}_{uuid.uuid4().hex[:8]}"
        return self.client.networks.create(
            name=net_name,
            driver="bridge",
            internal=True,
        )

    def start_cloneable_target(
        self,
        network_name: str,
        target_id: str,
        filename: str,
        file_content: str,
        start_cmd: str,
    ) -> Tuple[docker.models.containers.Container, str]:
        self.ensure_base_images()
        snapshot_tag = f"{self.config.clone_repo_prefix}:{target_id}"

        try:
            self.client.images.get(snapshot_tag)
            base_image = snapshot_tag
        except ImageNotFound:
            seed_container = self.client.containers.run(
                self.config.target_base_image,
                command="sh -c 'sleep 5'",
                detach=True,
            )
            try:
                seed_container.commit(repository=self.config.clone_repo_prefix, tag=target_id)
                base_image = snapshot_tag
            finally:
                seed_container.remove(force=True)

        container = self.client.containers.run(
            base_image,
            command="sh -c 'sleep 3600'",
            name=f"target_{uuid.uuid4().hex[:8]}",
            detach=True,
            network=network_name,
            mem_limit=self.config.container_mem_limit,
            memswap_limit=self.config.container_mem_limit,
            nano_cpus=self.config.container_cpu_nano,
            pids_limit=64,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
        )

        # Attach network alias 'target-service' so verifier container can resolve it
        network_obj = self.client.networks.get(network_name)
        network_obj.disconnect(container)
        network_obj.connect(container, aliases=["target-service"])

        tar_bytes = self._create_tar_bytes(filename, file_content)
        container.put_archive("/workspace", tar_bytes)

        # Launch the target service in the background inside the container
        container.exec_run(f"sh -c '{start_cmd} >/workspace/server.log 2>&1 &'", detach=True)
        time.sleep(0.8)
        return container, snapshot_tag

    def update_target_file_and_restart(
        self,
        container: docker.models.containers.Container,
        filename: str,
        patched_content: str,
        restart_cmd: str,
    ) -> None:
        container.exec_run("sh -c 'pkill -f node || pkill -f php || pkill -f python || true'")
        tar_bytes = self._create_tar_bytes(filename, patched_content)
        container.put_archive("/workspace", tar_bytes)
        container.exec_run(f"sh -c '{restart_cmd} >/workspace/server.log 2>&1 &'", detach=True)
        time.sleep(0.8)

    def run_isolated_verifier(
        self,
        network_name: str,
        verify_script_code: str,
    ) -> Tuple[int, str]:
        self.ensure_base_images()
        verifier_container: Optional[docker.models.containers.Container] = None
        try:
            verifier_container = self.client.containers.run(
                self.config.verifier_base_image,
                command="sh -c 'sleep 60'",
                name=f"verifier_{uuid.uuid4().hex[:8]}",
                detach=True,
                network=network_name,
                mem_limit="128m",
                memswap_limit="128m",
                nano_cpus=self.config.container_cpu_nano,
                pids_limit=32,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
            )

            tar_bytes = self._create_tar_bytes("verify.py", verify_script_code)
            verifier_container.put_archive("/verifier", tar_bytes)

            exec_result = verifier_container.exec_run("python3 /verifier/verify.py")
            output = exec_result.output.decode("utf-8", errors="replace").strip()
            return exec_result.exit_code, output
        finally:
            if verifier_container is not None:
                try:
                    verifier_container.remove(force=True)
                except APIError:
                    pass
```

### 7.5 `agents.py`
```python
import json
from pydantic import BaseModel
from openai import AsyncOpenAI
from config import PurpleBoxConfig, require_api_key
from prompts import RED_TEAM_SYSTEM_PROMPT, BLUE_TEAM_SYSTEM_PROMPT


class RedTeamFinding(BaseModel):
    vulnerability_class: str
    sink_location: str
    analysis_summary: str
    verification_script_python: str


class BlueTeamPatch(BaseModel):
    sanitization_strategy: str
    diff_summary: str
    patched_file_content: str


class MetaMuseClient:
    def __init__(self, config: PurpleBoxConfig):
        self.config = config
        require_api_key(self.config)
        self.client = AsyncOpenAI(
            api_key=self.config.meta_api_key,
            base_url=self.config.meta_base_url,
        )

    async def run_red_team_analysis(self, filename: str, source_code: str) -> RedTeamFinding:
        user_prompt = (
            f"Target Filename: {filename}\n"
            f"Target Source Code:\n```\n{source_code}\n```\n"
            "Analyze the code for unsanitized input sinks and produce the JSON verification payload."
        )
        response = await self.client.chat.completions.create(
            model=self.config.red_team_model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": RED_TEAM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw_content = response.choices[0].message.content or "{}"
        cleaned = self._strip_fences(raw_content)
        data = json.loads(cleaned)
        return RedTeamFinding(**data)

    async def run_blue_team_sanitizer(
        self,
        filename: str,
        source_code: str,
        finding: RedTeamFinding,
        verifier_output: str,
    ) -> BlueTeamPatch:
        user_prompt = (
            f"Target Filename: {filename}\n"
            f"Vulnerability Class: {finding.vulnerability_class}\n"
            f"Sink Location: {finding.sink_location}\n"
            f"Red Team Analysis: {finding.analysis_summary}\n"
            f"Verification Trace Output:\n{verifier_output}\n\n"
            f"Original Source Code:\n```\n{source_code}\n```\n"
            "Generate a strict input-sanitization patch without altering core business logic."
        )
        response = await self.client.chat.completions.create(
            model=self.config.blue_team_model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": BLUE_TEAM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw_content = response.choices[0].message.content or "{}"
        cleaned = self._strip_fences(raw_content)
        data = json.loads(cleaned)
        return BlueTeamPatch(**data)

    @staticmethod
    def _strip_fences(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return stripped
```

### 7.6 `main.py`
```python
import argparse
import asyncio
from pathlib import Path
from typing import Callable, Awaitable, Dict, Any
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import load_config
from docker_manager import DockerSandboxManager
from agents import MetaMuseClient

app = FastAPI(title="Secure Mitigation System Orchestrator")
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TARGETS_DIR = BASE_DIR / "targets"

TARGETS_REGISTRY: Dict[str, Dict[str, str]] = {
    "node_query_sink": {
        "filename": "app.js",
        "start_cmd": "node /workspace/app.js",
        "description": "Node.js HTTP endpoint with unsanitized query filter parameter",
    },
    "php_command_sink": {
        "filename": "index.php",
        "start_cmd": "php -S 0.0.0.0:8080 -t /workspace",
        "description": "PHP diagnostic endpoint with unvalidated host ping parameter",
    },
    "mysql_insecure_conf": {
        "filename": "my.cnf",
        "start_cmd": "python3 -m http.server 8080 --directory /workspace",
        "description": "MySQL configuration file exposing insecure bind and file privileges",
    },
}

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


async def execute_purple_workflow(
    target_key: str,
    emit: Callable[[str, str], Awaitable[None]],
) -> bool:
    config = load_config()
    sandbox = DockerSandboxManager(config)
    muse_client = MetaMuseClient(config)

    if target_key not in TARGETS_REGISTRY:
        await emit("system", f"[ERROR] Unknown target '{target_key}'.")
        return False

    target_meta = TARGETS_REGISTRY[target_key]
    target_file_path = TARGETS_DIR / target_key / target_meta["filename"]
    if not target_file_path.exists():
        await emit("system", f"[ERROR] Target file missing: {target_file_path}")
        return False

    original_source = target_file_path.read_text(encoding="utf-8")

    network = None
    target_container = None

    try:
        await emit(
            "system",
            f"[SYSTEM] Creating air-gapped internal bridge network for '{target_key}'...",
        )
        network = await asyncio.to_thread(sandbox.create_isolated_network)

        await emit(
            "system",
            "[SYSTEM] Cloning pre-built target container from warm snapshot...",
        )
        target_container, snapshot_tag = await asyncio.to_thread(
            sandbox.start_cloneable_target,
            network.name,
            target_key,
            target_meta["filename"],
            original_source,
            target_meta["start_cmd"],
        )
        await emit(
            "system",
            f"[SYSTEM] Target container active (Image: {snapshot_tag}). Isolated alias: target-service:8080",
        )

        # Phase 1: Red Team Analysis via Meta Muse
        await emit(
            "red",
            f"[RED TEAM] Dispatching source to Meta Muse ({config.red_team_model})...",
        )
        finding = await muse_client.run_red_team_analysis(target_meta["filename"], original_source)
        await emit(
            "red",
            f"[RED TEAM] Identified {finding.vulnerability_class} at {finding.sink_location}",
        )
        await emit("red", f"[RED TEAM] Summary: {finding.analysis_summary}")

        # Phase 2: Isolated Verification Container Run (Pre-Patch)
        await emit(
            "red",
            "[RED TEAM] Spinning up separated Verification Container to test input boundary...",
        )
        exit_code_pre, output_pre = await asyncio.to_thread(
            sandbox.run_isolated_verifier,
            network.name,
            finding.verification_script_python,
        )
        await emit(
            "red",
            f"[RED TEAM] Verifier Exit Code: {exit_code_pre} | Trace: {output_pre}",
        )

        # Phase 3: Blue Team Input Sanitization Patching via Meta Muse
        await emit(
            "blue",
            f"[BLUE TEAM] Requesting sanitization-only patch from Meta Muse ({config.blue_team_model})...",
        )
        patch = await muse_client.run_blue_team_sanitizer(
            target_meta["filename"],
            original_source,
            finding,
            output_pre,
        )
        await emit(
            "blue",
            f"[BLUE TEAM] Sanitization Strategy: {patch.sanitization_strategy}",
        )
        await emit("blue", f"[BLUE TEAM] Diff Summary: {patch.diff_summary}")

        # Phase 4: Apply Patch & Re-Verify
        await emit(
            "system",
            "[SYSTEM] Injecting sanitized file into target container & restarting service...",
        )
        await asyncio.to_thread(
            sandbox.update_target_file_and_restart,
            target_container,
            target_meta["filename"],
            patch.patched_file_content,
            target_meta["start_cmd"],
        )

        await emit(
            "blue",
            "[BLUE TEAM] Re-running isolated Verification Container against sanitized target...",
        )
        exit_code_post, output_post = await asyncio.to_thread(
            sandbox.run_isolated_verifier,
            network.name,
            finding.verification_script_python,
        )
        await emit(
            "blue",
            f"[BLUE TEAM] Post-Patch Verifier Exit Code: {exit_code_post} | Trace: {output_post}",
        )

        if exit_code_post != 0:
            await emit(
                "system",
                "[SYSTEM] VERIFICATION PASSED: Input boundary sanitized and untrusted input rejected.",
            )
            return True
        else:
            await emit(
                "system",
                "[SYSTEM] VERIFICATION WARNING: Boundary probe still returned exit code 0.",
            )
            return False

    except Exception as exc:
        await emit("system", f"[ERROR] Workflow exception: {str(exc)}")
        return False
    finally:
        await emit("system", "[SYSTEM] Tearing down isolated containers and network...")
        if target_container is not None:
            try:
                await asyncio.to_thread(target_container.remove, force=True)
            except Exception:
                pass
        if network is not None:
            try:
                await asyncio.to_thread(network.remove)
            except Exception:
                pass


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/targets")
async def list_targets() -> JSONResponse:
    return JSONResponse(content=TARGETS_REGISTRY)


@app.websocket("/ws/combat/{target_key}")
async def ws_combat(websocket: WebSocket, target_key: str) -> None:
    await websocket.accept()

    async def ws_emit(team: str, msg: str) -> None:
        await websocket.send_json({"team": team, "msg": msg})

    try:
        await execute_purple_workflow(target_key, ws_emit)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


async def cli_runner(target_key: str) -> int:
    async def cli_emit(team: str, msg: str) -> None:
        prefix = team.upper().ljust(6)
        print(f"[{prefix}] {msg}")

    success = await execute_purple_workflow(target_key, cli_emit)
    return 0 if success else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Secure Mitigation System: Meta Muse Containerized Sanitization Orchestrator"
    )
    parser.add_argument(
        "--init-images",
        action="store_true",
        help="Pre-build the cloneable Target and Verifier Docker base images",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the FastAPI Web UI and WebSocket server",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the FastAPI Web UI server (default: 8000)",
    )
    parser.add_argument(
        "--scan",
        type=str,
        choices=list(TARGETS_REGISTRY.keys()),
        help="Run a headless CLI scan against a specific target key",
    )

    args = parser.parse_args()
    config = load_config()

    if args.init_images:
        print("[SYSTEM] Building cloneable base Docker images...")
        manager = DockerSandboxManager(config)
        manager.ensure_base_images()
        print("[SYSTEM] Base images ready.")
        return

    if args.scan:
        raise SystemExit(asyncio.run(cli_runner(args.scan)))

    if args.serve:
        uvicorn.run("main:app", host="127.0.0.1", port=args.port, reload=False)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
```

### 7.7 `static/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Secure Mitigation System // Meta Muse Security Sanitizer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .term-font { font-family: 'Courier New', Courier, monospace; }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #090d16; }
        ::-webkit-scrollbar-thumb { background: #263044; border-radius: 4px; }
    </style>
</head>
<body class="bg-slate-950 text-slate-100 h-screen flex flex-col p-6">
    <header class="flex flex-wrap justify-between items-center pb-4 border-b border-slate-800 gap-4">
        <div>
            <h1 class="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-rose-500 via-purple-400 to-sky-400">
                Secure Mitigation System // Meta Muse Orchestrator
            </h1>
            <p class="text-slate-400 text-xs mt-1">
                Isolated Cloneable Container Verification &amp; Surgical Input-Sanitization Engine
            </p>
        </div>
        <div class="flex items-center gap-3">
            <select id="target-select" class="bg-slate-900 border border-slate-700 text-sm rounded px-3 py-2 text-slate-200">
                <option value="node_query_sink">Target 1: Node.js Query Sink (app.js)</option>
                <option value="php_command_sink">Target 2: PHP Diagnostic Parameter (index.php)</option>
                <option value="mysql_insecure_conf">Target 3: MySQL Configuration Hardening (my.cnf)</option>
            </select>
            <button id="run-btn" class="bg-purple-600 hover:bg-purple-500 text-white font-semibold py-2 px-5 rounded text-sm transition">
                Launch Sandbox Verification
            </button>
        </div>
    </header>

    <main class="flex-1 grid grid-cols-1 md:grid-cols-2 gap-6 mt-5 overflow-hidden">
        <section class="bg-black border border-rose-900/80 rounded-lg p-4 flex flex-col">
            <h2 class="text-rose-400 font-bold text-xs tracking-widest uppercase border-b border-rose-950 pb-2 mb-3">
                Red Team Agent // Boundary Auditor (Verifier Container)
            </h2>
            <div id="red-log" class="term-font text-rose-300 text-xs overflow-y-auto flex-1 whitespace-pre-wrap leading-relaxed"></div>
        </section>

        <section class="bg-black border border-sky-900/80 rounded-lg p-4 flex flex-col">
            <h2 class="text-sky-400 font-bold text-xs tracking-widest uppercase border-b border-sky-950 pb-2 mb-3">
                Blue Team Agent // Input Sanitizer (Target Container)
            </h2>
            <div id="blue-log" class="term-font text-sky-300 text-xs overflow-y-auto flex-1 whitespace-pre-wrap leading-relaxed"></div>
        </section>
    </main>

    <footer class="mt-5 bg-black border border-slate-800 rounded-lg p-4 h-40 flex flex-col">
        <h2 class="text-slate-400 font-bold text-xs tracking-widest uppercase border-b border-slate-900 pb-2 mb-2">
            Docker Sandbox &amp; Network Telemetry
        </h2>
        <div id="sys-log" class="term-font text-slate-300 text-xs overflow-y-auto flex-1 whitespace-pre-wrap leading-relaxed"></div>
    </footer>

    <script>
        const runBtn = document.getElementById('run-btn');
        const targetSelect = document.getElementById('target-select');
        const redLog = document.getElementById('red-log');
        const blueLog = document.getElementById('blue-log');
        const sysLog = document.getElementById('sys-log');

        function writeLine(container, text) {
            const line = document.createElement('div');
            line.className = 'mb-1.5';
            line.textContent = '> ' + text;
            container.appendChild(line);
            container.scrollTop = container.scrollHeight;
        }

        runBtn.addEventListener('click', () => {
            const targetKey = targetSelect.value;
            runBtn.disabled = true;
            runBtn.classList.add('opacity-50', 'cursor-not-allowed');
            redLog.innerHTML = '';
            blueLog.innerHTML = '';
            sysLog.innerHTML = '';

            const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const ws = new WebSocket(`${proto}//${window.location.host}/ws/combat/${targetKey}`);

            ws.onmessage = (event) => {
                const payload = JSON.parse(event.data);
                if (payload.team === 'red') {
                    writeLine(redLog, payload.msg);
                } else if (payload.team === 'blue') {
                    writeLine(blueLog, payload.msg);
                } else {
                    writeLine(sysLog, payload.msg);
                }
            };

            ws.onclose = () => {
                writeLine(sysLog, '[SYSTEM] Session closed.');
                runBtn.disabled = false;
                runBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            };
        });
    </script>
</body>
</html>
```

### 7.8 Sample Target: `targets/node_query_sink/app.js`
```javascript
const http = require('http');
const url = require('url');

// Simulated in-memory account records
const ACCOUNTS = [
    { id: 101, username: 'alice', role: 'user' },
    { id: 102, username: 'bob', role: 'admin' }
];

const server = http.createServer((req, res) => {
    const parsedUrl = url.parse(req.url, true);

    if (parsedUrl.pathname === '/lookup' && req.method === 'GET') {
        const rawUserId = parsedUrl.query.id || '';

        // Unsanitized dynamic evaluation sink (vulnerable to non-integer input boundaries)
        const queryExpression = ` item.id == ${rawUserId} `; try { const filterFn = new Function('item', `return (${queryExpression});`);
            const matches = ACCOUNTS.filter(filterFn);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'ok', count: matches.length, results: matches }));
        } catch (err) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'error', detail: err.message }));
        }
        return;
    }

    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'not_found' }));
});

server.listen(8080, '0.0.0.0', () => {
    console.log('Target service listening on port 8080');
});
```

---

## 8. Agent Expansion Roadmap (Next Tasks for AI Builders)

When an AI coding agent reads this `SPEC.md` and is tasked with finishing the repository, it should execute the following steps in order:
1. **Generate `AGENT.md` and `LICENSE.md`:** Write the root `AGENT.md` from Section 6 and populate `LICENSE.md` with the required noncommercial notice and link to the PolyForm Noncommercial 1.0.0 license.
2. **Create the Remaining Two Target Fixtures:**
   * `targets/php_command_sink/index.php`: A lightweight PHP script accepting a `?host=` query string that needs strict hostname/IP allowlist validation.
   * `targets/mysql_insecure_conf/my.cnf`: A MySQL configuration file containing `bind-address = 0.0.0.0`, `local-infile = 1`, and `secure-file-priv = ""` that the Blue Team agent must harden to `127.0.0.1` and `local-infile = 0`.
3. **Add Automated Self-Test Suite (`test_harness.py`):** Create a test script that verifies Docker daemon connectivity, checks that `internal=True` blocks external internet access inside both containers, and validates JSON schema parsing from the Meta Muse endpoints.
---

## 14. Wave 2 Zero-Day Delta (Oct 29, 2026)

Source: `RESEARCH_V1.md`. These features satisfy the zero-day mandate (accelerate same-day patching) and are additive to the existing scan surfaces. See `README.md#configuration`.

### 14.1 Sink-adjacency reachability fusion

New `reach_score` / `reach_evidence` fields on CVE summaries (CVE workflow output). Fuses OSV fixed-version ranges with static sink signals (`deep_scan.run_static_scan`) and Docker probe evidence (`docker_manager`) into a deterministic adjacency score. Fail-closed: absent signals lower the score, never raise it. Competitor Snyk/Endor does call-graph reachability, but we are doing version-range + sink-adjacency + probe proof for keyless teams.

### 14.2 CVE disclosure fast lane

New opt-in CVE fast lane on `execute_cve_scan(..., fast_lane=True)`: skips the scanner-binary stage entirely (static signals + keyless OSV only), keeps deterministic ordering and never-raises degradation, and returns the same `CveScanReport` shape. This is the precomputed disclosure trigger from Wave 1 same-day requirement (a): on disclosure day the fast lane produces triage input in minutes without waiting on host scanner binaries. NVD enrichment stays opt-in (`include_nvd`) and off the fast path.

### 14.3 Demand-driven ghost-probe liveness

The fixture workflow already re-runs trusted normal-input checks after the post-patch probe (`workflow.py` `final_health`, trace `after_probe_regression`). The project workflow only does the equivalent when the probe exits 1 (`project_workflow.verify_project_snapshot`). This delta closes the exit-2 gap: post-probe liveness runs whenever the probe exit is not 0, its evidence is named as post-probe regression, and a dead or inconclusive target earns no credit (fail-closed, LAW 4). No new check script is invented; the existing regression command is the liveness oracle.

### 14.4 Greenhouse generative hardening

`demo_gen` gains hardening controls (tri-surface: dashboard intensity/team/budget/consent widgets already exist since 0.2.0; CLI `--ai-demo` plus `--build-brief`/`--vulns`). Generated targets are secret-scanned and syntax-checked before container use (already shipped); hardening adds per-run variability and consent-gated generation.
