# mcp/ — Model Context Protocol surface (category map, files stay pinned)

`mcp/` is a documented category, not a moved directory (physical `mcp/`
marker dirs were attempted and reverted 06:15 UTC: a `tui/` package shadows
root `tui.py` and breaks `import tui`; symmetric map-only is the gate-safe
form). Pins:
`test_mcp_server.py` (`import main as app_module`, `monkeypatch.setattr("main.*")`),
`test_library_api.py`, `test_mcp_demo_red.py`.

| member | path (post-`library/` rename) | what |
|---|---|---|
| bridge | `library/services/mcp_bridge.py` | `submit_code_snippet` executor over the red/blue Docker loop |
| library API | `library/services/sms_api.py` | `scan_source`, `scan_binary`, `query_vault_stats`, `verify_receipt` |
| STDIO server | `main.py --mcp` | 5-tool handshake (`sms_*`) |
| HTTP endpoint | `main.py POST /mcp` | Streamable HTTP JSON-RPC, language allowlist + 64 KiB cap |
| dashboard mode | `static/` MCP mode + form + POST client | same envelope as STDIO |
| terminal demo | `scripts/mcp_client_demo.py` | `tui/demo-client` member too (shared surface) |

New code goes in `library/services/`; this map is the `mcp/` index.
