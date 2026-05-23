"""Built-in models (subset of pi models.generated.ts)."""

from __future__ import annotations

from pi_ai.types import Model, ModelCost

_ANTHROPIC_BASE = "https://api.anthropic.com"
_OPENAI_BASE = "https://api.openai.com/v1"

BUILTIN_PROVIDERS: frozenset[str] = frozenset({"openai", "anthropic", "faux"})


def builtin_models() -> list[Model]:
    return [
        Model(
            id="gpt-4o-mini",
            name="GPT-4o Mini",
            api="openai-completions",
            provider="openai",
            base_url=_OPENAI_BASE,
            context_window=128_000,
            max_tokens=16_384,
            cost=ModelCost(input=0.15, output=0.6),
        ),
        Model(
            id="claude-sonnet-4-5",
            name="Claude Sonnet 4.5",
            api="anthropic-messages",
            provider="anthropic",
            base_url=_ANTHROPIC_BASE,
            reasoning=True,
            context_window=200_000,
            max_tokens=64_000,
            cost=ModelCost(input=3.0, output=15.0),
        ),
        Model(
            id="claude-haiku-4-5",
            name="Claude Haiku 4.5",
            api="anthropic-messages",
            provider="anthropic",
            base_url=_ANTHROPIC_BASE,
            context_window=200_000,
            max_tokens=64_000,
            cost=ModelCost(input=0.8, output=4.0),
        ),
    ]
