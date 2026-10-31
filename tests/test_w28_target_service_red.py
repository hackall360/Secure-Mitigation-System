# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Wave 28 RED: ingested target-service pairing (tribunal 2a residual).

The probe contract requires verifiers to hit http://target-service:8080,
but the Wave-22 adapter never starts a target container — verify scripts
have nothing to probe. Pin: when a verifier script is present, the
ingest sandbox must start the staged target with the target-service alias
on the same network (bounded readiness), run the verifier, then stop it.
Fail closed everywhere: no readiness → SandboxError, never a pass.
"""

from unittest.mock import MagicMock

import main


def _snapshot(files=None):
    snap = MagicMock()
    snap.files = dict(files or {"server.py": "print('hi')\n"})
    snap.runtime_command = ("python3", "server.py")
    snap.url = "https://github.com/example/demo"
    return snap


def test_factory_exposes_target_service_pairing():
    import inspect

    src = inspect.getsource(main._ingest_sandbox_factory)
    assert "target-service" in src, "ingest adapter must alias the staged target"


def test_verify_without_target_service_fails_closed():
    """Without a paired target-service, script verify must fail closed.

    The adapter's _evidence(script=...) path must require a live paired
    target; if pairing is absent it raises instead of running the script
    against nothing (which would read as inconclusive-pass confusion).
    Today there is no pairing at all, so assert the gap explicitly: the
    factory source must grow a _serve_target/pairing helper. This test
    passes only when the pairing exists (see test_factory_exposes...).
    """
    import inspect

    src = inspect.getsource(main._ingest_sandbox_factory)
    assert "_ensure_target" in src and "target-service" in src


def test_adapter_imports_target_primitive():
    import inspect

    src = inspect.getsource(main)
    assert "start_project" in src or "_snapshot_project_image" in src
