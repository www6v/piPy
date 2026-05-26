"""Built-in models (subset of pi models.generated.ts)."""

from __future__ import annotations

from pi_ai.types import Model, ModelCost

_ANTHROPIC_BASE = "https://api.anthropic.com"
_OPENAI_BASE = "https://api.openai.com/v1"
_GOOGLE_BASE = "https://generativelanguage.googleapis.com"
_AZURE_OPENAI_RESPONSES_BASE = "https://example.azure.com/openai/v1"
_AMAZON_BEDROCK_BASE = "https://bedrock-runtime.us-east-1.amazonaws.com"

BUILTIN_PROVIDERS: frozenset[str] = frozenset(
    {
        "openai",
        "anthropic",
        "google",
        "faux",
        "azure-openai-responses",
        "amazon-bedrock",
    }
)


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
        Model(
            id="gemini-2.0-flash",
            name="Gemini 2.0 Flash",
            api="google-generate-content",
            provider="google",
            base_url=_GOOGLE_BASE,
            context_window=1_000_000,
            max_tokens=8_192,
            cost=ModelCost(input=0.0, output=0.0),
        ),
        Model(
            id="gpt-4o-mini",
            name="Azure OpenAI GPT-4o Mini",
            api="azure-openai-responses",
            provider="azure-openai-responses",
            base_url=_AZURE_OPENAI_RESPONSES_BASE,
            context_window=128_000,
            max_tokens=16_384,
            cost=ModelCost(input=0.15, output=0.6),
        ),
        Model(
            id="anthropic.claude-3-5-sonnet-20240620-v1:0",
            name="Bedrock Claude 3.5 Sonnet",
            api="amazon-bedrock",
            provider="amazon-bedrock",
            base_url=_AMAZON_BEDROCK_BASE,
            reasoning=True,
            context_window=200_000,
            max_tokens=8_192,
            cost=ModelCost(input=0.0, output=0.0),
        ),
    ]
