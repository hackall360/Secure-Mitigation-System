# Verify new dashboard controls (MCP/sweep/binary modes) are operable in headless Firefox.
"""LAW 11: operate new M2/M3/M4 dashboard controls via execute/sync JS."""

import json
import shutil
import subprocess
import sys
import time
import urllib.request

PORT = 18099
GD_PORT = 19501


def main() -> int:
    sys.path.insert(0, ".")
    sys.path.insert(0, ".jcode/tools")
    from ui_scan import wd_request  # noqa: E402 (path bootstrap like other tools)

    server = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, '.'); import uvicorn; "
            "from main import create_app; "
            "from modules.core.config import PurpleBoxConfig; "
            f"uvicorn.run(create_app(PurpleBoxConfig(meta_api_key='browser-check-not-a-key')), "
            f"host='127.0.0.1', port={PORT}, log_level='warning')",
        ],
        cwd=".",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(4)
    gecko = shutil.which("geckodriver")
    gd = subprocess.Popen(
        [gecko or "geckodriver", "--port", str(GD_PORT), "--host", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    session: str | None = None
    try:
        base = f"http://127.0.0.1:{GD_PORT}"
        for _ in range(50):
            try:
                if wd_request(base, "GET", "/status")["value"].get("ready"):
                    break
            except OSError:
                time.sleep(0.2)
        session = wd_request(
            base,
            "POST",
            "/session",
            {
                "capabilities": {
                    "alwaysMatch": {
                        "browserName": "firefox",
                        "moz:firefoxOptions": {"args": ["-headless"]},
                    }
                }
            },
        )["value"]["sessionId"]

        def run_js(script: str):
            return wd_request(
                base, "POST", f"/session/{session}/execute/sync", {"script": script, "args": []}
            )["value"]

        run_js(f"window.location.href = 'http://127.0.0.1:{PORT}/'; return true;")
        for _ in range(60):
            if run_js(
                "return document.getElementById('run-btn') !== null "
                "&& !document.getElementById('run-btn').disabled"
            ):
                break
            time.sleep(0.5)
        results = run_js("""return (() => {
      const out = {};
      document.querySelector('[data-mode="mcp"]').click();
      out.mcp_form_visible = !document.getElementById('mcp-form').hidden;
      document.getElementById('run-btn').click();
      out.mcp_errors_visible = !document.getElementById('mcp-errors').hidden;
      out.mcp_errors_text = document.getElementById('mcp-errors').textContent.slice(0, 60);
      out.sweep_options = [...document.getElementById('sweep-passes').options].map(o => o.value);
      document.querySelector('[data-mode="binary"]').click();
      out.binary_form_visible = !document.getElementById('binary-form').hidden;
      out.binary_file_type = document.getElementById('binary-file').type;
      return out;
    })()""")
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/mcp",
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        results["mcp_tools"] = [
            t["name"] for t in json.load(urllib.request.urlopen(req))["result"]["tools"]
        ]
        print("BROWSER-CONTROLS:", json.dumps(results, indent=1))
        assert results["mcp_form_visible"] and results["mcp_errors_visible"], results
        assert results["sweep_options"] == ["1", "2", "3"], results
        assert results["binary_form_visible"] and results["binary_file_type"] == "file", results
        # V1 Subsystem E shipped 5 MCP tools (submit_code_snippet + sms_*); assert order-independent superset.
        expected_tools = {
            "submit_code_snippet",
            "sms_scan_source",
            "sms_scan_binary",
            "sms_query_vault_stats",
            "sms_verify_receipt",
        }
        assert expected_tools.issubset(set(results["mcp_tools"])), results
        assert set(results["mcp_tools"]) == expected_tools, results
        print("BROWSER-CONTROLS: PASS all new controls operable")
        wd_request(base, "DELETE", f"/session/{session}", None)
        return 0
    finally:
        gd.terminate()
        gd.wait()
        server.terminate()
        server.wait()


if __name__ == "__main__":
    raise SystemExit(main())
