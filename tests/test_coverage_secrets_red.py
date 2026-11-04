# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): secrets-class probes must not leak secret VALUES into reports.

The coverage pass asks red to fetch files and exit 0 when "secret-looking
material is served verbatim". The redacted sweep report strips the probe
SCRIPT but keeps vulnerability_class + sink_location + analysis_summary
verbatim — a model that pastes the found secret into any of those three
fields leaks it into logs, receipts, and the user report. LAW 4 (never
log secrets) needs a prompt-level guard, not just post-hoc redaction.

Parity contract: the coverage prompt's SECRETS section directs red to
name the KIND + path:line (e.g. "hardcoded-secret at config/keys.py:12")
and to DESCRIBE the finding without reproducing the secret value in ANY
field (class, location, summary, or probe output). Probe scripts match
patterns (length/shape/prefix), never echo full values.
"""

from __future__ import annotations


def test_secrets_probe_bans_value_reproduction():
    from modules.core import prompts as prompts_mod

    text = prompts_mod.RED_COVERAGE_SWEEP_SYSTEM_PROMPT
    secrets_idx = text.find("SECRETS")
    assert secrets_idx != -1
    window = text[secrets_idx : secrets_idx + 3000].lower()
    assert "never reproduce" in window or "without reproducing" in window, (
        "SECRETS probe must forbid reproducing the secret value in any "
        "field (class, location, summary, probe output)"
    )
    assert "kind" in window and "path" in window
