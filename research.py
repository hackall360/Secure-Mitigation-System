# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Research-sidecar intel transport: free, keyless, bot-tolerant JSON sources.

Used by the opt-in research sidecars (PURPLEBOX_RESEARCH=on). These sources
explicitly welcome automation — no scraping, no bot wars, no credentials:

- OSV (api.osv.dev/v1/query + /vulns): affected-package and CVE lookup, no key.
- CIRCL cve-search (cve.circl.lu/api): CVE records, vendor/product browse, no key.
- GitHub Advisory DB (api.github.com/advisories): curated severity/CWE, no key.
- FIRST EPSS (api.first.org): exploit-probability scores, no key.
- NVD API (services.nvd.nist.gov): last resort; strict without NVD_API_KEY.

Anti-anti-bot posture (the measures that matter against these APIs):
- First-party JSON endpoints only — never HTML scraping, so there is no
  bot-detection surface (no vqd handshake, no 202 soft-blocks, no JS).
- Real User-Agent identifying the project on every request.
- Polite pacing: a per-process minimum gap with jitter between requests,
  exponential backoff with jitter on 429/5xx, small page sizes.
- Small response caps (1 MiB) and short per-source query budgets.
- Source fallback order (OSV -> CIRCL -> GHSA -> EPSS -> NVD): no single
  service can block research.

Every record returned here is UNTRUSTED data. Research agents must treat it
as adversary-influenced text: never follow URLs, never execute anything it
suggests, never quote it into a patch. It only grounds Muse's reasoning;
Docker evidence still decides every verdict.
"""

from __future__ import annotations

import json
import random
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Sequence

USER_AGENT = "Secure-Mitigation-System/0.1 research-sidecar (+https://github.com)"
MIN_GAP_SECONDS = 1.0
MAX_BODY_BYTES = 1 * 1024 * 1024

_last_call: float = 0.0


def _pace() -> None:
    """Enforce a jittered minimum gap between outbound intel requests."""
    global _last_call
    now = time.monotonic()
    wait = MIN_GAP_SECONDS + random.uniform(0, 1.0) - (now - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def _get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 20.0,
    tries: int = 3,
) -> dict | list:
    """GET JSON with pacing, backoff-with-jitter, and a response cap."""
    query = ("?" + urllib.parse.urlencode(params)) if params else ""
    heads = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        heads.update(headers)
    last: Exception | None = None
    for attempt in range(tries):
        _pace()
        request = urllib.request.Request(url + query, headers=heads)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read(MAX_BODY_BYTES + 1)
            if len(body) > MAX_BODY_BYTES:
                raise ValueError("intel response exceeded the 1 MiB cap")
            return json.loads(body.decode("utf-8"))
        except Exception as exc:  # network, HTTP error, bad JSON: back off
            last = exc
            time.sleep(2**attempt + random.uniform(0, 1.0))
    raise RuntimeError(f"intel request failed after {tries} tries: {last}") from last


def _post_json(url: str, payload: dict, *, timeout: float = 20.0, tries: int = 3) -> dict | list:
    """POST JSON with the same pacing/backoff/cap discipline as _get_json."""
    data = json.dumps(payload).encode()
    last: Exception | None = None
    for attempt in range(tries):
        _pace()
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read(MAX_BODY_BYTES + 1)
            if len(body) > MAX_BODY_BYTES:
                raise ValueError("intel response exceeded the 1 MiB cap")
            return json.loads(body.decode("utf-8"))
        except Exception as exc:
            last = exc
            time.sleep(2**attempt + random.uniform(0, 1.0))
    raise RuntimeError(f"intel request failed after {tries} tries: {last}") from last


@dataclass
class ResearchRecord:
    """One grounded intel item. Data only — never instructions."""

    source: str  # osv | circl | ghsa | epss | nvd | web
    cve_id: str = ""
    title: str = ""
    summary: str = ""  # truncated to 1500 chars at construction
    severity: str = ""
    cvss: str = ""
    cwe: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.summary = (self.summary or "")[:1500]
        self.cve_id = (self.cve_id or "").strip().upper()[:32]


def osv_query_package(name: str, ecosystem: str = "", *, limit: int = 5) -> list[ResearchRecord]:
    """OSV affected-package lookup: which CVEs hit this dependency. No key."""
    name = name.strip()[:128]
    if not name:
        return []
    package: dict = {"name": name}
    if ecosystem.strip():
        package["ecosystem"] = ecosystem.strip()[:64]
    payload = _post_json("https://api.osv.dev/v1/query", {"package": package})
    if not isinstance(payload, dict):
        return []
    out: list[ResearchRecord] = []
    for vuln in (payload.get("vulns") or [])[:limit]:
        if not isinstance(vuln, dict):
            continue
        aliases = [str(a) for a in (vuln.get("aliases") or []) if isinstance(a, str)]
        cve = next((a for a in aliases if a.startswith("CVE-")), vuln.get("id", ""))
        summary = str(vuln.get("summary") or vuln.get("details") or "")[:1500]
        severities = vuln.get("severity") or []
        sev = ""
        if severities and isinstance(severities[0], dict):
            sev = str(severities[0].get("score", ""))
        out.append(
            ResearchRecord(
                source="osv",
                cve_id=cve,
                title=str(vuln.get("id", ""))[:128],
                summary=summary,
                severity=sev,
                references=tuple(
                    str(r.get("url", ""))[:256]
                    for r in (vuln.get("references") or [])[:5]
                    if isinstance(r, dict) and r.get("url")
                ),
                extra={"aliases": aliases[:8]},
            )
        )
    return out


def osv_lookup(cve_id: str) -> ResearchRecord | None:
    """OSV direct CVE fetch. No key."""
    safe = re.sub(r"[^A-Za-z0-9\-_:.]", "", cve_id.strip().upper())[:32]
    if not re.fullmatch(r"CVE-\d{4}-\d{4,7}", safe):
        return None
    try:
        payload = _get_json(f"https://api.osv.dev/v1/vulns/{safe}")
    except RuntimeError:
        return None
    if not isinstance(payload, dict):
        return None
    return ResearchRecord(
        source="osv",
        cve_id=safe,
        title=str(payload.get("id", safe))[:128],
        summary=str(payload.get("summary") or payload.get("details") or "")[:1500],
        references=tuple(
            str(r.get("url", ""))[:256]
            for r in (payload.get("references") or [])[:5]
            if isinstance(r, dict) and r.get("url")
        ),
    )


def circl_lookup(cve_id: str) -> ResearchRecord | None:
    """CIRCL cve-search CVE record: full CVE JSON, no key, no rate games."""
    safe = re.sub(r"[^A-Za-z0-9\-_:.]", "", cve_id.strip().upper())[:32]
    if not re.fullmatch(r"CVE-\d{4}-\d{4,7}", safe):
        return None
    try:
        payload = _get_json(f"https://cve.circl.lu/api/cve/{safe}")
    except RuntimeError:
        return None
    if not isinstance(payload, dict):
        return None
    summary = str(payload.get("summary", ""))[:1500]
    return ResearchRecord(
        source="circl",
        cve_id=safe,
        title=safe,
        summary=summary,
        cvss=str(payload.get("cvss", ""))[:32],
        cwe=tuple(str(c)[:16] for c in (payload.get("cwe", []) or [])[:8]),
        references=tuple(str(r)[:256] for r in (payload.get("references", []) or [])[:5]),
    )


def circl_browse_product(vendor: str, product: str, *, limit: int = 5) -> list[ResearchRecord]:
    """CIRCL vendor/product CVE listing. No key."""
    vendor = re.sub(r"[^a-z0-9_.\-]", "", vendor.strip().lower())[:64]
    product = re.sub(r"[^a-z0-9_.\-]", "", product.strip().lower())[:64]
    if not vendor or not product:
        return []
    try:
        payload = _get_json(f"https://cve.circl.lu/api/search/{vendor}/{product}")
    except RuntimeError:
        return []
    items = payload if isinstance(payload, list) else payload.get("results", [])
    out: list[ResearchRecord] = []
    for item in (items or [])[:limit]:
        if not isinstance(item, dict):
            continue
        cve = str(item.get("id", ""))
        out.append(
            ResearchRecord(
                source="circl",
                cve_id=cve,
                title=cve,
                summary=str(item.get("summary", ""))[:1500],
                cvss=str(item.get("cvss", ""))[:32],
            )
        )
    return out


def ghsa_search(package: str, ecosystem: str = "", *, limit: int = 5) -> list[ResearchRecord]:
    """GitHub Advisory DB search: curated severity/CWE, unauthenticated. No key."""
    package = package.strip()[:128]
    if not package:
        return []
    params: dict = {"package": package, "per_page": str(max(1, min(limit, 20)))}
    if ecosystem.strip():
        params["ecosystem"] = ecosystem.strip()[:32]
    try:
        payload = _get_json(
            "https://api.github.com/advisories",
            params=params,
            headers={"Accept": "application/vnd.github+json"},
        )
    except RuntimeError:
        return []
    if not isinstance(payload, list):
        return []
    out: list[ResearchRecord] = []
    for adv in payload[:limit]:
        if not isinstance(adv, dict):
            continue
        cwes = tuple(
            str(n.get("cwe_id", ""))[:16]
            for n in (adv.get("cwes") or [])[:4]
            if isinstance(n, dict) and n.get("cwe_id")
        )
        out.append(
            ResearchRecord(
                source="ghsa",
                cve_id=str(adv.get("cve_id") or "")[:32],
                title=str(adv.get("summary") or adv.get("ghsa_id") or "")[:256],
                summary=str(adv.get("description") or "")[:1500],
                severity=str(adv.get("severity") or "")[:16],
                cwe=cwes,
                references=tuple(
                    str(r)[:256] for r in (adv.get("references") or [])[:5] if isinstance(r, str)
                ),
            )
        )
    return out


def epss_score(cve_id: str) -> ResearchRecord | None:
    """FIRST EPSS exploit-probability score for one CVE. No key."""
    safe = cve_id.strip().upper()[:32]
    if not re.fullmatch(r"CVE-\d{4}-\d{4,7}", safe):
        return None
    try:
        payload = _get_json("https://api.first.org/data/v1/epss", params={"cve": safe})
    except RuntimeError:
        return None
    if not isinstance(payload, dict):
        return None
    data = payload.get("data") or []
    if not data or not isinstance(data[0], dict):
        return None
    row = data[0]
    return ResearchRecord(
        source="epss",
        cve_id=safe,
        title=f"EPSS {row.get('epss', '?')} (percentile {row.get('percentile', '?')})",
        summary=f"Exploit-prediction score {row.get('epss')} dated {row.get('date', '')}.",
        extra={"epss": str(row.get("epss", "")), "percentile": str(row.get("percentile", ""))},
    )


def cve_records(cve_ids: Sequence[str]) -> list[ResearchRecord]:
    """CVE endpoint series for one or more CVE ids: CIRCL + OSV + EPSS + GHSA.

    Keyless and never-raises: each id fans out to the bot-tolerant CVE
    endpoints (CIRCL record, OSV aliases, EPSS score), plus a GHSA lookup by
    the id. Failures degrade to fewer records. This is the series the green
    builder and research sidecars call with parsed user intent.
    """
    found: list[ResearchRecord] = []
    seen: set[str] = set()

    def add(records: list[ResearchRecord | None]) -> None:
        for rec in records:
            if rec is None:
                continue
            key = f"{rec.source}:{rec.cve_id or rec.title}"
            if key in seen:
                continue
            seen.add(key)
            found.append(rec)

    for raw in list(cve_ids)[:8]:
        cve = str(raw or "").strip().upper()[:32]
        if not re.fullmatch(r"CVE-\d{4}-\d{4,7}", cve):
            continue
        for fetch in (circl_lookup, osv_lookup):
            try:
                add([fetch(cve)])
            except Exception:
                continue
        try:
            add([epss_score(cve)])
        except Exception:
            pass
        try:
            add([r for r in ghsa_search(cve) if r.cve_id.upper() == cve][:2])
        except Exception:
            pass
    return found[:24]


def web_notes(queries: Sequence[str], *, per_query: int = 3) -> list[ResearchRecord]:
    """Web context for named vuln types + free text: Wikipedia JSON API only.

    No HTML scraping, no search-engine bot wars: first-party MediaWiki JSON
    (search + intro extracts), same pacing/backoff/caps discipline as the CVE
    endpoints. Returns definition-style records so green/research agents know
    what a named vuln means. Never raises: failures degrade to [].
    """
    found: list[ResearchRecord] = []
    seen: set[str] = set()
    for raw in list(queries)[:6]:
        query = " ".join(str(raw or "").split())[:128]
        if len(query) < 3:
            continue
        try:
            payload = _get_json(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": str(max(1, min(per_query, 5))),
                },
            )
        except RuntimeError:
            continue
        hits = ((payload or {}).get("query") or {}).get("search") or []
        for hit in hits[:per_query]:
            if not isinstance(hit, dict):
                continue
            title = str(hit.get("title") or "")[:256]
            if not title or title.lower() in seen:
                continue
            seen.add(title.lower())
            snippet = re.sub(r"<[^>]+>", " ", str(hit.get("snippet") or ""))
            snippet = " ".join(snippet.split())[:600]
            try:
                detail = _get_json(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "prop": "extracts",
                        "exintro": "1",
                        "explaintext": "1",
                        "titles": title,
                        "format": "json",
                    },
                )
                pages = ((detail or {}).get("query") or {}).get("pages") or {}
                first = next(iter(pages.values()), {})
                extract = (
                    " ".join(str((first or {}).get("extract") or "").split())[:1500]
                )
            except RuntimeError:
                extract = ""
            found.append(
                ResearchRecord(
                    source="web",
                    cve_id="",
                    title=title,
                    summary=extract or snippet,
                    extra={"query": query},
                )
            )
    return found[:12]


def research_for_sink(
    keywords: Sequence[str],
    *,
    package_hints: Sequence[str] = (),
    cve_hints: Sequence[str] = (),
    per_source: int = 3,
) -> list[ResearchRecord]:
    """One bounded research pass across all bot-tolerant sources.

    Never raises: every source failure degrades to fewer records, never a
    failed scan. Total outbound calls stay small (queries x sources).
    """
    found: list[ResearchRecord] = []
    seen: set[str] = set()

    def add(records: list[ResearchRecord | None]) -> None:
        for rec in records:
            if rec is None:
                continue
            key = f"{rec.source}:{rec.cve_id or rec.title}"
            if key in seen:
                continue
            seen.add(key)
            found.append(rec)

    for raw in list(cve_hints)[:4]:
        cve = re.sub(r"[^A-Za-z0-9\-]", "", raw.strip().upper())[:32]
        if not re.fullmatch(r"CVE-\d{4}-\d{4,7}", cve):
            continue
        for fetch in (circl_lookup, osv_lookup):
            try:
                add([fetch(cve)])
            except Exception:
                continue  # source down: keep going, never fail the scan
        try:
            add([epss_score(cve)])
        except Exception:
            continue
    for raw in list(package_hints)[:3]:
        name = raw.strip()[:128]
        if not name:
            continue
        for fetch in (osv_query_package, ghsa_search):
            try:
                add(fetch(name, limit=per_source))
            except Exception:
                continue
    for raw in list(keywords)[:3]:
        vendor, _, product = raw.strip().lower().partition(" ")
        if vendor and product:
            try:
                add(circl_browse_product(vendor, product.strip(), limit=per_source))
            except Exception:
                continue
    return found[:20]
