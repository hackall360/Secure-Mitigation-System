# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: scan-surface parity -- CLI --scan vs WS combat for the binary fixture.

Scout headlines (2026-11-01, UNVERIFIED) under test:
H1: main.py --scan choices=list(TARGETS_REGISTRY) admits binary_argv_echo
    while the WS combat route (run_socket ~L1043) special-cases it.
H2: some --help/epilog text names flags that do not exist.

LAW 9: real parser + real route only. build_parser().parse_args is the live
parser; fastapi TestClient drives the real /ws/combat route (the explicit
test config is setup, not a mock of the unit). No Docker/Muse: the binary
path raises before any sandbox or model contact.
"""

import re

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main as _main
from modules.core.config import PurpleBoxConfig
from modules.core.registry import TARGETS_REGISTRY


def _combat_events(target_key: str):
    """Drive the real WS combat route; return (frames, raised)."""
    app = _main.create_app(PurpleBoxConfig(meta_api_key="k"))
    frames: list = []
    raised = None
    try:
        with TestClient(app, base_url="http://localhost") as client:
            headers = {"origin": "http://localhost"}
            with client.websocket_connect(
                f"ws://localhost/ws/combat/{target_key}", headers=headers
            ) as ws:
                try:
                    while True:
                        frames.append(ws.receive_json())
                except (WebSocketDisconnect, Exception) as exc:
                    # Clean close (post-fix) ends the stream normally; an
                    # abnormal drop leaves frames short AND the server error
                    # surfaces at context exit below.
                    if not isinstance(exc, WebSocketDisconnect):
                        frames.append({"type": "dropped", "detail": repr(exc)})
    except Exception as exc:  # noqa: BLE001 - the defect IS the raise
        raised = exc
    return frames, raised


def test_h1_cli_admits_binary_but_socket_does_not_fail_closed():
    """H1 (expect FAIL pre-fix): CLI --scan accepts binary_argv_echo while
    the registry description itself says "not --scan", and the WS combat
    route answers with an unhandled ValueError instead of a fail-closed
    invalid frame like the project/demo paths send. Passes only when the
    socket fails closed gracefully."""
    ns = _main.build_parser().parse_args(["--scan", "binary_argv_echo"])
    assert ns.scan == "binary_argv_echo"  # CLI surface admits it: real parser
    assert "not --scan" in TARGETS_REGISTRY["binary_argv_echo"].description
    frames, raised = _combat_events("binary_argv_echo")
    assert raised is None, f"socket raised instead of failing closed: {raised!r}"
    kinds = [f.get("type") for f in frames if isinstance(f, dict)]
    assert "invalid" in kinds, f"no fail-closed invalid frame: {kinds}"


def test_h2_help_names_only_registered_flags():
    """H2 SCOUT ERROR (expect PASS): every --flag token in --help, including
    the epilog's --fast-lane, is a registered parser option. Documents that
    no lying flag text was found; guards against future drift."""
    parser = _main.build_parser()
    help_text = parser.format_help()
    registered = {opt for a in parser._actions for opt in a.option_strings}
    tokens = set(re.findall(r"--[a-z][a-z-]*", help_text))
    assert tokens, "help text names no flags at all?"
    assert tokens <= registered, f"help names unregistered flags: {sorted(tokens - registered)}"
    assert "--fast-lane" in tokens and "--fast-lane" in registered
    assert "--binary-target" in tokens and "--binary-target" in registered
