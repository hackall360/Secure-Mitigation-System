# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""One inference transport, explicitly addressed to a configured Muse endpoint."""

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from config import PurpleBoxConfig, require_api_key
from prompts import BLUE_TEAM_SYSTEM_PROMPT, RED_TEAM_SYSTEM_PROMPT


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


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class MetaMuseClient:
    def __init__(
        self, config: PurpleBoxConfig, *, transport: httpx.AsyncBaseTransport | None = None
    ):
        require_api_key(config)
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.meta_base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {config.meta_api_key}"},
            timeout=config.api_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

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
        return body

    async def _request(
        self, model: str, system: str, payload: dict, schema: type[ResponseModel]
    ) -> ResponseModel:
        try:
            async with self.client.stream(
                "POST",
                "chat/completions",
                json=self._body(model, system, payload),
            ) as response:
                if response.status_code != 200:
                    raise AgentError(
                        f"Muse API returned HTTP {response.status_code}; check endpoint, model access, and key."
                    )
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 1_048_576:
                        raise AgentError("Muse response exceeded the 1 MiB limit.")
            choice = json.loads(body)["choices"][0]
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
            return schema.model_validate_json(content)
        except httpx.HTTPError as exc:
            raise AgentError(
                "Muse request failed or timed out; no fallback provider was contacted."
            ) from exc
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise AgentError(
                "Muse returned invalid JSON or an unexpected response schema."
            ) from exc

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
        )
