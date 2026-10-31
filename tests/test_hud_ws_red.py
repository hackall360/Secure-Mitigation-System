# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
"""LAW 9 RED: HUD websocket schema contract (schema only, no browser proof)."""

import json


def test_telemetry_event_shape_valid_for_write_line():
    from modules.services.sms_api import build_telemetry_event

    evt = build_telemetry_event(raw=1000, sent=250, savings_pct=75.0, novel=3, known=7)
    assert evt["team"] == "telemetry"
    assert evt["type"] == "log"
    assert "Raw" in evt["msg"] and "Sent" in evt["msg"] and "Savings" in evt["msg"]
    json.dumps({"type": evt["type"], "team": evt["team"], "msg": evt["msg"]})


def test_telemetry_event_zero_savings_still_valid():
    from modules.services.sms_api import build_telemetry_event

    evt = build_telemetry_event(raw=100, sent=100, savings_pct=0.0, novel=0, known=0)
    assert evt["team"] == "telemetry"
    assert isinstance(evt["msg"], str) and "Savings" in evt["msg"]


def test_ingest_event_redacts_repo_url():
    from modules.services.sms_api import build_ingest_event

    evt = build_ingest_event(
        repo_url="https://user:secret@example.com/org/repo.git", sha="abcdef1234567890"
    )
    assert evt["team"] == "ingest"
    assert isinstance(evt["msg"], str)
    assert "@" not in evt["msg"], "full URL with credentials leaked"
    assert "example.com" in evt["msg"]
    assert "abcdef1" in evt["msg"] or "abcdef12" in evt["msg"]


def test_result_dump_includes_hud_keys_for_render_usage():
    from modules.services.sms_api import build_result_hud

    result = {
        "verdict": "verified",
        "hud_tokens": {"raw": 1000, "sent": 250},
        "hud_vault": {"novel": 3},
    }
    hud = build_result_hud(result)
    assert any(k in hud for k in ("hud_tokens", "hud_vault", "savings_pct", "novel_vs_historical"))
