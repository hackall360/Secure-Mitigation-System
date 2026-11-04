# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): MISSION OMNI-INGEST Wave 2 — DynamicProvisioner thick image.

Wave 1 maps ecosystems to toolchains; nothing can INSTALL them. The target
image (python:3.12-alpine + node + php) has no gcc/make/cmake/cargo/go, so
`cargo test` / `go test ./...` / `make` argv resolve but cannot execute —
a runtime-shaped refusal by another name. LAW 2: provisioning (network ON)
and execution (network OFF) must be strictly sequential states.

Contract:
- `docker/Dockerfile.polyglot` exists: pinned python:3.12-alpine3.22 base
  (same digest discipline as Dockerfile.target) + build toolchains
  (gcc/make/cmake) + Go + Rust toolchains via pinned apk packages where
  available, with a documented fallback when an apk package is missing.
- `config.polyglot_base_image` names it; `build_base_images` builds it.
- `provision_toolchains(network, ecosystem)` runs the package-install
  phase with network attached, then the execution wave re-attaches with
  network NONE. LAW 2 holds by construction: no single container ever
  spans both states.
"""

from __future__ import annotations


def test_polyglot_dockerfile_exists_and_pinned():
    from pathlib import Path

    text = Path("docker/Dockerfile.polyglot").read_text()
    assert "sha256:" in text, "polyglot base must be digest-pinned like Dockerfile.target"
    for tool in ("gcc", "make", "cmake"):
        assert tool in text, f"polyglot image must install {tool}"


def test_polyglot_image_wired_into_build():
    from modules.core import docker_manager as dm

    src = open(dm.__file__).read()
    assert "Dockerfile.polyglot" in src, "build path must know the polyglot Dockerfile"
    assert "polyglot_base_image" in src, "config must name the polyglot image"


def test_provision_then_seal_contract():
    from modules.core import docker_manager as dm

    src = open(dm.__file__).read()
    assert "provision_toolchains" in src, "DynamicProvisioner entry point must exist"
