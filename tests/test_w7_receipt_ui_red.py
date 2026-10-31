# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9) receipt-chain visual badge tests per tribunal 2d-9 gap (W7).

Fails today: the dashboard renders the verdict receipt one-liner but never
surfaces receipt-chain state, and the CLI ``receipt`` bullet carries no chain
token. GREEN wires the renderers only (backend already ships chain fields
from Wave 6: ``build_verdict_receipt(prev_receipt=...)`` +
``verify_receipt`` -> ``chain_ok``): app.js renders ``sha12 · chain ok/broken``,
index.html adds a ``fact-receipt-chain`` row + ``receipt-chain-badge`` verify
badge, sms_cli gains the same ``chain ok``/``chain broken`` token (flows to
the TUI through ``format_facts``).

LAW 9B: do not weaken these assertions (sha length, exact tokens, exact ids).
"""

import re
from html.parser import HTMLParser
from types import SimpleNamespace

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


class _Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


def _ids():
    parser = _Elements()
    parser.feed((ROOT / "static/index.html").read_text())
    return [attrs["id"] for _, attrs in parser.nodes if "id" in attrs]


def _chained_receipt_payload():
    """VerdictReceipt-shaped payload with an INTACT chain link (same patch)."""
    from modules.workflows.workflow import build_verdict_receipt

    prev = build_verdict_receipt(
        fixture="node_query_sink",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content="diff-bytes",
    )
    chained = build_verdict_receipt(
        fixture="node_query_sink",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content="diff-bytes",
        prev_receipt=prev,
    )
    return SimpleNamespace(
        target="node_query_sink",
        status="verified",
        receipt=chained,
        model_dump=lambda: {"target": "node_query_sink", "status": "verified"},
    )


def _genesis_receipt_payload():
    """Unlinked (genesis) receipt: no prev link -> chain reads broken."""
    from modules.workflows.workflow import build_verdict_receipt

    receipt = build_verdict_receipt(
        fixture="node_query_sink",
        pre_exit_code=0,
        post_exit_code=1,
        regression_passed=True,
        patch_content="diff-bytes",
    )
    return SimpleNamespace(
        target="node_query_sink",
        status="verified",
        receipt=receipt,
        model_dump=lambda: {"target": "node_query_sink", "status": "verified"},
    )


# --- index.html surface (row + badge ids) ---


def test_receipt_chain_row_exists():
    """fact-receipt-chain row renders the chain state beside the one-liner."""
    assert "fact-receipt-chain" in _ids(), "#fact-receipt-chain row missing"


def test_receipt_chain_badge_exists():
    """receipt-chain-badge verify badge element exists on the result card."""
    assert "receipt-chain-badge" in _ids(), "#receipt-chain-badge missing"


# --- CLI bullet: sha12 + chain token (flows to TUI via format_facts) ---


def test_cli_receipt_bullet_is_sha12_with_chain_ok():
    """Intact chain renders sha12 (not sha16) + explicit chain-ok token."""
    from sms_cli import format_wave2_facts

    facts = format_wave2_facts(_chained_receipt_payload(), use_color=False)
    bullet = facts["receipt"]
    digest = __import__("hashlib").sha256(b"diff-bytes").hexdigest()
    assert f"sha {digest[:12]}" in bullet, f"sha12 {digest[:12]} missing: {bullet!r}"
    assert digest[:16] not in bullet, "sha16 must shrink to sha12"
    assert re.search(r"chain[ -]?ok", bullet, re.IGNORECASE), f"chain-ok token missing: {bullet!r}"


def test_cli_receipt_bullet_chain_broken_on_genesis():
    """Unlinked receipt reads chain-broken (verify_receipt chain_ok False)."""
    from sms_cli import format_wave2_facts

    facts = format_wave2_facts(_genesis_receipt_payload(), use_color=False)
    bullet = facts["receipt"]
    digest12 = __import__("hashlib").sha256(b"diff-bytes").hexdigest()[:12]
    assert f"sha {digest12}" in bullet
    assert re.search(r"chain[ -]?broken", bullet, re.IGNORECASE), (
        f"genesis must read chain-broken, got: {bullet!r}"
    )


def test_cli_receipt_bullet_chain_missing_degrades():
    """Receipt shaped dict without chain fields degrades, never raises."""
    from sms_cli import format_wave2_facts

    result = SimpleNamespace(
        target="node_query_sink",
        status="verified",
        receipt={"fixture": "node_query_sink", "patch_sha256": "ab" * 32},
        model_dump=lambda: {"target": "node_query_sink"},
    )
    facts = format_wave2_facts(result, use_color=False)
    assert "abababababab" in facts["receipt"]
    assert "chain" in facts["receipt"].lower()


# --- app.js render wiring (static patterns; node has no DOM harness) ---


def test_app_js_receipt_chain_helper_and_badge_wiring():
    """app.js computes chain state + paints the chain row and badge."""
    js = (ROOT / "static/app.js").read_text()
    assert "w2v2Chain" in js, "chain render helper w2v2Chain missing"
    assert "chain_ok" in js, "chain_ok field unread in app.js"
    assert "prev_receipt_sha" in js, "prev_receipt_sha link unread in app.js"
    assert "fact-receipt-chain" in js, "chain row never painted"
    assert "receipt-chain-badge" in js, "verify badge never painted"
    assert "chain ok" in js.lower(), "chain-ok token missing from one-liner"
    assert "chain broken" in js.lower(), "chain-broken token missing"


def test_app_js_receipt_one_liner_is_sha12():
    """Receipt one-liner truncates the digest to 12 hex chars (tribunal ask)."""
    js = (ROOT / "static/app.js").read_text()
    assert "String(hash).slice(0, 12)" in js, "sha12 truncation missing in receipt one-liner"
    assert "String(hash).slice(0, 16)" not in js, "receipt sha16 must shrink to sha12"
