# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Token usage accounting and cost estimates for Muse calls.

Prices are USD per 1M tokens from https://dev.meta.ai/docs/pricing-rate-limits
(read 2026-10-28). Reasoning tokens are billed as output tokens and are already
included in completion_tokens (https://dev.meta.ai/docs/reasoning, read
2026-10-28: "Reasoning tokens are billed at the same rate as visible output
tokens"). Models without a known price report tokens only.
"""

from pydantic import BaseModel, Field

# model -> (cached input, input, output) per 1M tokens
PRICES_PER_MILLION: dict[str, tuple[float, float, float]] = {
    "muse-wonder-1.0": (0.20, 4.00, 20.00),
    "muse-spark-1.3": (0.15, 1.25, 4.25),
    "muse-spark-1.2": (0.15, 1.25, 4.25),
    "muse-spark-1.1": (0.15, 1.25, 4.25),
    "muse-spark-1.3-contributor": (0.002, 0.10, 0.20),
    "muse-spark-1.2-contributor": (0.002, 0.10, 0.20),
}


class CallUsage(BaseModel):
    role: str
    model: str
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    seconds: float = 0.0
    cost_usd: float | None = None


class ScanUsage(BaseModel):
    calls: list[CallUsage] = Field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return sum(c.prompt_tokens + c.completion_tokens for c in self.calls)

    @property
    def cost_usd(self) -> float | None:
        # Unknown if any call has no price, so a partial sum is never shown as the total.
        if not self.calls or any(c.cost_usd is None for c in self.calls):
            return None
        return round(sum(c.cost_usd for c in self.calls), 6)


def estimate_cost(model: str, prompt: int, cached: int, completion: int) -> float | None:
    price = PRICES_PER_MILLION.get(model)
    if price is None:
        return None
    cached_rate, input_rate, output_rate = price
    cached = min(max(cached, 0), max(prompt, 0))
    uncached = max(prompt, 0) - cached
    total = cached * cached_rate + uncached * input_rate + max(completion, 0) * output_rate
    return round(total / 1_000_000, 6)


def usage_from_response(role: str, model: str, body: dict, seconds: float) -> CallUsage:
    """Read the OpenAI-compatible usage block. Missing fields count as zero."""
    usage = body.get("usage") if isinstance(body, dict) else None
    usage = usage if isinstance(usage, dict) else {}

    def number(value) -> int:
        return value if isinstance(value, int) and value >= 0 else 0

    prompt = number(usage.get("prompt_tokens"))
    completion = number(usage.get("completion_tokens"))
    cached = number((usage.get("prompt_tokens_details") or {}).get("cached_tokens"))
    reasoning = number((usage.get("completion_tokens_details") or {}).get("reasoning_tokens"))
    return CallUsage(
        role=role,
        model=model,
        prompt_tokens=prompt,
        cached_tokens=cached,
        completion_tokens=completion,
        reasoning_tokens=reasoning,
        seconds=round(seconds, 2),
        cost_usd=estimate_cost(model, prompt, cached, completion),
    )
