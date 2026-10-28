# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""One inference transport, explicitly addressed to a configured Muse endpoint."""

import asyncio
import json
import re
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from config import PurpleBoxConfig, require_api_key
from pricing import CallUsage, usage_from_response
from prompts import (
    BLUE_RESEARCH_SYSTEM_PROMPT,
    BLUE_TEAM_SYSTEM_PROMPT,
    RED_RESEARCH_SYSTEM_PROMPT,
    RED_TEAM_SYSTEM_PROMPT,
)

# Alias for branding migration; both names refer to the same config type.
SecureMitigationSystemConfig = PurpleBoxConfig


class AgentError(RuntimeError):
    """An API or schema failure, with no credentials/provider body in the message."""


class RedTeamFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    vulnerability_class: str = Field(min_length=1, max_length=256)
    sink_location: str = Field(min_length=1, max_length=512)
    analysis_summary: str = Field(min_length=1, max_length=8192)
    verification_script_python: str = Field(min_length=1, max_length=65_536)


class BlueTeamPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    sanitization_strategy: str = Field(min_length=1, max_length=8192)
    diff_summary: str = Field(min_length=1, max_length=8192)
    patched_file_content: str = Field(min_length=1, max_length=65_536)


class RedResearchDigest(BaseModel):
    """Research-only output: grounded queries + patterns, never work product."""

    model_config = ConfigDict(extra="forbid", strict=True)
    queries: list[str] = Field(min_length=1, max_length=4)
    attack_patterns: list[str] = Field(default_factory=list, max_length=4)
    cwe_hints: list[str] = Field(default_factory=list, max_length=4)


class BlueResearchDigest(BaseModel):
    """Research-only output: grounded fix patterns, never a patch."""

    model_config = ConfigDict(extra="forbid", strict=True)
    queries: list[str] = Field(min_length=1, max_length=4)
    fix_patterns: list[str] = Field(default_factory=list, max_length=4)
    cwe_hints: list[str] = Field(default_factory=list, max_length=4)


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
    stripped = text.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?\s*```\s*", stripped, flags=re.DOTALL)
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
            timeout=config.api_timeout_seconds,
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
        self, model: str, system: str, payload: dict, schema: type[ResponseModel], role: str = ""
    ) -> ResponseModel:
        # Bounded retry for transient HTTP codes while recording every completed response.
        last_error: Exception | None = None
        for attempt in range(2):
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
                ) as response:
                    if response.status_code in (429, 502, 503, 504) and attempt == 0:
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
                        await asyncio.sleep(0.5)
                        continue
                    if response.status_code != 200:
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
                if choice.get("finish_reason") == "length":
                    raise AgentError(
                        "Muse ran out of output tokens before finishing (reasoning counts toward "
                        "the limit). Raise META_MUSE_MAX_TOKENS or lower META_MUSE_REASONING_EFFORT."
                    )
                if choice.get("finish_reason") not in (None, "stop"):
                    raise AgentError("Muse returned an incomplete response.")
                content = choice["message"]["content"]
                if not isinstance(content, str):
                    raise AgentError("Muse did not return text JSON.")
                # Strip fences and extract JSON before schema validation.
                cleaned = _extract_json_object(content)
                try:
                    return schema.model_validate_json(cleaned)
                except (ValidationError, ValueError) as exc:
                    # Usage already recorded above; re-raise as AgentError.
                    raise AgentError(
                        "Muse returned invalid JSON or an unexpected response schema."
                    ) from exc
            except httpx.HTTPError as exc:
                last_error = exc
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
        raise AgentError("Muse API returned a transient error after retry.")

    async def run_red_team_analysis(
        self, filename: str, source_code: str, contract: str = ""
    ) -> RedTeamFinding:
        return await self._request(
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

    async def run_blue_team_sanitizer(
        self,
        filename: str,
        source_code: str,
        finding: RedTeamFinding,
        verifier_output: str,
        contract: str = "",
    ) -> BlueTeamPatch:
        return await self._request(
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

    async def run_red_research(
        self, sink_description: str, intel_records: list[dict]
    ) -> RedResearchDigest:
        """Research-only: grounded attack patterns for one sink. No work product."""
        return await self._request(
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

    async def run_blue_research(
        self, sink_description: str, intel_records: list[dict]
    ) -> BlueResearchDigest:
        """Research-only: grounded fix patterns for one sink. Never a patch."""
        return await self._request(
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
