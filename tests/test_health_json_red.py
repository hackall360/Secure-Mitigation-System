# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: json stdout purity (F-03), health busy lock (F-04), example.env drift (F-05).

LAWs 0/2/3/4/6/9/10 govern: red-first, surgical diffs, no truncation.
SCOPE: main.py cli_runner/_health_report, example.env, this file only.

F-03: cli_runner json mode must keep stdout machine-pure (report JSON only);
  the "[SYSTEM] Report:" chatter line must ride stderr via _out.
F-04: _health_report must reflect the live WS scan lock when provided
  (keyword-only scan_lock=None default keeps CLI callers truthful-idle).
F-05: every PURPLEBOX_* name load_config reads from env (except the
  intentionally-defaulted infra knobs pinned by test_config_dead_knobs_red)
  must have a template line in example.env.
"""

import inspect
import json
import re
from pathlib import Path
from types import SimpleNamespace

import main
from modules.core.config import PurpleBoxConfig
from modules.core.pricing import ScanUsage

REPO_ROOT = Path(main.__file__).resolve().parent


def _result(**over):
    payload = {
        "target": "node_query_sink",
        "status": "verified",
        "message": "Probe blocked",
        "diff": "--- a/app.js\n+++ b/app.js\n@@ -1 +1 @@\n-old\n+new\n",
        "cleanup_ok": True,
        "pre_exit_code": 0,
        "post_exit_code": 1,
        "baseline_passed": True,
        "regression_passed": True,
        "cycles": [],
        "total_tokens": 11,
        "cost_usd": 0.0001,
    }
    payload.update(over)
    return SimpleNamespace(
        **payload,
        usage=ScanUsage(),
        success=True,
        model_dump=lambda: dict(payload),
    )


class _Locked:
    def locked(self):
        return True


class _Unlocked:
    def locked(self):
        return False


# F-03: json-mode scan with output_dir must leave stdout as pure JSON.
async def test_json_mode_report_line_goes_to_stderr(monkeypatch, tmp_path, capsys):
    async def workflow(target, emit, **kwargs):
        return _result()

    monkeypatch.setattr(main, "execute_purple_workflow", workflow)
    monkeypatch.setattr(main, "load_config", lambda: PurpleBoxConfig())
    out_dir = tmp_path / "runs"
    rc = await main.cli_runner("node_query_sink", output_dir=out_dir, out_format="json")
    assert rc == 0
    captured = capsys.readouterr()
    # Full stdout must parse as one JSON document (purity).
    payload = json.loads(captured.out)
    assert payload["status"] == "verified"
    # The chatter line must ride stderr, never stdout.
    assert "Report:" in captured.err
    assert "Report:" not in captured.out


# F-03 sibling check: cli_runner body must route all chatter through _out/stderr.
def test_cli_runner_has_no_bare_stdout_prints():
    src = inspect.getsource(main.cli_runner)
    lines = src.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("print("):
            depth = lines[i].count("(") - lines[i].count(")")
            stmt = [lines[i]]
            while depth > 0 and i + 1 < len(lines):
                i += 1
                stmt.append(lines[i])
                depth += lines[i].count("(") - lines[i].count(")")
            text = "\n".join(stmt)
            # The json payload dumps are the sanctioned bare prints: fixture
            # path (user_report) and CVE path (cve_result-shaped payload).
            # Everything else must route via _out (stderr in json mode).
            if "json.dumps(user_report" not in text and '"target": cve_result.target' not in text:
                assert "file=" in text, f"bare stdout print in cli_runner: {text.strip()[:200]}"
        i += 1


# F-04: busy follows the live lock when provided; stays False without one
# (plain --health CLI runs with no server, so False is truthful there).
def test_health_report_busy_follows_scan_lock():
    # F-209: busy is the scan-phase flag, not lock.locked() (the acquire
    # handoff left locked() True while no scan ran). scan_lock kwarg is
    # legacy and ignored; busy= drives the verdict.
    assert main._health_report(PurpleBoxConfig(), busy=True)["busy"] is True
    assert main._health_report(PurpleBoxConfig(), busy=False)["busy"] is False
    assert main._health_report(PurpleBoxConfig())["busy"] is False


# F-04: the serve-path health snapshot must see the real lock.
def test_serve_path_health_uses_live_lock():
    src = inspect.getsource(main.create_app)
    assert "scan_lock" in src, "serve app must track the WS scan lock"
    assert "scan_phase" in src, "serve-path health must report the scan phase (F-209)"
    assert re.search(r"_health_report\([\s\S]*?busy", src), (
        "serve-path _health_report call must receive the scan-phase busy flag"
    )


# F-05: every env-read PURPLEBOX_* knob (outside the intentionally-pinned
# infra set) must have a template line in example.env.
_PINNED_INFRA = {
    "PURPLEBOX_TARGET_IMAGE",
    "PURPLEBOX_VERIFIER_IMAGE",
    "PURPLEBOX_BINARY_IMAGE",
    "PURPLEBOX_CLONE_PREFIX",
    "PURPLEBOX_MEM_LIMIT",
    "PURPLEBOX_CPU_NANO",
    "PURPLEBOX_NETWORK_PREFIX",
    "PURPLEBOX_MAX_SOURCE_BYTES",
}


def test_example_env_covers_env_read_purplebox_knobs():
    import library.core.config as config_mod

    load_src = inspect.getsource(config_mod.load_config)
    read_names = set(re.findall(r'os\.getenv\("([A-Z0-9_]+)"', load_src))
    purplebox = {n for n in read_names if n.startswith("PURPLEBOX_")} - _PINNED_INFRA
    assert purplebox, "load_config must read at least one PURPLEBOX_* knob"
    env_text = (REPO_ROOT / "example.env").read_text(encoding="utf-8")
    missing = sorted(n for n in purplebox if n not in env_text)
    assert not missing, f"example.env omits template lines for: {missing}"
