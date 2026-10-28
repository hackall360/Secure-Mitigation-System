# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Deep CVE + static-signal scanning wired into project and file workflows."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agents import MetaMuseClient
from config import ConfigurationError, PurpleBoxConfig, load_config, require_api_key
from deep_scan import (
    extract_dependencies,
    fetch_osv_vuln,
    muse_deep_assessment,
    query_osv_batch,
    run_static_scan,
    summarize_osv_vuln,
)
from projects import ProjectSnapshot, ProjectSpec, snapshot_project
from workflow import blocking

Emit = Callable[[str, str], Awaitable[None]]


class CveScanReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    target: str
    status: str = "completed"
    message: str = "Deep scan completed."
    static_findings: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[dict[str, str]] = Field(default_factory=list)
    vulnerabilities: list[dict[str, Any]] = Field(default_factory=list)
    deep_assessment: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)
    cleanup_ok: bool = True

    @property
    def success(self) -> bool:
        return self.status == "completed"


def files_from_snapshot(snapshot: ProjectSnapshot) -> dict[str, str]:
    out: dict[str, str] = {}
    for path, content in snapshot.files.items():
        try:
            out[path] = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
    return out


async def execute_cve_scan(
    project: ProjectSpec | Mapping[str, str] | str,
    emit: Emit,
    *,
    config: PurpleBoxConfig | None = None,
    include_osv: bool = True,
    include_deep_assessment: bool = False,
    max_osv_details: int = 25,
    include_nvd: bool = False,
) -> CveScanReport:
    """Run static signals + optional OSV CVE lookup + optional Muse deep triage.

    - `project` may be a ProjectSpec (entire repo), a {path: content} mapping (file/codebase),
      or a single file path string examined with its parent as context is NOT loaded (caller provides mapping).
    - OSV lookup requires network access to api.osv.dev; disable with include_osv=False for offline.
    - Muse deep assessment requires a key unless local inference; disabled by default.
    """

    async def log(team: str, message: str) -> None:
        try:
            await emit(team, message)
        except Exception:
            pass

    settings = config or load_config()
    if isinstance(project, ProjectSpec):
        name = project.path.name
        await log("system", f"Deep scan: snapshotting {name} for static signals and manifests.")
        snapshot = await blocking(snapshot_project, project)
        files = files_from_snapshot(snapshot)
        contract = project.contract
    elif isinstance(project, Mapping):
        name = "codebase"
        files = {str(k): str(v) for k, v in project.items()}
        contract = ""
    else:
        # Single file path string: read-only, no snapshot.
        from pathlib import Path as _Path

        p = _Path(str(project))
        name = p.name
        try:
            files = {name: p.read_text(encoding="utf-8", errors="strict")[:2_000_000]}
        except Exception as exc:
            return CveScanReport(target=name, status="error", message=f"Cannot read file: {exc}")
        contract = ""

    await log("system", f"Deep scan: running static signals over {len(files)} text files.")
    static_findings = run_static_scan(files)
    await log("red", f"Deep scan: {len(static_findings)} static signals found for Muse triage.")
    deps = extract_dependencies(files)
    await log("system", f"Deep scan: {len(deps)} dependency versions inventoried.")

    osv_results: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    errors: list[str] = []
    if include_osv and deps:
        try:
            await log("system", "Deep scan: querying OSV.dev for known CVEs (no key required).")
            batch = await blocking(query_osv_batch, deps)
            results = batch.get("results") or []
            # Collect unique vuln IDs across all deps.
            vuln_ids: list[str] = []
            for dep, res in zip(deps, results, strict=False):
                vulns = (res or {}).get("vulns") or []
                entry: dict[str, Any] = {"dependency": dep, "vulns": vulns}
                osv_results.append(entry)
                for v in vulns:
                    vid = v.get("id") if isinstance(v, dict) else None
                    if vid and vid not in vuln_ids:
                        vuln_ids.append(vid)
            await log("system", f"Deep scan: {len(vuln_ids)} unique OSV records; fetching details.")
            for vid in vuln_ids[:max_osv_details]:
                try:
                    record = await blocking(fetch_osv_vuln, vid)
                    summaries.append(summarize_osv_vuln(record))
                except Exception as exc:
                    errors.append(f"OSV fetch {vid} failed: {type(exc).__name__}")
        except Exception as exc:
            errors.append(f"OSV query failed: {type(exc).__name__}: {str(exc)[:300]}")
            await log("system", f"Deep scan: OSV lookup unavailable ({type(exc).__name__}).")
    elif include_osv:
        await log("system", "Deep scan: no dependency manifests found; skipping OSV lookup.")

    deep_report_dict: dict[str, Any] | None = None
    if include_deep_assessment:
        try:
            require_api_key(settings)
        except ConfigurationError as exc:
            return CveScanReport(
                target=name,
                status="error",
                message=str(exc),
                static_findings=[f.__dict__ for f in static_findings],
                dependencies=deps,
                vulnerabilities=summaries,
                errors=errors,
            )
        await log("red", "Deep scan: Muse triaging static signals and CVE context.")
        muse = MetaMuseClient(settings)
        try:
            report = await muse_deep_assessment(
                muse,
                files=files,
                static_findings=static_findings,
                cve_context=summaries,
                contract=contract,
                project_name=name,
            )
            deep_report_dict = report.model_dump()
            await log("blue", f"Deep scan: Muse prioritized {len(report.prioritized_paths)} paths.")
        finally:
            try:
                await muse.aclose()
            except Exception:
                pass

    if include_nvd and summaries:
        try:
            from intel_search import nvd_lookup, osv_lookup_by_cve, summarize_nvd_record

            for summary in summaries[:10]:
                for cve_id in (summary.get("cves") or [])[:2]:
                    try:
                        payload = await blocking(nvd_lookup, cve_id)
                        vulns = (payload or {}).get("vulnerabilities") or []
                        if vulns:
                            summary["nvd"] = summarize_nvd_record(vulns[0])
                            break
                    except Exception as exc:
                        summary.setdefault("nvd_error", f"{type(exc).__name__}")
                        break
                # Keyless OSV second opinion: fix commits / ranges NVD often omits.
                for cve_id in (summary.get("cves") or [])[:2]:
                    try:
                        record = await blocking(osv_lookup_by_cve, cve_id)
                        affected = record.get("affected") or []
                        ranges = [
                            r.get("type")
                            for a in affected
                            for r in (a.get("ranges") or [])
                            if r.get("type")
                        ]
                        fixed = sorted(
                            {
                                e.get("fixed")
                                for a in affected
                                for e in (a.get("ranges") or [])
                                for e in (e.get("events") or [])
                                if e.get("fixed")
                            }
                        )
                        if ranges or fixed:
                            summary["osv_ranges"] = {
                                "types": sorted(set(ranges))[:4],
                                "fixed": fixed[:8],
                            }
                        break
                    except Exception:
                        break
            await log("system", "Deep scan: NVD enrichment complete.")
        except Exception as exc:
            errors.append(f"NVD enrichment failed: {type(exc).__name__}")
    cve_count = len(summaries)
    message = (
        f"Deep scan completed: {len(static_findings)} static signals, "
        f"{len(deps)} dependencies, {cve_count} CVE records."
    )
    if errors:
        message += f" {len(errors)} lookup warnings."
    await log("system", message)
    return CveScanReport(
        target=name,
        status="completed",
        message=message,
        static_findings=[f.__dict__ for f in static_findings],
        dependencies=deps,
        vulnerabilities=summaries,
        deep_assessment=deep_report_dict,
        errors=errors,
    )
