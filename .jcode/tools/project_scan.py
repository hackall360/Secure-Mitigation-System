#!/usr/bin/env python3
# Exercise arbitrary-project two-cycle remediation through real Docker with deterministic Muse HTTP replies.
# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""No inference credentials or network calls. Temporary projects are never modified by scans."""

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path

# ruff: noqa: E402
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import httpx

from agents import MetaMuseClient
from config import PurpleBoxConfig
from project_workflow import execute_project_workflow
from projects import ProjectSpec

APP = """from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit
from src.boundaries import lookup, echo

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlsplit(self.path).query)
        try:
            if self.path.startswith('/lookup'):
                answer = lookup(query.get('id', ['101'])[0])
            else:
                answer = echo(query.get('value', ['hello'])[0])
            self.send_response(200)
        except ValueError:
            answer = 'blocked'
            self.send_response(400)
        self.end_headers()
        self.wfile.write(answer.encode())

HTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
"""

ORIGINAL = """import sqlite3

def lookup(raw):
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE accounts (id INTEGER, name TEXT)')
    db.executemany('INSERT INTO accounts VALUES (?, ?)', [(101, 'Alice'), (102, 'Bob')])
    return ','.join(row[0] for row in db.execute('SELECT name FROM accounts WHERE id = ' + raw))

def echo(raw):
    return str(eval(raw, {'__builtins__': {}}, {}))
"""

PATCH_ONE = ORIGINAL.replace(
    "db.execute('SELECT name FROM accounts WHERE id = ' + raw)",
    "db.execute('SELECT name FROM accounts WHERE id = ?', (raw,))",
)
PATCH_TWO = PATCH_ONE.replace(
    "    return str(eval(raw, {'__builtins__': {}}, {}))",
    "    if not raw.isdecimal():\n        raise ValueError('decimal input required')\n    return str(int(raw))",
)

REGRESSION = """from src.boundaries import lookup, echo
assert lookup('101') == 'Alice'
assert lookup('102') == 'Bob'
assert lookup('999') == ''
assert echo('123') == '123'
print('normal-input checks passed')
"""


def probe(cycle):
    route = "lookup?id=101%20OR%201%3D1" if cycle == 1 else "echo?value=40%2B2"
    expected = "Alice,Bob" if cycle == 1 else "42"
    return f"""import sys, time, urllib.request, urllib.error
for attempt in range(40):
    try:
        response = urllib.request.urlopen('http://target-service:8080/{route}', timeout=1)
        text = response.read().decode()
        print('observed:', text)
        sys.exit(0 if text == {expected!r} else 1)
    except urllib.error.HTTPError as error:
        if error.code == 400:
            print('input blocked')
            sys.exit(1)
        raise
    except urllib.error.URLError:
        time.sleep(0.1)
sys.exit(2)
"""


def fake_transport(request):
    body = json.loads(request.content)
    assert len(body["messages"]) == 2, "A stage reused conversation context"
    payload = json.loads(body["messages"][1]["content"])
    assert str(ROOT) not in body["messages"][1]["content"], "Host path leaked to inference"
    system = body["messages"][0]["content"]
    cycle = payload.get("cycle", 1)
    candidate = {
        "vulnerability": "SQL injection" if cycle == 1 else "expression injection",
        "affected_paths": ["src/boundaries.py"],
        "evidence": "Untrusted text reaches an expression without validation.",
        "verification_script_python": probe(cycle),
        "confidence": "high",
    }
    no_finding = {
        "outcome": "no_finding",
        "analysis_summary": "Independent bounded review found no new candidate.",
        "limitations": ["Deterministic test reply, not a real security assessment."],
    }
    if "batch" in payload:
        answer = {
            "candidates": [] if payload.get("phase") == "verification" else [candidate],
            "observations": [],
            "no_candidate_reason": "Deterministic test review",
        }
    elif "evidence_digests" in payload:
        answer = (
            no_finding
            if payload.get("phase") == "verification"
            else {
                "outcome": "finding",
                "vulnerability": candidate["vulnerability"],
                "affected_paths": candidate["affected_paths"],
                "analysis_summary": candidate["evidence"],
                "verification_script_python": probe(cycle),
                "limitations": [],
            }
        )
    elif "safe_snapshot_files" in payload:
        original = ORIGINAL if cycle == 1 else PATCH_ONE
        answer = {
            "strategy": "Parameterize SQL" if cycle == 1 else "Allowlist decimal input",
            "replacements": [
                {
                    "path": "src/boundaries.py",
                    "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
                    "replacement_content": PATCH_ONE if cycle == 1 else PATCH_TWO,
                    "rationale": "Harden only the demonstrated input boundary.",
                    "change_kind": "parameterization" if cycle == 1 else "input_validation",
                }
            ],
            "limitations": [],
        }
    elif "stage_evidence" in payload:
        evidence = payload["stage_evidence"]
        answer = {
            "disposition": evidence["disposition"],
            "summary": "Original probe blocked and normal-input regression passed."
            if evidence["disposition"] == "retained"
            else "No verified change retained.",
            "evidence": ["See recorded Docker exit codes."],
            "changed_paths": ["src/boundaries.py"] if evidence["disposition"] == "retained" else [],
            "limitations": ["Finite deterministic acceptance test, not live inference."],
        }
    else:
        raise AssertionError(f"Unexpected stage request: {system[:80]} {list(payload)}")
    return httpx.Response(
        200,
        json={
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(answer)}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )


async def run(output):
    config = PurpleBoxConfig(
        inference_mode="local",
        meta_base_url="http://127.0.0.1:8081/v1",
        verifier_timeout_seconds=20,
    )
    with tempfile.TemporaryDirectory(prefix="purplebox-project-", dir=output) as directory:
        project = Path(directory)
        (project / "src").mkdir()
        (project / "src" / "__init__.py").write_text("")
        (project / "src" / "boundaries.py").write_text(ORIGINAL)
        (project / "app.py").write_text(APP)
        (project / "test_contract.py").write_text(REGRESSION)
        (project / ".env").write_text("TEST_SECRET=must-not-be-snapshotted\n")
        spec = ProjectSpec(
            path=project,
            command=["python3", "app.py"],
            test_command=["python3", "test_contract.py"],
            contract="HTTP service at target-service:8080. Preserve lookup 101=Alice, 102=Bob, 999 empty and echo decimal input. Only sanitize input.",
            cycles=2,
        )

        async def emit(team, message):
            print(f"[{team}] {message}", flush=True)

        result = await execute_project_workflow(
            spec,
            emit,
            config=config,
            muse_factory=lambda settings: MetaMuseClient(
                settings, transport=httpx.MockTransport(fake_transport)
            ),
        )
        report = result.model_dump()
        (output / "project-acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
        assert (project / "src" / "boundaries.py").read_text() == ORIGINAL, (
            "Original project was modified"
        )
        assert result.success, report.get("message")
        assert report["cycles_completed"] == 2, report
        cycles = report.get("cycles", report.get("cycle_reports", []))
        assert all(item["status"] == "retained" for item in cycles), report
        assert report.get("cleanup_ok", report.get("cleanup", {}).get("succeeded")), report
        assert "db.execute" in report.get("diff", report.get("cumulative_diff", "")), report
        print(
            "PASS: two distinct boundaries, two cumulative patches, original source unchanged, isolated execution, independent contexts, cleanup",
            flush=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports" / "project-acceptance")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    asyncio.run(run(args.output_dir.resolve()))


if __name__ == "__main__":
    main()
