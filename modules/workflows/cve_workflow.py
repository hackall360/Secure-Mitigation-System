# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Deep CVE + static-signal scanning wired into project and file workflows."""

from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from modules.core.agents import MetaMuseClient
from modules.core.config import ConfigurationError, PurpleBoxConfig, load_config, require_api_key
from modules.intel.research import epss_score, kev_lookup
from modules.services.projects import ProjectSnapshot, ProjectSpec, snapshot_project
from modules.shared.sms_async import Emit, blocking, make_log
from modules.workflows.deep_scan import (
    extract_dependencies,
    fetch_osv_vuln,
    muse_deep_assessment,
    query_osv_batch,
    run_static_scan,
    summarize_osv_vuln,
)

# Fast-lane topping (SPEC 14.8 item 3): the day-zero queue is ordered by
# patchability, not severity. Intake is id-sorted before the detail cap so the
# capped set never depends on OSV result ordering, and each ranked summary
# carries an auditable KEV/EPSS tie-break evidence string.
FAST_LANE_MAX_INTAKE = 10

# SPEC 14.9 item 1 (Lane 5): EUVD stays out of the fast lane. Competitor
# playbooks assume EUVD API coverage, but EUVD is unreachable as a keyless
# JSON source (site 200, API returns SPA HTML 2026-10-29; no verified keyless
# JSON endpoint), so the fast lane excludes it and fails closed instead of
# hallucinating coverage. Named explicitly so the exclusion is asserted, not
# merely absent. Never blocks the scan: allowed sources pass through.
FAST_LANE_EXCLUDED_SOURCES = frozenset({"euvd"})


def assert_fast_lane_source_allowed(source: str) -> bool:
    """Fail closed if the fast lane ever consults an excluded source (EUVD).

    Raises AssertionError on excluded sources; returns True otherwise so
    allowed keyless sources (osv/kev/epss) never block the scan. Called at
    each fast-lane consultation site so a future EUVD wiring trips loudly.
    """
    name = str(source or "").strip().lower()
    if name in FAST_LANE_EXCLUDED_SOURCES:
        raise AssertionError(
            f"EUVD is excluded from the fast lane: no verified keyless JSON "
            f"endpoint (site 200, API returns SPA HTML 2026-10-29); "
            f"failing closed instead of hallucinating coverage (got {source!r})."
        )
    return True


# Queue freshness (SPEC 14.9 item 1): intel sources stamp their live dates
# (KEV dateAdded, EPSS score date); any source older than 1 day is dropped
# from queue_evidence (fail-closed absent, never blocks the scan). EUVD
# stays out of the fast lane: no keyless JSON endpoint verified 2026-10-29.
_SOURCE_FRESH_DAYS = 1


def _source_fresh(raw: object) -> bool:
    """True unless a stamped source date proves the signal older than 1 day.

    Accepts an ISO date or datetime prefix (YYYY-MM-DD...). A missing or
    unparseable date is NOT stale: the signal was fetched live during this
    scan (enrichment runs inline), so only a proven-old vintage drops it.
    Fail-closed applies to absent signals, which never reach here. Future
    dates count as fresh: they are newer than the cutoff, not older.
    """
    day = str(raw or "").strip()[:10]
    if not day:
        return True
    try:
        stamped = datetime.date.fromisoformat(day)
    except (TypeError, ValueError):
        return True
    today = datetime.datetime.now(datetime.timezone.utc).date()
    return (today - stamped).days <= _SOURCE_FRESH_DAYS


def _queue_evidence(summary: dict[str, Any]) -> str:
    """One-line auditable tie-break record for a fast-lane ranked summary.

    Pure function of the enriched summary: reach score, first fixed version,
    KEV listing, EPSS percentile. Absence is recorded explicitly so the queue
    order is auditable whether signals fired or not. Bounded, deterministic.
    Stale-dated (>1 day) KEV/EPSS signals read as absent while the
    enriched numeric fields stay untouched (ordering is fail-closed too).
    Undated signals stay: enrichment fetches them live inline.
    """
    try:
        reach_s = str(int(summary.get("reach_score") or 0))
    except (TypeError, ValueError):
        reach_s = "?"
    fixed = summary.get("fixed_versions") or []
    fix_s = str(fixed[0])[:40] if fixed else "none"
    kev_s = (
        "listed"
        if summary.get("kev_listed") is True and _source_fresh(summary.get("kev_date"))
        else "absent"
    )
    try:
        pct = float(summary.get("epss_percentile", ""))
        epss_s = (
            f"{pct:.2f}"
            if 0.0 <= pct <= 1.0 and _source_fresh(summary.get("epss_date"))
            else "absent"
        )
    except (TypeError, ValueError):
        epss_s = "absent"
    return f"reach:{reach_s} fix:{fix_s} kev:{kev_s} epss:{epss_s}"


def _fast_lane_rank(summary: dict[str, Any]) -> tuple:
    """SSVC-style actionability key: reachable + fixable first, then KEV/EPSS
    tie-breaks, id as the final deterministic tiebreak. Stale-dated (>1 day)
    KEV/EPSS signals rank as absent so ordering agrees with _queue_evidence."""
    kev = summary.get("kev_listed") is True and _source_fresh(summary.get("kev_date"))
    try:
        pct = float(summary.get("epss_percentile", ""))
    except (TypeError, ValueError):
        pct = -1.0
    if not 0.0 <= pct <= 1.0 or not _source_fresh(summary.get("epss_date")):
        pct = -1.0
    return (
        -int(summary.get("reach_score") or 0),
        not bool(summary.get("fixed_versions")),
        not kev,
        -pct,
        summary.get("id") or "",
    )


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


def _enrich_reach_signals(summary: dict[str, Any]) -> dict[str, Any]:
    """Attach KEV/EPSS likelihood signals to one OSV summary, fail-closed.

    Uses the summary's first CVE alias only: at most 1 KEV + 1 EPSS lookup
    per summary. Both lookups are keyless and never-raise, and each call is
    additionally wrapped in try/except so any failure leaves the summary
    fields unset (fail-closed: no KEV flag, no EPSS percentile). Mutates
    and returns `summary` for call-site convenience.
    """
    cves = summary.get("cves") or []
    first = next((c for c in cves if isinstance(c, str) and c), "")
    if not first:
        return summary
    assert_fast_lane_source_allowed("kev")
    try:
        kev = kev_lookup(first)
    except Exception:
        kev = None
    if kev is not None:
        try:
            if kev.extra.get("kev_listed"):
                summary["kev_listed"] = True
                if kev.extra.get("kev_date"):  # W5 item 1: freshness stamp
                    summary["kev_date"] = str(kev.extra["kev_date"])[:32]
        except Exception:
            pass
    assert_fast_lane_source_allowed("epss")
    try:
        epss = epss_score(first)
    except Exception:
        epss = None
    if epss is not None:
        try:
            pct = float(epss.extra.get("percentile", ""))
        except (TypeError, ValueError):
            pct = -1.0
        if 0.0 <= pct <= 1.0:
            summary["epss_percentile"] = pct
            if epss.extra.get("epss_date"):  # W5 item 1: freshness stamp
                summary["epss_date"] = str(epss.extra["epss_date"])[:32]
    return summary


async def execute_cve_scan(
    project: ProjectSpec | Mapping[str, str] | str,
    emit: Emit,
    *,
    config: PurpleBoxConfig | None = None,
    include_osv: bool = True,
    include_deep_assessment: bool = False,
    max_osv_details: int = 25,
    include_nvd: bool = False,
    fast_lane: bool = False,
) -> CveScanReport:
    """Run static signals + optional OSV CVE lookup + optional Muse deep triage.

    - `project` may be a ProjectSpec (entire repo), a {path: content} mapping (file/codebase),
      or a single file path string examined with its parent as context is NOT loaded (caller provides mapping).
    - OSV lookup requires network access to api.osv.dev; disable with include_osv=False for offline.
    - Muse deep assessment requires a key unless local inference; disabled by default.
    - `fast_lane` is an opt-in disclosure fast lane: it forces
      `include_deep_assessment=False` and `include_nvd=False`, caps
      `max_osv_details` to min(given, 10), sorts vulnerabilities by actionability
      tier (-reach_score, fix availability, id), and
      prefixes the message with "Fast lane: ". Same shape, never raises.
    """

    log = make_log(emit)

    if fast_lane:
        include_deep_assessment = False
        include_nvd = False
        max_osv_details = min(max_osv_details, FAST_LANE_MAX_INTAKE)

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
            assert_fast_lane_source_allowed("osv")
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
            intake = sorted(vuln_ids) if fast_lane else vuln_ids
            for vid in intake[:max_osv_details]:
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
            from modules.intel.intel_search import (
                nvd_lookup,
                osv_lookup_by_cve,
                summarize_nvd_record,
            )

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
                        affected = (record or {}).get("affected") or []
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
    for summary in summaries:
        try:
            _enrich_reach_signals(summary)
            from modules.workflows.deep_scan import reachability_score as _reachability_score

            score, reach_evidence = _reachability_score(summary, static_findings)
            summary["reach_score"] = score
            summary["reach_evidence"] = reach_evidence
        except Exception:
            summary["reach_score"] = 0
            summary["reach_evidence"] = ["scoring unavailable"]
    cve_count = len(summaries)
    if fast_lane:
        # Reachable + fixable first, KEV/EPSS tie-breaks, id final tiebreak.
        summaries.sort(key=_fast_lane_rank)
        for summary in summaries:
            summary["queue_evidence"] = _queue_evidence(summary)
    message = (
        f"Deep scan completed: {len(static_findings)} static signals, "
        f"{len(deps)} dependencies, {cve_count} CVE records."
    )
    if fast_lane:
        message = f"Fast lane: {message}"
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
