# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""One inference transport, explicitly addressed to a configured Muse endpoint."""

import asyncio
import json
import random
import re
import time
from typing import Annotated, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from modules.core.config import PurpleBoxConfig, require_api_key
from modules.core.pricing import CallUsage, usage_from_response
from modules.core.prompts import (
    BLUE_RESEARCH_SYSTEM_PROMPT,
    BLUE_TEAM_SYSTEM_PROMPT,
    RED_CHAIN_SYSTEM_PROMPT,
    RED_DEEP_SWEEP_SYSTEM_PROMPT,
    RED_RESEARCH_SYSTEM_PROMPT,
    RED_TEAM_SYSTEM_PROMPT,
    RED_THREAT_ACTOR_SYSTEM_PROMPT,
)
from modules.shared.sms_budget import check_payload_budget
from modules.shared.sms_observability import get_aspect as _get_aspect
from modules.shared.sms_observability import log as _obs_log
from modules.shared.sms_observability import record_metric as _obs_metric
from modules.shared.sms_observability import trace as _obs_trace

_OBS_AGENTS = _get_aspect("core.agents")


# Alias for branding migration; both names refer to the same config type.
SecureMitigationSystemConfig = PurpleBoxConfig


class AgentError(RuntimeError):
    """An API or schema failure, with no credentials/provider body in the message."""


# Shared item constraints: strip padding, then reject blank/oversize entries.
# Scalar fields keep their own Field() bounds below; these aliases only make
# the list-item rules explicit so one blank entry cannot slip through.
QueryStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
PatternStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1024)]
CweStr = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=16, pattern=r"(?i)^CWE-\d{1,5}$"
    ),
]


class RedTeamFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    vulnerability_class: str = Field(min_length=1, max_length=256)
    sink_location: str = Field(min_length=1, max_length=512)
    analysis_summary: str = Field(min_length=1, max_length=8192)
    verification_script_python: str = Field(min_length=1, max_length=65_536)


class BlueTeamPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    sanitization_strategy: str = Field(min_length=1, max_length=8192)
    diff_summary: str = Field(min_length=1, max_length=8192)
    patched_file_content: str = Field(min_length=1, max_length=65_536)


class RedResearchDigest(BaseModel):
    """Research-only output: grounded queries + patterns, never work product."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    queries: list[QueryStr] = Field(min_length=1, max_length=4)
    attack_patterns: list[PatternStr] = Field(default_factory=list, max_length=4)
    cwe_hints: list[CweStr] = Field(default_factory=list, max_length=4)


class BlueResearchDigest(BaseModel):
    """Research-only output: grounded fix patterns, never a patch."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    queries: list[QueryStr] = Field(min_length=1, max_length=4)
    fix_patterns: list[PatternStr] = Field(default_factory=list, max_length=4)
    cwe_hints: list[CweStr] = Field(default_factory=list, max_length=4)


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


# Agent transport perf: schema cache + stream cap.
# model_json_schema() rebuilds the JSON-schema dict on every call; cache it
# per response-model class so repeated red/blue calls reuse one object.
# Streaming bodies are capped by one shared helper (single cap constant).
_SCHEMA_CACHE: dict[type, dict] = {}
STREAM_CAP_BYTES = 1_048_576


def _schema_for(model_cls: type[ResponseModel]) -> dict:
    """Cached JSON schema dict for a response-model class."""
    cached = _SCHEMA_CACHE.get(model_cls)
    if cached is None:
        cached = model_cls.model_json_schema()
        _SCHEMA_CACHE[model_cls] = cached
    return cached


def _extract_json_object(text: str) -> str:
    """Return the first balanced JSON object from text, single pass.

    - Strips wrapping Markdown fences ``` or ```json if present.
    - Otherwise extracts the first balanced {...} in one forward scan that
      respects string literals and escapes, so braces inside strings do not
      affect boundary detection. No re-scan, no trial parses here: the
      caller validates via schema parsing.
    """
    if "\x00" in text:
        raise ValueError("Response contains NUL bytes.")
    stripped = text.strip().lstrip("\ufeff").strip()
    if not stripped:
        raise ValueError("Response contains no JSON object.")
    fence_match = re.fullmatch(
        r"```\s*(?:json\b)?\s*(.*?)\s*```\s*", stripped, flags=re.DOTALL | re.IGNORECASE
    )
    if fence_match:
        stripped = fence_match.group(1).strip()
    in_string = False
    escape = False
    depth = 0
    start_idx = -1
    for idx, ch in enumerate(stripped):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start_idx = idx
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start_idx != -1:
                    return stripped[start_idx : idx + 1]
    return stripped


# Bounded transient-retry discipline for the Muse transport.
# Same model, same provider, no fallback (SPEC strict model lock): a
# transport blip (timeout/DNS/reset) or transient HTTP status climbs one
# ladder — immediate re-try, then ~10 s, then ~20 s — then fails closed.
# RETRY_MAX_ATTEMPTS bounds total tries (never loop forever); the first
# step keeps the old exponential base+jitter; steps 2+ use the fixed
# ladder below. A server Retry-After on 429 is honored but capped at
# RETRY_AFTER_MAX_SECONDS so one header cannot stall the scan.
TRANSIENT_STATUS_CODES = (429, 502, 503, 504)
RETRY_MAX_ATTEMPTS = 4
RETRY_BASE_SECONDS = 0.5
RETRY_JITTER_SECONDS = 0.5
RETRY_AFTER_MAX_SECONDS = 5.0
# Fixed waits (seconds) before attempts 3 and 4 for transport blips and
# retried transient statuses: fail fast first, then 10 s, then 20 s.
RETRY_LADDER_SECONDS = (10.0, 20.0)


def _retry_delay_seconds(failures: int, retry_after: float | None = None) -> float:
    """Backoff after `failures` consecutive failures (1-based: 1st failure, 2nd, ...).

    After the 1st failure: immediate re-try (exponential base + jitter,
    unchanged). After the 2nd: ~10 s + jitter. After the 3rd+: ~20 s +
    jitter. A 429 Retry-After is still honored but capped, and never
    below the ladder floor for its step — a `Retry-After: 0` must not
    collapse the 10 s / 20 s waits.
    """
    if retry_after is None and failures >= 2:
        ladder_pos = min(failures - 2, len(RETRY_LADDER_SECONDS) - 1)
        return RETRY_LADDER_SECONDS[ladder_pos] + random.uniform(0, RETRY_JITTER_SECONDS)
    delay = RETRY_BASE_SECONDS * (2 ** (failures - 1)) + random.uniform(0, RETRY_JITTER_SECONDS)
    if retry_after is not None:
        floor = (
            RETRY_LADDER_SECONDS[min(failures - 2, len(RETRY_LADDER_SECONDS) - 1)]
            if failures >= 2
            else 0.0
        )
        delay = max(
            min(max(retry_after, 0.0), RETRY_AFTER_MAX_SECONDS),
            floor,
        ) + random.uniform(0, RETRY_JITTER_SECONDS)
    return delay


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header (delta-seconds only); None when absent/invalid."""
    if not value:
        return None
    try:
        return max(float(value.strip()), 0.0)
    except (TypeError, ValueError):
        return None


def _obs_report_call(role: str, calls: list[CallUsage]) -> None:
    """Log one model-call milestone + numeric metrics (never prompt text)."""
    if not calls:
        _obs_log(_OBS_AGENTS, "call", "model call finished", role=role)
        return
    last = calls[-1]
    _obs_log(
        _OBS_AGENTS,
        "call",
        "model call finished",
        role=role,
        model=last.model,
    )
    _obs_metric(_OBS_AGENTS, "tokens_in", last.prompt_tokens, unit="tokens")
    _obs_metric(_OBS_AGENTS, "tokens_out", last.completion_tokens, unit="tokens")
    _obs_metric(_OBS_AGENTS, "seconds", round(last.seconds, 3), unit="seconds")
    if last.cost_usd is not None:
        _obs_metric(_OBS_AGENTS, "cost_usd", last.cost_usd, unit="usd")


def _httpx_timeout(timeout_s: float) -> httpx.Timeout | float:
    """Map the timeout knob to an httpx timeout.

    0 = no read timeout: connect/write/pool stay bounded (30 s), only the
    read wait is uncapped — "wait as long as the model needs" without
    parking the connect phase forever.
    """
    if timeout_s == 0:
        return httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
    return timeout_s


class MetaMuseClient:
    def __init__(
        self, config: PurpleBoxConfig, *, transport: httpx.AsyncBaseTransport | None = None
    ):
        require_api_key(config)
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.meta_base_url.rstrip("/") + "/",
            headers=(
                {"Authorization": f"Bearer {config.meta_api_key}"} if config.meta_api_key else {}
            ),
            timeout=_httpx_timeout(config.api_timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )
        # One entry per completed HTTP call, including calls whose JSON was rejected,
        # because the provider still bills them.
        self.usage: list[CallUsage] = []

    async def aclose(self) -> None:
        await self.client.aclose()

    def _body(self, model: str, system: str, payload: dict) -> dict:
        # Muse models reason before answering, and reasoning tokens count toward
        # max_tokens. A small budget truncates the JSON (finish_reason "length").
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload)},
            ],
            "max_tokens": self.config.max_output_tokens,
        }
        if self.config.reasoning_effort:
            body["reasoning_effort"] = self.config.reasoning_effort
        else:
            body["temperature"] = 0.1
        return body

    async def _request(
        self,
        model: str,
        system: str,
        payload: dict,
        schema: type[ResponseModel],
        role: str = "",
        max_payload_bytes: int = 256_000,
        timeout_s: float | None = None,
    ) -> ResponseModel:
        # Per-call timeout override (WS ?timeout_s=, 0 = no read timeout).
        # Falls back to config when unset; applied per attempt via the
        # stream options so a late override never leaks across calls.
        effective_timeout = self.config.api_timeout_seconds if timeout_s is None else timeout_s
        # Bounded retry for transient HTTP codes while recording every completed response.
        last_error: Exception | None = None
        throttled = False
        # F-217b: enforce the caller-supplied payload budget here too, so a
        # direct _request caller cannot bypass the demo_gen pre-check.
        check_payload_budget(payload, max_payload_bytes, "Model request")
        consecutive_failures = 0
        for attempt in range(RETRY_MAX_ATTEMPTS):
            started = time.monotonic()
            # Meta's Chat Completions endpoint constrains decoding through response_format,
            # not a schema embedded only in prompt text. Keep exactly one schema on wire.
            user_payload = dict(payload)
            user_payload.pop("response_schema", None)
            request_body = self._body(model, system, user_payload)
            request_body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": _schema_for(schema),
                },
            }

            async def _read_capped(resp) -> bytearray:
                """Drain a streaming body up to STREAM_CAP_BYTES."""
                bounded = bytearray()
                async for chunk in resp.aiter_bytes():
                    bounded.extend(chunk)
                    if len(bounded) > STREAM_CAP_BYTES:
                        del bounded[STREAM_CAP_BYTES:]
                        break
                return bounded

            try:
                async with self.client.stream(
                    "POST",
                    "chat/completions",
                    json=request_body,
                    timeout=_httpx_timeout(effective_timeout),
                ) as response:
                    if (
                        response.status_code in TRANSIENT_STATUS_CODES
                        and attempt < RETRY_MAX_ATTEMPTS - 1
                    ):
                        # Record usage if possible before retrying.
                        try:
                            body = await _read_capped(response)
                            try:
                                data = json.loads(body) if body else {}
                            except Exception:
                                data = {}
                            # Only record if body looks like a model response.
                            if isinstance(data, dict) and "usage" in data:
                                self.usage.append(
                                    usage_from_response(
                                        role, model, data, time.monotonic() - started
                                    )
                                )
                        except Exception:
                            pass
                        # Rate-limit graceful: jittered exponential backoff; a
                        # server Retry-After on 429 is honored but capped, so a
                        # hostile header cannot stall the scan. Loop bound above
                        # (attempt == 0) guarantees no infinite retry.
                        retry_after = (
                            _parse_retry_after(response.headers.get("retry-after"))
                            if response.status_code == 429
                            else None
                        )
                        if response.status_code == 429:
                            throttled = True
                        consecutive_failures += 1
                        await asyncio.sleep(_retry_delay_seconds(consecutive_failures, retry_after))
                        continue
                    if response.status_code != 200:
                        if response.status_code == 429 or throttled:
                            raise AgentError(
                                "Muse API rate limit reached (HTTP 429); the provider is "
                                "throttling requests. Wait a moment, then run the scan again."
                            )
                        raise AgentError(
                            f"Muse API returned HTTP {response.status_code}; check endpoint, model access, and key."
                        )
                    body = await _read_capped(response)
                    if len(body) >= STREAM_CAP_BYTES:
                        raise AgentError("Muse response exceeded the 1 MiB limit.")
                data = json.loads(body)
                self.usage.append(
                    usage_from_response(role, model, data, time.monotonic() - started)
                )
                choice = data["choices"][0]
                if not isinstance(choice, dict):
                    raise AgentError("Muse returned an incomplete response.")
                if choice.get("finish_reason") == "length":
                    raise AgentError(
                        "Muse ran out of output tokens before finishing (reasoning counts toward "
                        "the limit). Raise META_MUSE_MAX_TOKENS or lower META_MUSE_REASONING_EFFORT."
                    )
                if choice.get("finish_reason") not in (None, "stop"):
                    raise AgentError("Muse returned an incomplete response.")
                message = choice.get("message")
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, str):
                    raise AgentError("Muse did not return text JSON.")
                # Strip fences and extract JSON before schema validation.
                cleaned = _extract_json_object(content)
                try:
                    return schema.model_validate_json(cleaned)
                except (ValidationError, ValueError) as exc:
                    # Usage already recorded above; re-raise as AgentError.
                    # Env-gated debug: dump the raw content so recurring
                    # schema clusters (forge F14/F15) can be diagnosed.
                    try:
                        import os as _os
                        import tempfile as _tf

                        _dbg = _os.environ.get("PURPLEBOX_LOG_RAW_RESPONSES")
                        if _dbg:
                            if not _os.path.isdir(_dbg):
                                raise AgentError(
                                    "PURPLEBOX_LOG_RAW_RESPONSES points to a missing "
                                    "directory; no debug payload was written."
                                )
                            _fd, _dp = _tf.mkstemp(
                                prefix=f"schemadebug-{role}-",
                                suffix=".txt",
                                dir=_dbg if _os.path.isdir(_dbg) else None,
                            )
                            with _os.fdopen(_fd, "w") as _fh:
                                _fh.write(f"ROLE={role} MODEL={model}\n")
                                _fh.write(f"CLEANED_LEN={len(cleaned)}\n")
                                _fh.write("----- CLEANED -----\n")
                                _fh.write(cleaned[:8000])
                                _fh.write("\n----- RAW -----\n")
                                _fh.write(content[:8000])
                    except AgentError:
                        raise
                    except Exception:
                        pass
                    raise AgentError(
                        "Muse returned invalid JSON or an unexpected response schema."
                    ) from exc
            except httpx.HTTPError as exc:
                # Transport blip (timeout, DNS hiccup, reset): climb the same
                # ladder as transient statuses — immediate re-try, then 10 s,
                # then 20 s. SPEC strict model lock holds: the SAME model is
                # re-called through the SAME provider; no fallback provider
                # is contacted. The last attempt still raises below.
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    last_error = exc
                    consecutive_failures += 1
                    await asyncio.sleep(_retry_delay_seconds(consecutive_failures, None))
                    continue
                raise AgentError(
                    "Muse request failed or timed out; no fallback provider was contacted."
                ) from exc
            except AgentError:
                raise
            except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
                raise AgentError(
                    "Muse returned invalid JSON or an unexpected response schema."
                ) from exc
        # If loop exhausted via transient retry without success, raise last transient.
        if last_error is not None:
            raise AgentError(
                "Muse request failed or timed out; no fallback provider was contacted."
            ) from last_error
        if throttled:
            raise AgentError(
                "Muse API rate limit reached (HTTP 429); the provider is "
                "throttling requests. Wait a moment, then run the scan again."
            )
        raise AgentError("Muse API returned a transient error after retry.")

    async def run_red_team_analysis(
        self, filename: str, source_code: str, contract: str = ""
    ) -> RedTeamFinding:
        with _obs_trace(_OBS_AGENTS, "red"):
            _obs_log(_OBS_AGENTS, "call_start", "model call started", role="red")
            result = await self._request(
                self.config.red_team_model,
                RED_TEAM_SYSTEM_PROMPT,
                {
                    "filename": filename,
                    "source": source_code,
                    "fixture_contract": contract,
                },
                RedTeamFinding,
                role="red",
            )
            _obs_report_call("red", self.usage)
            return result

    async def run_red_team_pass_analysis(
        self, pass_id: str, filename: str, source_code: str, contract: str = ""
    ) -> RedTeamFinding:
        """Sweep red pass: standard reuses the P1 prompt, deep/threat-actor use theirs."""
        if pass_id == "deep":
            system = RED_DEEP_SWEEP_SYSTEM_PROMPT
        elif pass_id == "threat_actor":
            system = RED_THREAT_ACTOR_SYSTEM_PROMPT
        elif pass_id == "chain":
            system = RED_CHAIN_SYSTEM_PROMPT
        elif pass_id == "standard":
            system = RED_TEAM_SYSTEM_PROMPT
        else:
            raise AgentError(f"Unknown sweep pass: {pass_id}.")
        with _obs_trace(_OBS_AGENTS, "red-pass"):
            _obs_log(_OBS_AGENTS, "call_start", "model call started", role="red")
            result = await self._request(
                self.config.red_team_model,
                system,
                {
                    "filename": filename,
                    "source": source_code,
                    "fixture_contract": contract,
                    "sweep_pass": pass_id,
                },
                RedTeamFinding,
                role="red",
            )
            _obs_report_call("red", self.usage)
            return result

    async def run_blue_team_sanitizer(
        self,
        filename: str,
        source_code: str,
        finding: RedTeamFinding,
        verifier_output: str,
        contract: str = "",
    ) -> BlueTeamPatch:
        with _obs_trace(_OBS_AGENTS, "blue"):
            _obs_log(_OBS_AGENTS, "call_start", "model call started", role="blue")
            result = await self._request(
                self.config.blue_team_model,
                BLUE_TEAM_SYSTEM_PROMPT,
                {
                    "filename": filename,
                    "source": source_code,
                    "finding": finding.model_dump(),
                    "verification_evidence": verifier_output,
                    "fixture_contract": contract,
                },
                BlueTeamPatch,
                role="blue",
            )
            _obs_report_call("blue", self.usage)
            return result

    async def run_red_research(
        self, sink_description: str, intel_records: list[dict]
    ) -> RedResearchDigest:
        """Research-only: grounded attack patterns for one sink. No work product."""
        with _obs_trace(_OBS_AGENTS, "red-research"):
            _obs_log(_OBS_AGENTS, "call_start", "model call started", role="red-research")
            result = await self._request(
                self.config.red_team_model,
                RED_RESEARCH_SYSTEM_PROMPT,
                {
                    "sink_description": sink_description[:2000],
                    "intel_records": intel_records[:20],
                    "note": "Research only. Do not produce findings, patches, or scripts.",
                },
                RedResearchDigest,
                role="red-research",
            )
            _obs_report_call("red-research", self.usage)
            return result

    async def run_blue_research(
        self, sink_description: str, intel_records: list[dict]
    ) -> BlueResearchDigest:
        """Research-only: grounded fix patterns for one sink. Never a patch."""
        with _obs_trace(_OBS_AGENTS, "blue-research"):
            _obs_log(_OBS_AGENTS, "call_start", "model call started", role="blue-research")
            result = await self._request(
                self.config.blue_team_model,
                BLUE_RESEARCH_SYSTEM_PROMPT,
                {
                    "sink_description": sink_description[:2000],
                    "intel_records": intel_records[:20],
                    "note": "Research only. Do not produce patches or file content.",
                },
                BlueResearchDigest,
                role="blue-research",
            )
            _obs_report_call("blue-research", self.usage)
            return result
