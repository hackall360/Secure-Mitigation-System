# tui/ — terminal surface (category map, files stay pinned)

`tui/` is a documented category, not a moved directory (a physical `tui/`
package would shadow root `tui.py` and break `import tui` — attempted and
reverted 06:15 UTC). Pins: `import tui`
in 6 test files + `from tui import main` in `main.py:2794`; `scripts.*`
namespace asserted by `test_mcp_demo_red.py`; CLI output asserted by
`test_cli_parity.py`.

## tui/interactive/ ≡ `tui.py` (pinned, do not move)

Curses 80x24 + `run_plain` fallback; `TuiState`, `parse_key`,
`apply_action`, `render_panes`, `prompt_line`, mode dispatch threads.
String-form seam: `sys.modules.get("modules.workflows.*")` (~ll.1009-1016) —
mockable without importing heavy deps. Keep the `modules.*` spelling so the
seam keeps matching fakes.

## tui/cli/ ≡ `sms_cli.py` + `main.py` argparse (pinned, do not move)

`sms_cli.py` helpers (`Spinner`, `fact_table`, `health_table`,
`load_config_file`, `merge_config`) imported by `main.py:43-52` and lazily
(`format_wave2_facts` at `main.py:2275`); every `--flag` + `--help` text
pinned by `test_cli_parity.py`.

## tui/demo-client/ ≡ `scripts/mcp_client_demo.py` (pinned, do not move)

Terminal MCP demo: `run_demo(base_url, filename, language, source)` →
`{status, pre_probe_exit, post_probe_exit, receipt_sha}`; `--help` mentions
`/mcp`; dead-port fails closed; 64 KiB cap enforced before HTTP.
