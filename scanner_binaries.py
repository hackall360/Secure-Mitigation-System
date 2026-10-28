# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Local binary scanner transports: Trivy, Grype, OSV-Scanner, Dependency-Check.

Each scanner gets a small stdlib-subprocess wrapper sharing one contract:

- `available()`: binary on PATH (or configured path) and executable.
- `run_scan(target, timeout)`: bounded subprocess run, JSON parsed, mapped to
  `ScannerRecord` list. Never raises on scan failure: absent binary, timeout,
  bad JSON, and nonzero exits degrade to an empty list.
- `parse_report(payload)`: pure mapping from the tool's documented JSON shape
  to `ScannerRecord`. Unit-tested against canned fixtures; no binary needed.

All five tools are opt-in and off by default (see config/CLI). They run on the
HOST against a materialized source directory, never inside the air-gapped
sandbox containers. Their records feed the research sidecar as additional
grounding, same untrusted-data rules as `research.py`: never instructions,
Docker evidence still decides.

Documented JSON shapes consumed here (tool versions drift; mapping is
defensive — missing keys yield empty strings, never KeyError):
- Trivy: {"Results": [{"Target": str, "Vulnerabilities": [{
    "VulnerabilityID", "PkgName", "InstalledVersion", "FixedVersion",
    "Severity", "Title", "Description", "CVSS": {vendor: {"V3Score": n}},
    "CweIDs": [...] }]}]}
- Grype: {"matches": [{"vulnerability": {"id", "severity", "description",
    "fix": {"versions": [...]}, "cvss": [{"version": "3.1",
    "metrics": {"baseScore": n}}]}, "artifact": {"name", "version"}}]}
- OSV-Scanner: {"results": [{"source": {"path", "type"},
    "packages": [{"package": {"name", "version", "ecosystem"},
    "vulnerabilities": [{"id", "summary", "severity": [{"score"}],
    "affected": [...]}]}]}]}
- Dependency-Check: {"dependencies": [{"fileName", "vulnerabilities": [{
    "name", "severity", "description", "cvssv3": {"baseScore"},
    "cwes": [...] }]}]}
Dependency-Track (a server, not a binary) lives in scanner_dtrack.py.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass

MAX_SCAN_BYTES = 8 * 1024 * 1024
DEFAULT_TIMEOUT = 300.0


@dataclass
class ScannerRecord:
    """One normalized scanner finding. Data only — never instructions."""

    scanner: str  # trivy | grype | osv-scanner | dependency-check | dependency-track
    cve_id: str = ""
    package: str = ""
    installed_version: str = ""
    fixed_version: str = ""
    severity: str = ""
    cvss: str = ""
    title: str = ""
    summary: str = ""  # truncated to 1500 chars at construction
    cwe: tuple[str, ...] = ()
    references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.summary = (self.summary or "")[:1500]
        self.cve_id = (self.cve_id or "").strip().upper()[:64]


def _run_json(
    binary: str, args: list[str], *, timeout: float = DEFAULT_TIMEOUT
) -> dict | list | None:
    """Run a scanner binary, return parsed JSON. None on any failure."""
    exe = shutil.which(binary)
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, *args],
            capture_output=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if not proc.stdout or len(proc.stdout) > MAX_SCAN_BYTES:
        return None
    try:
        return json.loads(proc.stdout.decode("utf-8", "replace"))
    except (ValueError, UnicodeDecodeError):
        return None


def available(binary: str) -> bool:
    """True when the scanner binary resolves on PATH."""
    return shutil.which(binary) is not None


def _cvss_from_trivy_cvss(cvss: dict) -> str:
    for vendor in ("nvd", "redhat", "ghsa"):
        entry = cvss.get(vendor) if isinstance(cvss, dict) else None
        if isinstance(entry, dict):
            for key in ("V3Score", "V40Score", "V2Score"):
                if entry.get(key) is not None:
                    return str(entry[key])
    if isinstance(cvss, dict):
        for entry in cvss.values():
            if isinstance(entry, dict):
                for key in ("V3Score", "V40Score", "V2Score"):
                    if entry.get(key) is not None:
                        return str(entry[key])
    return ""


def parse_trivy_report(payload: dict | list) -> list[ScannerRecord]:
    """Map Trivy JSON (`trivy fs -f json`) to ScannerRecords."""
    if isinstance(payload, dict):
        results = payload.get("Results") or []
    else:
        results = []
    out: list[ScannerRecord] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        for vuln in result.get("Vulnerabilities") or []:
            if not isinstance(vuln, dict):
                continue
            out.append(
                ScannerRecord(
                    scanner="trivy",
                    cve_id=str(vuln.get("VulnerabilityID", "")),
                    package=str(vuln.get("PkgName", ""))[:128],
                    installed_version=str(vuln.get("InstalledVersion", ""))[:64],
                    fixed_version=str(vuln.get("FixedVersion", ""))[:64],
                    severity=str(vuln.get("Severity", ""))[:16],
                    cvss=_cvss_from_trivy_cvss(vuln.get("CVSS") or {}),
                    title=str(vuln.get("Title", ""))[:256],
                    summary=str(vuln.get("Description", "")),
                    cwe=tuple(str(c)[:16] for c in (vuln.get("CweIDs") or [])[:8]),
                    references=tuple(
                        str(r)[:256]
                        for r in (vuln.get("References") or [])[:5]
                        if isinstance(r, str)
                    ),
                )
            )
    return out


def _cvss_from_grype_cvss(entries: list) -> str:
    best = ""
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        metrics = entry.get("metrics") or {}
        score = metrics.get("baseScore") if isinstance(metrics, dict) else None
        if score is not None and (not best or float(score or 0) > float(best or 0)):
            best = str(score)
    return best


def parse_grype_report(payload: dict | list) -> list[ScannerRecord]:
    """Map Grype JSON (`grype -o json`) to ScannerRecords."""
    matches = payload.get("matches") if isinstance(payload, dict) else None
    out: list[ScannerRecord] = []
    for match in matches or []:
        if not isinstance(match, dict):
            continue
        vuln = match.get("vulnerability") or {}
        artifact = match.get("artifact") or {}
        fix = vuln.get("fix") or {} if isinstance(vuln, dict) else {}
        fixes = fix.get("versions") or [] if isinstance(fix, dict) else []
        out.append(
            ScannerRecord(
                scanner="grype",
                cve_id=str(vuln.get("id", "")),
                package=str(artifact.get("name", ""))[:128],
                installed_version=str(artifact.get("version", ""))[:64],
                fixed_version=str(fixes[0] if fixes else "")[:64],
                severity=str(vuln.get("severity", ""))[:16],
                cvss=_cvss_from_grype_cvss(vuln.get("cvss") or []),
                summary=str(vuln.get("description", "")),
                references=tuple(
                    str(r.get("url", ""))[:256]
                    for r in (vuln.get("urls") or [])[:5]
                    if isinstance(r, dict) and r.get("url")
                ),
            )
        )
    return out


def parse_osv_scanner_report(payload: dict | list) -> list[ScannerRecord]:
    """Map OSV-Scanner JSON (`osv-scanner --format json`) to ScannerRecords."""
    results = payload.get("results") if isinstance(payload, dict) else None
    out: list[ScannerRecord] = []
    for result in results or []:
        if not isinstance(result, dict):
            continue
        for pkg in result.get("packages") or []:
            if not isinstance(pkg, dict):
                continue
            info = pkg.get("package") or {}
            for vuln in pkg.get("vulnerabilities") or []:
                if not isinstance(vuln, dict):
                    continue
                sev = ""
                for s in vuln.get("severity") or []:
                    if isinstance(s, dict) and s.get("score"):
                        sev = str(s["score"])
                        break
                out.append(
                    ScannerRecord(
                        scanner="osv-scanner",
                        cve_id=str(vuln.get("id", "")),
                        package=str(info.get("name", ""))[:128],
                        installed_version=str(info.get("version", ""))[:64],
                        severity=sev[:16],
                        summary=str(vuln.get("summary") or vuln.get("details") or ""),
                        references=tuple(
                            str(r.get("url", ""))[:256]
                            for r in (vuln.get("references") or [])[:5]
                            if isinstance(r, dict) and r.get("url")
                        ),
                    )
                )
    return out


def parse_depcheck_report(payload: dict | list) -> list[ScannerRecord]:
    """Map Dependency-Check JSON report to ScannerRecords."""
    deps = payload.get("dependencies") if isinstance(payload, dict) else None
    out: list[ScannerRecord] = []
    for dep in deps or []:
        if not isinstance(dep, dict):
            continue
        fname = str(dep.get("fileName", ""))[:128]
        for vuln in dep.get("vulnerabilities") or []:
            if not isinstance(vuln, dict):
                continue
            cvss3 = vuln.get("cvssv3") or {}
            score = cvss3.get("baseScore") if isinstance(cvss3, dict) else None
            cwes: list[str] = []
            for c in vuln.get("cwes") or []:
                if isinstance(c, dict) and c.get("name"):
                    cwes.append(str(c["name"])[:16])
                elif isinstance(c, str):
                    cwes.append(c[:16])
            out.append(
                ScannerRecord(
                    scanner="dependency-check",
                    cve_id=str(vuln.get("name", "")),
                    package=fname,
                    severity=str(vuln.get("severity", ""))[:16],
                    cvss=str(score) if score is not None else "",
                    summary=str(vuln.get("description", "")),
                    cwe=tuple(cwes[:8]),
                )
            )
    return out


def run_trivy(path: str, *, timeout: float = DEFAULT_TIMEOUT) -> list[ScannerRecord]:
    """`trivy fs` over a directory. None-safe: [] when unavailable/failing."""
    payload = _run_json(
        "trivy",
        [
            "fs",
            "--format",
            "json",
            "--quiet",
            "--scanners",
            "vuln",
            "--severity",
            "UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL",
            path,
        ],
        timeout=timeout,
    )
    return parse_trivy_report(payload) if isinstance(payload, dict) else []


def run_grype(path: str, *, timeout: float = DEFAULT_TIMEOUT) -> list[ScannerRecord]:
    """`grype dir:` over a directory. None-safe."""
    payload = _run_json("grype", [f"dir:{path}", "-o", "json", "-q"], timeout=timeout)
    return parse_grype_report(payload) if isinstance(payload, dict) else []


def run_osv_scanner(path: str, *, timeout: float = DEFAULT_TIMEOUT) -> list[ScannerRecord]:
    """`osv-scanner` over a directory. None-safe."""
    payload = _run_json("osv-scanner", ["--format", "json", "--recursive", path], timeout=timeout)
    return parse_osv_scanner_report(payload) if isinstance(payload, dict) else []


def run_dependency_check(
    path: str, *, output_dir: str = "/tmp/depcheck", timeout: float = 900.0
) -> list[ScannerRecord]:
    """Dependency-Check over a directory, parsing its JSON report. None-safe.

    Slow on first run (local H2 DB + NVD fetch); callers should use the long
    default timeout. Requires the `dependency-check.sh` launcher on PATH.
    """
    import tempfile
    from pathlib import Path

    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    report = outdir / "dependency-check-report.json"
    exe = shutil.which("dependency-check.sh") or shutil.which("dependency-check")
    if not exe:
        return []
    with tempfile.TemporaryFile() as null:
        try:
            subprocess.run(
                [exe, "--scan", path, "--format", "JSON", "--out", str(outdir), "--noupdate"],
                stdout=null,
                stderr=null,
                timeout=timeout,
            )
        except (subprocess.TimeoutExpired, OSError):
            return []
    if not report.is_file() or report.stat().st_size > MAX_SCAN_BYTES:
        return []
    try:
        payload = json.loads(report.read_text(encoding="utf-8", errors="replace"))
    except ValueError:
        return []
    return parse_depcheck_report(payload) if isinstance(payload, dict) else []
