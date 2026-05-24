"""Model pattern resolution (pi: model-resolver.ts subset)."""

from __future__ import annotations

from dataclasses import dataclass

from pi_ai.model_registry import ModelRegistry
from pi_ai.models import get_model
from pi_ai.types import Model

THINKING_LEVELS = frozenset({"off", "minimal", "low", "medium", "high", "xhigh"})


@dataclass
class ResolvedModel:
    model: Model
    provider: str
    model_id: str
    thinking_level: str | None = None
    warning: str | None = None


def _try_match_model(pattern: str, models: list[Model]) -> Model | None:
    needle = pattern.strip().lower()
    if not needle:
        return None
    exact = [
        model
        for model in models
        if f"{model.provider}/{model.id}".lower() == needle
        or model.id.lower() == needle
    ]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return None
    partial = [
        model
        for model in models
        if needle in model.id.lower() or needle in model.name.lower()
    ]
    if not partial:
        return None
    partial.sort(key=lambda model: model.id, reverse=True)
    return partial[0]


def parse_model_pattern(
    pattern: str,
    registry: ModelRegistry,
) -> ResolvedModel | None:
    models = registry.get_all()
    warning: str | None = None

    def resolve(subpattern: str, level: str | None) -> ResolvedModel | None:
        matched = _try_match_model(subpattern, models)
        if matched is None:
            return None
        return ResolvedModel(
            model=matched,
            provider=matched.provider,
            model_id=matched.id,
            thinking_level=level,
            warning=warning,
        )

    direct = resolve(pattern, None)
    if direct is not None:
        return direct

    if ":" not in pattern:
        return None
    prefix, suffix = pattern.rsplit(":", 1)
    if suffix in THINKING_LEVELS:
        return resolve(prefix, suffix)
    warning = (
        f'Invalid thinking level "{suffix}" in "{pattern}"; '
        "using model without thinking suffix."
    )
    return resolve(pattern, None)


def resolve_model_reference(
    pattern: str,
    registry: ModelRegistry,
    *,
    provider_override: str | None = None,
) -> ResolvedModel:
    parsed = parse_model_pattern(pattern, registry)
    if parsed is not None:
        return parsed
    if "/" in pattern:
        provider, model_id = pattern.split("/", 1)
    else:
        provider = provider_override or "openai"
        model_id = pattern
    if provider_override is not None:
        provider = provider_override
    model = registry.find(provider, model_id)
    if model is None:
        model = get_model(provider, model_id)
    return ResolvedModel(
        model=model,
        provider=provider,
        model_id=model_id,
    )
