# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first R2 gap tests: compress dedup/prune/budget + scan-parse norm + canned scanner parsers.

LAW 9 RED-first: written from a reading of the code, BEFORE running.
First run must FAIL for a functional reason. Wrong expectations in THIS
file are fixed here, never in library/. A REAL library bug stops the run
as [FT]. Parsers ONLY: no scanner subprocesses, no network; every payload
below is CANNED, mirroring tests/test_scanners.py fixture shapes.

Uncovered branches pinned here (baseline via scripts/dev/verify_cov.py
over test_compression + test_scanners + test_sms_leaves):
- sms_compress 86.7%: blank-line filler drop (89), corrupt dict load
  (162), dict eviction (172-173), fold_marker (176-177), chmod-fail
  pass (186), save-fail pass (188), dict fold on repeat (230),
  all-filler fallback (238), fast-path record (248), head-skip
  budget branch (274-275).
- sms_scan_parse 91.8%: vendor-map non-dict (57), any-vendor
  fallback (64), cvss_best non-dict skip (72), bad-score skip (80).
- scanner_binaries parser subset: trivy list-payload + junk row/vuln
  skips (200/204/207), grype junk-match skip (232), osv junk
  result/pkg/vuln skips (263/266/270), depcheck junk dep/vuln
  skips (300/304). Runner lines (_run_json reasons, run_*,
  run_dependency_check body) are OUT of scope: never run subprocesses.
"""

import os

import modules.intel.scanner_binaries as sb
import modules.shared.sms_compress as comp
import modules.shared.sms_scan_parse as scan

# --- sms_compress: blank lines are filler ------------------------------------


def test_r2_blank_line_drops_from_output():
    report = comp.compress_context("const a = 1;\n\nconst b = 2;\n", filename="a.js")
    assert "\n\n" not in report.compressed_text
    assert "const a = 1;" in report.compressed_text
    assert "const b = 2;" in report.compressed_text


# --- sms_compress: DictionaryStore load/record/evict/marker/save -------------


def test_r2_dictionary_corrupt_file_loads_empty(tmp_path):
    path = tmp_path / "d.json"
    path.write_text("### not json ###", encoding="utf-8")
    assert not comp.DictionaryStore(path=path).known("anything")


def test_r2_dictionary_evicts_oldest_past_cap(monkeypatch, tmp_path):
    monkeypatch.setattr(comp, "DICTIONARY_MAX_LINES", 3)
    store = comp.DictionaryStore(path=tmp_path / "d.json")
    store.record(filename="a.py", seen_lines=["l0", "l1", "l2", "l3", "l4"])
    assert set(store._lines) == {"l2", "l3", "l4"}


def test_r2_fold_marker_shows_count_and_truncates():
    store = comp.DictionaryStore(path="/nonexistent-r2/marker.json")
    store.record(filename="a.py", seen_lines=["k"])
    assert store.fold_marker("k") == "[... seen 1x in prior cycles: k ...]"
    assert store.fold_marker("never-seen") == "[... seen 0x in prior cycles: never-seen ...]"
    long_line = "z" * 80
    assert store.fold_marker(long_line).endswith("...]") and "z" * 60 in store.fold_marker(
        long_line
    )
    assert "z" * 61 not in store.fold_marker(long_line)


def test_r2_dictionary_save_survives_chmod_failure(monkeypatch, tmp_path):
    path = tmp_path / "d.json"
    store = comp.DictionaryStore(path=path)
    store.record(filename="a.py", seen_lines=["kept"])
    monkeypatch.setattr(os, "chmod", lambda *a, **k: (_ for _ in ()).throw(OSError("ro")))
    store.save()
    assert comp.DictionaryStore(path=path).known("kept")


def test_r2_dictionary_save_failure_never_raises(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("file, not dir", encoding="utf-8")
    store = comp.DictionaryStore(path=blocker / "d.json")
    store.record(filename="a.py", seen_lines=["x"])
    store.save()
    assert not (blocker / "d.json").exists()


# --- sms_compress: dedup fold / prune fallback / fast-path record -------------


def test_r2_known_repeat_folds_to_marker_unknown_repeat_drops(tmp_path):
    store = comp.DictionaryStore(path=tmp_path / "d.json")
    store.record(filename="a.js", seen_lines=["const a = 1;"])
    src = "const a = 1;\nconst a = 1;\nconst b = 2;\nconst b = 2;\nconst c = 3;\n"
    report = comp.compress_context(src, filename="a.js", dictionary=store)
    assert "[... seen 1x in prior cycles: const a = 1; ...]" in report.compressed_text
    assert report.compressed_text.count("const b = 2;") == 1
    assert "const c = 3;" in report.compressed_text


def test_r2_all_filler_source_keeps_first_line():
    report = comp.compress_context("// filler line one\n// filler line two\n", filename="a.js")
    assert report.compressed_text == "// filler line one\n"
    assert report.tokens_saved > 0


def test_r2_fast_path_records_dictionary(tmp_path):
    store = comp.DictionaryStore(path=tmp_path / "d.json")
    report = comp.compress_context(
        "const a = 1;\nconst b = 2;\n", filename="a.js", dictionary=store
    )
    assert report.tokens_saved >= 0
    assert store.known("const a = 1;") and store.known("const b = 2;")


# --- sms_compress: budget head-skip ------------------------------------------


def test_r2_budget_head_skip_keeps_critical_drops_filler():
    critical = "const queryExpression = eval(rawUserId);"
    filler = "".join(f"const filler_{i:04d} = {i};\n" for i in range(300))
    report = comp.compress_context(filler + critical + "\n", filename="a.js", max_tokens=12)
    assert report.compressed_tokens <= 12
    assert critical in report.compressed_text
    assert "filler_" not in report.compressed_text


# --- sms_scan_parse: vendor-map guards + fallback -----------------------------


def test_r2_vendor_map_rejects_non_dict():
    assert scan.cvss_from_vendor_map(None) == ""
    assert scan.cvss_from_vendor_map([("nvd", {"V3Score": 9.8})]) == ""
    assert scan.cvss_from_vendor_map("nvd") == ""


def test_r2_vendor_map_prefers_nvd_then_falls_back():
    assert scan.cvss_from_vendor_map({"redhat": {"V3Score": 7.0}, "nvd": {"V3Score": 9.0}}) == "9.0"
    assert scan.cvss_from_vendor_map({"other": {"V3Score": 8.0}}) == "8.0"
    assert scan.cvss_from_vendor_map({"nvd": "junk", "other": {"V3Score": 8.0}}) == "8.0"
    assert scan.cvss_from_vendor_map({"nvd": {"V2Score": None}, "other": {"V3Score": 8.0}}) == "8.0"


def test_r2_vendor_map_prefers_listed_vendor_order():
    assert (
        scan.cvss_from_vendor_map({"ghsa": {"V3Score": 5.0}, "redhat": {"V3Score": 7.0}}) == "7.0"
    )
    assert scan.cvss_from_vendor_map({"ghsa": {"V3Score": 5.0}}) == "5.0"


def test_r2_cvss_best_skips_non_dict_and_bad_scores():
    assert scan.cvss_best([None, "junk", 42, {"metrics": {"baseScore": 4.5}}]) == "4.5"
    assert scan.cvss_best(None) == ""
    assert scan.cvss_best([]) == ""
    assert scan.cvss_best([{"metrics": None}, {"metrics": {"baseScore": 6.0}}]) == "6.0"
    assert (
        scan.cvss_best([{"metrics": {"baseScore": 6.0}}, {"metrics": {"baseScore": "high"}}])
        == "6.0"
    )


# --- scanner parsers on canned payloads (no subprocesses) ----------------------


def test_r2_trivy_list_payload_and_junk_rows_skipped():
    assert sb.parse_trivy_report([]) == []
    assert sb.parse_trivy_report([{"Results": []}]) == []
    payload = {"Results": ["junk", 42, {"Vulnerabilities": ["junk", 7, {}]}]}
    (rec,) = sb.parse_trivy_report(payload)
    assert (rec.scanner, rec.cve_id, rec.package) == ("trivy", "", "")
    assert rec.cvss == "" and rec.cwe == () and rec.references == ()


def test_r2_trivy_normalizes_ids_and_truncates_fields():
    payload = {
        "Results": [
            {
                "Target": "package-lock.json",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "  cve-2024-0001  ",
                        "PkgName": "p" * 200,
                        "InstalledVersion": "1.0",
                        "FixedVersion": "2.0",
                        "Severity": "HIGH" + "x" * 20,
                        "Title": "t" * 300,
                        "Description": "desc",
                        "CVSS": {"redhat": {"V3Score": 7.0}, "nvd": {"V3Score": 9.0}},
                        "CweIDs": ["CWE-78"],
                        "References": ["https://example.invalid/norm"],
                    }
                ],
            }
        ]
    }
    (rec,) = sb.parse_trivy_report(payload)
    assert rec.cve_id == "CVE-2024-0001"
    assert len(rec.package) == 128 and len(rec.severity) == 16 and len(rec.title) == 256
    assert rec.cvss == "9.0"


def test_r2_grype_none_matches_degrades_to_empty():
    assert sb.parse_grype_report({"matches": None}) == []
    assert sb.parse_grype_report({}) == []


def test_r2_grype_skips_junk_matches_and_empty_fix():
    payload = {
        "matches": [
            "junk",
            42,
            {
                "vulnerability": {"id": "CVE-2024-2", "severity": "High", "description": "d"},
                "artifact": {"name": "lib", "version": "1.0"},
            },
        ]
    }
    (rec,) = sb.parse_grype_report(payload)
    assert (rec.scanner, rec.cve_id, rec.fixed_version) == ("grype", "CVE-2024-2", "")


def test_r2_grype_best_cvss_and_url_cap():
    payload = {
        "matches": [
            {
                "vulnerability": {
                    "id": "CVE-2024-3",
                    "severity": "Critical",
                    "description": "d",
                    "fix": {"versions": ["9.9"]},
                    "cvss": [
                        {"version": "3.1", "metrics": {"baseScore": 7.5}},
                        {"version": "3.1", "metrics": {"baseScore": 9.0}},
                    ],
                    "urls": [{"url": f"https://example.invalid/{i}"} for i in range(7)]
                    + [{"no_url": True}],
                },
                "artifact": {"name": "pkg", "version": "1.0"},
            }
        ]
    }
    (rec,) = sb.parse_grype_report(payload)
    assert rec.cvss == "9.0" and rec.fixed_version == "9.9"
    assert len(rec.references) == 5
    assert rec.references[0] == "https://example.invalid/0"


def test_r2_osv_skips_junk_rows_and_falls_back_to_details():
    payload = {
        "results": [
            "junk",
            {
                "source": {"path": "req.txt", "type": "lockfile"},
                "packages": [
                    "junk",
                    {
                        "package": {"name": "django", "version": "3.2"},
                        "vulnerabilities": [
                            "junk",
                            {
                                "id": "GHSA-x",
                                "details": "fallback details",
                                "severity": [{"junk": 1}, {"score": "CVSS:3.1/AV:N"}],
                                "references": [{"url": "https://example.invalid/o"}, {"no_url": 1}],
                            },
                        ],
                    },
                ],
            },
        ]
    }
    (rec,) = sb.parse_osv_scanner_report(payload)
    assert (rec.scanner, rec.package, rec.severity) == ("osv-scanner", "django", "CVSS:3.1/AV:N")
    assert rec.summary == "fallback details"
    assert rec.references == ("https://example.invalid/o",)


def test_r2_depcheck_skips_junk_and_empty_cvss():
    payload = {
        "dependencies": [
            "junk",
            {
                "fileName": "spring-core-5.3.jar",
                "vulnerabilities": [
                    "junk",
                    {"name": "CVE-2022-1", "severity": "High", "description": "d"},
                ],
            },
        ]
    }
    (rec,) = sb.parse_depcheck_report(payload)
    assert (rec.scanner, rec.cve_id, rec.cvss) == ("dependency-check", "CVE-2022-1", "")
    assert rec.package == "spring-core-5.3.jar"
