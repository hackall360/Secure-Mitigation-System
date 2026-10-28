def test_parse_build_intent_splits_cve_named_free():
    from demo_gen import parse_build_intent

    intent = parse_build_intent(
        build_brief="a tiny notes app",
        vulns="CVE-2024-3094, sqli, weird header thing",
        theme="xss",
    )
    assert intent.build_brief == "a tiny notes app"
    assert intent.themes == ["xss"]
    assert intent.cve_ids == ["CVE-2024-3094"]
    assert intent.named_types == ["SQL injection"]
    assert intent.free_text == ["weird header thing"]
    assert intent.vulns == ["CVE-2024-3094", "SQL injection", "weird header thing"]


def test_parse_build_intent_case_punctuation_duplicates():
    from demo_gen import parse_build_intent

    intent = parse_build_intent(vulns="cve-2021-44228 log4shell; XSS!!!, sqli, SQL-INJECTION")
    assert intent.cve_ids == ["CVE-2021-44228"]
    assert "SQL injection" in intent.named_types
    assert intent.named_types.count("SQL injection") == 1
    assert "Log4Shell (CVE-2021-44228)" in intent.named_types


def test_parse_build_intent_bare_cve_has_no_free_text():
    from demo_gen import parse_build_intent

    intent = parse_build_intent(vulns="CVE-2024-3094")
    assert intent.cve_ids == ["CVE-2024-3094"]
    assert intent.free_text == []


def test_generate_demo_project_carries_intent_into_payload(monkeypatch):
    """I5 wiring: brief + requested flaws reach the generator payload."""
    import demo_gen as _dg

    captured = {}

    class FakeClient:
        config = type("C", (), {"red_team_model": "muse-spark-1.3"})()

        async def _request(self, model, system, payload, schema, **kwargs):
            captured["payload"] = payload
            return _dg.DemoProjectFiles(
                app_py="x = 1\n",
                test_contract_py="assert True\n",
                contract="c",
                flaw_notes=["SQL injection at /q"],
                cve_inspiration=["CVE-2024-3094"],
            )

    import asyncio as _aio

    files = _aio.run(
        _dg.generate_demo_project(
            FakeClient(),
            intel_context=[{"cve_id": "CVE-2024-3094"}],
            theme="notes app",
            build_brief="a tiny notes app",
            vulns=["CVE-2024-3094", "SQL injection"],
        )
    )
    assert files.cve_inspiration == ["CVE-2024-3094"]
    assert "notes app" in captured["payload"]["build_brief"]
    assert "CVE-2024-3094" in captured["payload"]["requested_vulns"]
