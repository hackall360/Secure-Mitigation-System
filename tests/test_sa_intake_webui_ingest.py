# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (slice/intake-36): WebUI ingest-mode parity — optional commit (HEAD default) + contract.

Parity directive (user, binding): ingest mode must offer BOTH spellings with a
zero-config demo default:

1. ``commit_hash`` OPTIONAL — ``REQUIRED.ingest`` drops ``commit_hash``; the
   field validator passes on empty (omitted = HEAD as-is) while a non-empty
   value must still be 40-hex.
2. Contract parity — the ingest source definition carries a ``contract`` field
   like CLI/MCP/library.
3. The compiled ingest body OMITS ``commit_hash`` when empty (HEAD as-is)
   rather than sending ``""``.
4. setup-prod.js ingest display shows ``HEAD (default branch)`` when no commit
   is given and ``host @ sha[:12]`` when pinned — never the full URL (LAW-4);
   prod-setup.html gains no inline handlers (CSP ``script-src 'self'``).

Static assertions only (text + ``node --check`` + a small node harness that
loads schema.js/compile.js with a window stub — no browser needed).
"""

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / "web" / "js" / "options" / "schema.js"
COMPILE = REPO / "web" / "js" / "options" / "compile.js"
SETUP_PROD = REPO / "web" / "js" / "pages" / "setup-prod.js"
HTML = REPO / "web" / "prod-setup.html"
NODE = "node"

GOOD_SHA = "9ff342479591ca5a43cb30000195bcf55c1bbed9"

_NODE_HARNESS = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(%s, 'utf8'));
eval(fs.readFileSync(%s, 'utf8'));
const O = window.SMS.options;
const out = {};
out.requiredIngest = O.REQUIRED.ingest;
out.ingestFields = O.SOURCES.ingest.fields;
out.ingestSub = O.SOURCES.ingest.sub;
out.emptyErr = O.FIELDS.commit_hash.validate('', {});
out.goodErr = O.FIELDS.commit_hash.validate(%s, {});
out.shortErr = O.FIELDS.commit_hash.validate('abc123', {});
out.nonHexErr = O.FIELDS.commit_hash.validate('z'.repeat(40), {});
out.emptyBody = O.compile('ingest',
  { ingest_repo: 'https://github.com/org/repo', commit_hash: '' }, {}).body;
out.pinnedBody = O.compile('ingest',
  { ingest_repo: 'https://github.com/org/repo', commit_hash: %s }, {}).body;
console.log(JSON.stringify(out));
""" % (
    json.dumps(str(SCHEMA)),
    json.dumps(str(COMPILE)),
    json.dumps(GOOD_SHA),
    json.dumps(GOOD_SHA),
)


def _probe():
    proc = subprocess.run(
        [NODE, "-e", _NODE_HARNESS],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=60,
    )
    assert proc.returncode == 0, f"node harness failed:\n{proc.stderr}"
    return json.loads(proc.stdout)


def test_required_ingest_omits_commit_hash():
    assert _probe()["requiredIngest"] == ["ingest_repo"]


def test_commit_validate_empty_passes_bad_fails():
    probe = _probe()
    assert probe["emptyErr"] == "", "empty commit_hash must validate clean (HEAD as-is)"
    assert probe["goodErr"] == "", "40-hex commit_hash must validate clean"
    assert probe["shortErr"] != "", "short commit_hash must still error"
    assert probe["nonHexErr"] != "", "non-hex 40-char commit_hash must still error"


def test_ingest_fields_include_contract():
    assert "contract" in _probe()["ingestFields"]


def test_compile_omits_empty_commit_hash():
    probe = _probe()
    assert probe["emptyBody"]["ingest_repo"] == "https://github.com/org/repo"
    assert "commit_hash" not in probe["emptyBody"], (
        "empty commit_hash must be omitted (HEAD as-is), not sent as ''"
    )
    assert probe["pinnedBody"]["commit_hash"] == GOOD_SHA


def test_ingest_source_sub_mentions_head():
    probe = _probe()
    assert probe["ingestSub"] == "HEAD or pinned commit"


def test_setup_prod_ingest_display_head_default():
    text = SETUP_PROD.read_text(encoding="utf-8")
    assert "HEAD (default branch)" in text
    assert "hostname" in text, "ingest display must derive host, never the full URL"
    assert "@ ${sha.slice(0, 12)}" in text or "@ ${sha" in text or "sha.slice(0, 12)" in text


def test_prod_setup_html_ingest_markup_no_inline_handlers():
    html = HTML.read_text(encoding="utf-8")
    assert "HEAD or pinned commit" in html
    bad = [line.strip()[:80] for line in html.splitlines() if re.search(r"""\son\w+\s*=""", line)]
    assert not bad, "inline handlers blocked by CSP:\n" + "\n".join(bad)


def test_node_check_passes_on_edited_js():
    for path in (SCHEMA, COMPILE, SETUP_PROD):
        proc = subprocess.run(
            [NODE, "--check", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, f"node --check failed for {path}:\n{proc.stderr}"
