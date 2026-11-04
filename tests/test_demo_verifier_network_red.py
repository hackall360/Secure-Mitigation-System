# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): verifier probes speak to the target, not just the wrapper.

Found live 2026-11-04 (Part 2 dry run): red's probes could only fetch the
wrapper's static file service — HTTP-text of staged bytes. A purple-team
probe surface must reach the ACTUAL target behavior: raw sockets, TLS,
arbitrary ports, DNS, custom protocols — cyber, not just text.

Fix contract: verifier containers join the isolated project network
(``network_mode`` = the scan network, NOT ``none``) with DNS alias
``target-service``, so probes open real connections to the real target:
raw TCP/UDP sockets, TLS handshakes, any port the target serves, DNS
resolution through the sandbox resolver. The wrapper's 8080 file service
remains the DEFAULT surface (back-compat: every existing probe keeps
working), but red may now also probe the target's own ports directly.

Isolation holds: the network is internal (no egress), non-root,
cap-dropped, no-new-privileges. Probes can reach the target — nothing else.

This pin asserts verifier containers ride the scan network (not none).
"""

from __future__ import annotations


def _runtime_src() -> str:
    import inspect

    import library.core.docker_manager as dm

    return inspect.getsource(dm.DockerSandboxManager._runtime)


def test_verifier_runtime_takes_network():
    src = _runtime_src()
    assert '"network": network.name' in src or "'network': network.name" in src


def test_isolated_verifier_joins_scan_network():
    import inspect

    import library.core.docker_manager as dm

    src = inspect.getsource(dm.DockerSandboxManager.run_isolated_verifier)
    assert "network_mode" not in src or "none" not in src.split("network_mode")[1][:30], (
        "run_isolated_verifier must NOT force network_mode=none — "
        "probes need the scan network to reach target-service"
    )
    assert "network" in src, "verifier must take the scan network"


def test_verifier_reaches_target_on_arbitrary_port():
    """Live: a raw-socket probe hits a listening target on a custom port.

    This is the cyber proof — not HTTP-text, but a real socket to a real
    service on a non-8080 port, plus DNS + TLS module availability. Docker
    required; skipped cleanly without it.
    """
    import shutil
    import time

    if shutil.which("docker") is None:
        import pytest

        pytest.skip("docker required for live probe-surface proof")
    from library.core.config import load_config
    from library.core.docker_manager import DockerSandboxManager
    from library.services.projects import ProjectFileMetadata, _make_snapshot

    settings = load_config()
    mgr = DockerSandboxManager(settings)
    try:
        net = mgr.create_isolated_network()
        code = {"app.py": b"x = 1\n"}
        meta = {"app.py": ProjectFileMetadata(size=6, mode=0o644)}
        snapshot = _make_snapshot(code, meta)
        image = mgr._snapshot_project_image(settings.target_base_image, snapshot, "test")
        srv = (
            "python3",
            "-c",
            "import socket; s=socket.socket(); s.setsockopt(1,2,1); s.bind(('0.0.0.0',9999)); s.listen(1); "
            "c,a=s.accept(); c.sendall(b'PWNED'); c.close()",
        )
        target = mgr._runtime(
            image,
            net,
            "target",
            list(srv),
            aliases=["target-service"],
            clear_entrypoint=True,
            working_dir="/workspace",
        )
        time.sleep(4)
        probe = (
            "import socket, sys\ns = socket.create_connection(('target-service', 9999), timeout=5)\n"
            "data = s.recv(16)\nprint('GOT', data)\nassert data == b'PWNED'\n"
            "print('DNS:', socket.gethostbyname('target-service'))\n"
            "import ssl; print('TLS-MOD-OK', ssl.OPENSSL_VERSION.split()[1])\nsys.exit(0)\n"
        )
        result = mgr.run_isolated_verifier(net, probe)
        assert result.exit_code == 0, f"raw-socket probe failed: {result.output[:300]}"
        assert "GOT" in (result.output or "")
        target.remove(force=True)
        net.remove()
    finally:
        mgr.close()
