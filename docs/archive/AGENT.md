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

Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
https://polyformproject.org/licenses/noncommercial/1.0.0

## Repository Map
See [../architecture/REPOSITORY.md](../architecture/REPOSITORY.md) for import provenance, verified local
validation commands, entry points, and local-state caveats.

For current setup commands, Docker rebuild/cleanup rules, and environment traps,
see [../guides/DEVELOPMENT.md](../guides/DEVELOPMENT.md).

Arbitrary local projects use `projects.py`, `project_agents.py`, and
`project_workflow.py`, separate from the fixture workflow. See
[../guides/PROJECTS.md](../guides/PROJECTS.md) for snapshot/runtime constraints and
[../architecture/PROJECT_WORKFLOW.md](../architecture/PROJECT_WORKFLOW.md) for evidence and context rules.
Local Muse serving is an explicit loopback-only opt-in, never a fallback provider.

Scan intensity and team configuration live in [docs/SCAN_PROFILES.md](docs/SCAN_PROFILES.md).
See [docs/DISCOVERY_TEAMS.md](docs/DISCOVERY_TEAMS.md) for leader/worker payloads
and [../architecture/PROJECT_WORKFLOW.md](../architecture/PROJECT_WORKFLOW.md) for cycle/pass evidence semantics.
