def test_parse_build_intent_splits_cve_named_free():
    from modules.services.demo_gen import parse_build_intent

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
    from modules.services.demo_gen import parse_build_intent

    intent = parse_build_intent(vulns="cve-2021-44228 log4shell; XSS!!!, sqli, SQL-INJECTION")
    assert intent.cve_ids == ["CVE-2021-44228"]
    assert "SQL injection" in intent.named_types
    assert intent.named_types.count("SQL injection") == 1
    assert "Log4Shell (CVE-2021-44228)" in intent.named_types


def test_parse_build_intent_bare_cve_has_no_free_text():
    from modules.services.demo_gen import parse_build_intent

    intent = parse_build_intent(vulns="CVE-2024-3094")
    assert intent.cve_ids == ["CVE-2024-3094"]
    assert intent.free_text == []


def test_parse_build_intent_no_phantom_sinks_from_separator_fragments():
    """aa09566 hunk 1: separator fragments stay free text, never phantom sinks.

    'path/traversal' splits at '/' into the fragments 'path' and 'traversal',
    which the old substring fallback matched because 'path' in '...path
    traversal' — inventing a path-traversal sink the user never requested.
    Only the explicitly named command-injection survives.
    """
    from modules.services.demo_gen import parse_build_intent

    intent = parse_build_intent(vulns="path/traversal plus command-injection")
    assert intent.named_types == ["OS command injection"]
    assert "path traversal" not in intent.named_types


def test_parse_build_intent_no_phantom_sinks_from_hypernyms():
    """aa09566 hunk 1: bare hypernyms stay free text, never phantom sinks.

    The old substring fallback matched 'injection' inside every '...X
    injection' alias (7 phantom types), 'header' inside 'header
    injection'/'header reflection', and 'site' inside 'cross site
    scripting' — inventing sinks the user never named.
    """
    from modules.services.demo_gen import parse_build_intent

    for hypernym in ("injection", "header", "site"):
        intent = parse_build_intent(vulns=hypernym)
        assert intent.named_types == [], hypernym
        assert intent.free_text == [hypernym], hypernym


def test_parse_build_intent_whole_word_aliases_still_match():
    """aa09566 hunk 1: the whole-word restriction keeps every tested case green."""
    from modules.services.demo_gen import parse_build_intent

    assert parse_build_intent(vulns="sqli").named_types == ["SQL injection"]
    assert parse_build_intent(vulns="XSS!!!").named_types == ["cross-site scripting"]
    assert parse_build_intent(vulns="SQL-INJECTION").named_types == ["SQL injection"]
    assert parse_build_intent(vulns="log4shell").named_types == ["Log4Shell (CVE-2021-44228)"]
    assert parse_build_intent(vulns="command-injection").named_types == ["OS command injection"]
    assert parse_build_intent(vulns="deserialization vuln").named_types == [
        "insecure deserialization"
    ]


def test_generate_demo_project_carries_intent_into_payload(monkeypatch):
    """I5 wiring: brief + requested flaws reach the generator payload."""
    import modules.services.demo_gen as _dg

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


def _run_generate(**kwargs):
    """Shared fake-client harness: capture the Muse payload, return (files, payload)."""
    import asyncio as _aio

    import modules.services.demo_gen as _dg

    captured = {}

    class FakeClient:
        config = type("C", (), {"red_team_model": "muse-spark-1.3"})()

        async def _request(self, model, system, payload, schema, **kwargs):
            captured["payload"] = payload
            captured["system"] = system
            return _dg.DemoProjectFiles(
                app_py="x = 1\n",
                test_contract_py="assert True\n",
                contract="c",
            )

    files = _aio.run(_dg.generate_demo_project(FakeClient(), intel_context=[], **kwargs))
    return files, captured["payload"], captured["system"]


def test_generate_demo_project_flaw_count_slices_wanted():
    """L3: flaw_count=2 with 5 vulns -> payload requested_vulns len 2."""
    _, payload, _ = _run_generate(
        vulns=["a", "b", "c", "d", "e"],
        flaw_count=2,
    )
    assert len(payload["requested_vulns"]) == 2
    assert payload["flaw_count"] == 2


def test_generate_demo_project_flaw_count_clamps_to_8():
    """L3: flaw_count=99 clamps to 8, never raises, payload capped."""
    _, payload, _ = _run_generate(
        vulns=["v%d" % i for i in range(10)],
        flaw_count=99,
    )
    assert payload["flaw_count"] == 8
    assert len(payload["requested_vulns"]) == 8


def test_generate_demo_project_bad_size_falls_back_and_seed_passes_through():
    """L3: size='bogus' -> payload demo_size 'standard', seed passed through."""
    _, payload, _ = _run_generate(vulns=["a", "b"], size="bogus", seed=42)
    assert payload["demo_size"] == "standard"
    assert payload["seed"] == 42


def test_generate_demo_project_defaults_match_current_behavior():
    """L3: defaults -> demo_size 'standard', flaw_count == len(requested)."""
    _, payload, system = _run_generate(vulns=["a", "b", "c"])
    assert payload["demo_size"] == "standard"
    assert payload["flaw_count"] == len(payload["requested_vulns"]) == 3
    assert payload["seed"] is None
    assert "demo_size" in system and "variation nonce" in system


def test_generate_demo_project_never_raises_on_garbage():
    """L3: invalid flaw_count/size/seed types never raise, fall back sanely."""
    _, payload, _ = _run_generate(vulns=["a"], size=123, flaw_count="xx", seed="yy")
    assert payload["demo_size"] == "standard"
    assert payload["requested_vulns"] == ["a"]
    assert payload["seed"] is None
