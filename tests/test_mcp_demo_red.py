# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED test for the future scripts/mcp_client_demo.py (LAW 9).

The demo module does not exist yet (ls scripts/ -> no such directory);
importing it raises ModuleNotFoundError, which IS the expected FAIL.
Do NOT implement the feature here. GREEN lands with the demo script.
"""

import re
import socket

import pytest

try:
    import scripts.mcp_client_demo as demo

    HAS_DEMO = True
except ModuleNotFoundError:
    HAS_DEMO = False
    demo = None  # type: ignore[assignment]

REQUIRES_DEMO = "RED: scripts/mcp_client_demo.py not implemented"


def test_demo_module_exists():
    assert HAS_DEMO, REQUIRES_DEMO


def test_demo_module_shape_and_contract(monkeypatch):
    import inspect

    assert callable(demo.main)
    assert callable(demo.run_demo)
    assert list(inspect.signature(demo.run_demo).parameters) == [
        "base_url",
        "filename",
        "language",
        "source",
    ]
    monkeypatch.setattr(demo, "_post_rpc", lambda *a, **k: {"jsonrpc": "2.0", "id": 1, "result": {}})
    result = demo.run_demo(
        base_url="http://127.0.0.1:9",
        filename="snippet.py",
        language="python",
        source="print('hi')\n",
    )
    assert isinstance(result, dict)
    assert {"status", "pre_probe_exit", "post_probe_exit", "receipt_sha"} <= set(result)


def test_demo_help_mentions_mcp_endpoint(capsys):
    with pytest.raises(SystemExit) as exc:
        demo.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert re.search(r"/mcp|MCP endpoint|mcp", out)


def _closed_loopback_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_demo_dead_port_fails_closed(capsys):
    port = _closed_loopback_port()
    with pytest.raises(SystemExit) as exc:
        demo.main(
            [
                "--base-url",
                f"http://127.0.0.1:{port}",
                "--timeout",
                "2",
            ]
        )
    assert exc.value.code != 0
    combined = capsys.readouterr().out + capsys.readouterr().err
    assert re.search(r"refused|unreachable|failed", combined, re.IGNORECASE)


def test_demo_oversize_source_rejected_before_http(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("HTTP must not be attempted for oversize source")

    monkeypatch.setattr("socket.create_connection", _boom)
    monkeypatch.setattr("urllib.request.urlopen", _boom)
    big = "x" * (65536 + 1)
    with pytest.raises((ValueError, SystemExit)):
        demo.run_demo(
            base_url="http://127.0.0.1:9",
            filename="big.py",
            language="python",
            source=big,
        )
