# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first intel gap tests (verification sweep, P3 `library/intel/`).

LAWs 9 + 10F govern this file: REAL behavior, no network, no library edits.
All HTTP/subprocess boundaries are faked at the seam the existing intel
tests already use (module-level `_get_json` / `_post_json` /
`paced_request_json` / `subprocess.run` doubles); payloads are CANNED, so
every assertion below pins a live-but-offline code path:

G1 vault crypto fail-closed: short key refuses at encrypt_blob (line 131)
   AND decrypt_blob (line 147); truncated/wrong-version envelope fails.
G2 vault store guards: malformed record id refused (line 223); non-mapping
   commit refused (line 276); empty-key decrypt refused (line 147).
G3 vault query fail-closed on total tamper: every blob undecryptable ->
   VaultError, never a silent NOVEL (lines 341-342).
G4 OSV package lookup maps real canned vulns (lines 138-173) incl. alias
   CVE choice, severity score, reference URLs, bounded limit.
G5 GHSA first-patched-version nesting: top-level str / dict identifier /
   nested vulnerabilities[] / absent -> "" (lines 258-275).
G6 NVD summarize maps a canned CVE item (lines 141-172): en description,
   cvssMetricV31 baseScore/vector/severity, CWE list, reference rows; and
   summarize_nvd_search skips a malformed row (lines 184-188).
G7 dtrack scan_packages polls to project UUID with faked transport
   (lines 204-245) and build_bom truncates/skips (line 140-160).
G8 scanner runner failure reasons: timeout/empty/oversize/bad-json all
   degrade _run_json to None (lines 168-184) with last_reason set.

RED expectation: each test asserts REAL post-fix behavior. If a test
fails on a REAL library defect the run stops and the sweep classifies
[FT] without touching library/. L2 = this file's RED run documented
below; L1 = full green after (no library edits permitted here).
"""

import json

import pytest


# ---------------------------------------------------------------------------
# G1: vault crypto fail-closed
# ---------------------------------------------------------------------------


def test_encrypt_blob_refuses_short_key():
    from modules.intel.sms_vault import VaultError
    from modules.intel.sms_vault import encrypt_blob

    with pytest.raises(VaultError, match="32 bytes"):
        encrypt_blob({"a": 1}, key=b"\x01" * 16)


def test_decrypt_blob_refuses_short_key():
    from modules.intel.sms_vault import VaultError
    from modules.intel.sms_vault import decrypt_blob

    with pytest.raises(VaultError, match="32 bytes"):
        decrypt_blob(b"{}", key=b"\x01" * 8)


def test_decrypt_blob_rejects_truncated_envelope(tmp_path):
    from modules.intel.sms_vault import VaultError
    from modules.intel.sms_vault import decrypt_blob
    from modules.intel.sms_vault import encrypt_blob

    key = b"\x02" * 32
    blob = encrypt_blob({"kind": "boundary_escape", "sink": "eval(x)"}, key=key)
    tampered = blob[: len(blob) // 2]
    with pytest.raises(VaultError, match="authentication"):
        decrypt_blob(tampered, key=key)


# ---------------------------------------------------------------------------
# G2: vault store guards
# ---------------------------------------------------------------------------


def test_blob_path_rejects_malformed_record_id(tmp_path):
    from modules.intel.sms_vault import VaultError
    from modules.intel.sms_vault import VaultNamespace
    from modules.intel.sms_vault import VaultStore

    store = VaultStore(namespace=VaultNamespace.RED, vault_dir=tmp_path / "v")
    with pytest.raises(VaultError, match="malformed"):
        store.fetch("../escape")
    with pytest.raises(VaultError, match="malformed"):
        store.fetch("NOT-HEX-AT-ALL-xxxxxxxxxxxxxxxx")


def test_commit_refuses_non_mapping_payload(tmp_path):
    from modules.intel.sms_vault import VaultError
    from modules.intel.sms_vault import VaultNamespace
    from modules.intel.sms_vault import VaultStore

    store = VaultStore(namespace=VaultNamespace.BLUE, vault_dir=tmp_path / "v")
    with pytest.raises(VaultError, match="mapping"):
        store.commit(["not", "a", "mapping"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# G3: total-tamper query fails closed
# ---------------------------------------------------------------------------


def test_query_vault_raises_when_all_blobs_tampered(tmp_path):
    """Every blob undecryptable -> VaultError, never silent NOVEL_SURFACE."""
    from modules.intel import sms_vault as vault

    vault_dir = tmp_path / "v"
    store = vault.VaultStore(namespace=vault.VaultNamespace.RED, vault_dir=vault_dir)
    rid = store.commit({"kind": "boundary_escape", "sink": "eval(x)"}, fingerprint="fp-t")
    (vault_dir / "red" / f"{rid}.vault").write_bytes(b"tampered-bytes")
    (vault_dir / "red" / "_fingerprints.json").unlink(missing_ok=True)
    with pytest.raises(vault.VaultError, match="decryptable"):
        store.record_fingerprints()


# ---------------------------------------------------------------------------
# G4: OSV package lookup maps canned vulns (mock HTTP boundary only)
# ---------------------------------------------------------------------------


def _canned_osv_query():
    return {
        "vulns": [
            {
                "id": "OSV-2024-1",
                "aliases": ["CVE-2024-3094", "GHSA-x"],
                "summary": "xz backdoor",
                "details": "fallback details",
                "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L"}],
                "references": [{"url": "https://example.invalid/osv"}],
            },
            "not-a-dict-row",
            {
                "id": "OSV-2024-2",
                "aliases": [],
                "summary": "",
                "details": "no alias keeps raw id",
                "severity": [],
                "references": [{"no_url": True}],
            },
        ]
    }


def test_osv_query_package_maps_alias_and_severity(monkeypatch):
    import modules.intel.research as _research

    calls = {}

    def fake_post(url, payload):
        calls["url"] = url
        calls["payload"] = payload
        return _canned_osv_query()

    monkeypatch.setattr(_research, "_post_json", fake_post)
    recs = _research.osv_query_package("xz", ecosystem="Debian", limit=3)
    assert calls["url"] == "https://api.osv.dev/v1/query"
    assert calls["payload"] == {"package": {"name": "xz", "ecosystem": "Debian"}}
    assert len(recs) == 2
    first, second = recs
    assert (first.source, first.cve_id) == ("osv", "CVE-2024-3094")
    assert first.title == "OSV-2024-1"
    assert first.severity == "CVSS:3.1/AV:N/AC:L"
    assert first.references == ("https://example.invalid/osv",)
    assert first.extra == {"aliases": ["CVE-2024-3094", "GHSA-x"]}
    assert (second.source, second.cve_id) == ("osv", "OSV-2024-2")
    assert second.summary == "no alias keeps raw id"
    assert second.references == ()


def test_osv_query_package_empty_name_never_posts(monkeypatch):
    import modules.intel.research as _research

    monkeypatch.setattr(
        _research, "_post_json", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no net"))
    )
    assert _research.osv_query_package("   ") == []


# ---------------------------------------------------------------------------
# G5: GHSA first-patched-version nesting
# ---------------------------------------------------------------------------


def test_ghsa_first_patched_version_branches():
    from modules.intel.research import _ghsa_first_patched_version as fpv

    assert fpv({"first_patched_version": "  5.6.2  "}) == "5.6.2"
    assert fpv({"first_patched_version": {"identifier": "1.2.3"}}) == "1.2.3"
    assert (
        fpv({"vulnerabilities": [{"first_patched_version": "9.9.9"}, {"junk": 1}]}) == "9.9.9"
    )
    assert (
        fpv({"vulnerabilities": [{"first_patched_version": {"identifier": "7.7.7"}}]})
        == "7.7.7"
    )
    assert fpv({"vulnerabilities": ["nope", {"first_patched_version": None}]}) == ""
    assert fpv({}) == ""


# ---------------------------------------------------------------------------
# G6: NVD summarize maps a canned CVE item
# ---------------------------------------------------------------------------


def _canned_nvd_item():
    return {
        "cve": {
            "id": "CVE-2024-3094",
            "descriptions": [
                {"lang": "es", "value": "no spanish"},
                {"lang": "en", "value": "xz backdoor malicious code"},
            ],
            "metrics": {
                "cvssMetricV31": [
                    {
                        "cvssData": {
                            "version": "3.1",
                            "baseScore": 9.0,
                            "vectorString": "CVSS:3.1/AV:N/AC:L",
                            "baseSeverity": "CRITICAL",
                        }
                    }
                ],
                "cvssMetricV2": [],
            },
            "weaknesses": [
                {"description": [{"lang": "en", "value": "CWE-506"}]},
                {"description": [{"lang": "en", "value": "CWE-506"}]},
            ],
            "published": "2024-03-29T00:00Z",
            "lastModified": "2024-04-01T00:00Z",
            "references": [{"url": "https://example.invalid/nvd", "source": "NVD"}],
        }
    }


def test_summarize_nvd_record_maps_canned_item():
    from modules.intel.intel_search import summarize_nvd_record

    out = summarize_nvd_record(_canned_nvd_item())
    assert out["cve_id"] == "CVE-2024-3094"
    assert out["description"] == "xz backdoor malicious code"
    assert out["published"] == "2024-03-29T00:00Z"
    assert out["cvss"] == [
        {
            "version": "3.1",
            "baseScore": "9.0",
            "vector": "CVSS:3.1/AV:N/AC:L",
            "severity": "CRITICAL",
        }
    ]
    assert out["cwe"] == ["CWE-506"]
    assert out["references"] == [{"url": "https://example.invalid/nvd", "source": "NVD"}]


def test_summarize_nvd_search_skips_malformed_row():
    from modules.intel.intel_search import summarize_nvd_search

    out = summarize_nvd_search(
        {"vulnerabilities": [_canned_nvd_item(), {"cve": None}, {"unexpected": "shape"}]},
        limit=5,
    )
    assert [row["cve_id"] for row in out if row["cve_id"]] == ["CVE-2024-3094"]


# ---------------------------------------------------------------------------
# G7: dtrack scan_packages happy path + bom guards (faked transport)
# ---------------------------------------------------------------------------


def test_build_bom_skips_blank_and_truncates():
    from modules.intel.scanner_dtrack import build_bom

    bom = build_bom("proj", [("django", "3.2"), ("   ", "9.9"), ("x" * 200, "1.0")])
    assert bom["bomFormat"] == "CycloneDX"
    assert [c["name"] for c in bom["components"]] == ["django", "x" * 128]
    assert bom["components"][0]["bom-ref"] == "django@3.2"


def test_scan_packages_polls_to_project_uuid(monkeypatch):
    import modules.intel.scanner_dtrack as _dt

    monkeypatch.setenv("PURPLEBOX_DTRACK_URL", "https://dtrack.internal")
    monkeypatch.setenv("PURPLEBOX_DTRACK_API_KEY", "k")
    calls = []

    def fake_request(base, key, method, path, body=None, **kw):
        calls.append((method, path, body))
        if path == "/api/v1/bom":
            assert body["projectName"] == "proj"
            assert json.loads(__import__("base64").b64decode(body["bom"]).decode())[
                "bomFormat"
            ] == "CycloneDX"
            return {"token": "tok-1"}
        if path.startswith("/api/v1/bom/token/"):
            return {"processing": True} if len(calls) < 3 else {"processing": False, "project": "uuid-9"}
        if path.startswith("/api/v1/finding/project/"):
            assert path.endswith("uuid-9")
            return [
                {
                    "vulnerability": {"vulnId": "CVE-2024-1", "severity": "HIGH"},
                    "component": {"name": "django", "version": "3.2"},
                    "analysis": {"state": "IN_TRIAGE"},
                }
            ]
        raise AssertionError(path)

    monkeypatch.setattr(_dt, "_request", fake_request)
    monkeypatch.setattr(_dt.time, "sleep", lambda s: None)
    (rec,) = _dt.scan_packages("proj", [("django", "3.2")], poll_tries=3)
    assert (rec.scanner, rec.cve_id, rec.package) == ("dependency-track", "CVE-2024-1", "django")
    assert any(c[0] == "PUT" for c in calls)


# ---------------------------------------------------------------------------
# G8: scanner runner failure reasons degrade to None
# ---------------------------------------------------------------------------


def test_run_json_failure_reasons_degrade(monkeypatch):
    import subprocess as _sp

    import modules.intel.scanner_binaries as _sb

    monkeypatch.setattr(_sb, "_cached_which", lambda b: "/bin/true")

    class _Proc:
        def __init__(self, out):
            self.stdout = out

    monkeypatch.setattr(_sb.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(_sp.TimeoutExpired("x", 1)))
    assert _sb._run_json("trivy", ["x"], timeout=1) is None
    assert _sb._run_json.last_reason == "timeout"

    monkeypatch.setattr(_sb.subprocess, "run", lambda *a, **k: _Proc(b""))
    assert _sb._run_json("trivy", ["x"]) is None
    assert _sb._run_json.last_reason == "empty_output"

    monkeypatch.setattr(_sb.subprocess, "run", lambda *a, **k: _Proc(b"{not json"))
    assert _sb._run_json("trivy", ["x"]) is None
    assert _sb._run_json.last_reason == "bad_json"

    monkeypatch.setattr(_sb, "STDOUT_CAP_BYTES", 4)
    monkeypatch.setattr(_sb.subprocess, "run", lambda *a, **k: _Proc(b"12345"))
    assert _sb._run_json("trivy", ["x"]) is None
    assert _sb._run_json.last_reason == "oversize"
