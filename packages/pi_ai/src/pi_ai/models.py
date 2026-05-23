"""Model registry for pi-ai."""

from __future__ import annotations

from pi_ai.providers import faux as faux_provider
from pi_ai.types import Model, ModelCost

_OPENAI_MODELS: dict[str, Model] = {
    "gpt-4o-mini": Model(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        api="openai-completions",
        provider="openai",
        base_url="https://api.openai.com/v1",
        context_window=128_000,
        max_tokens=16_384,
        cost=ModelCost(input=0.15, output=0.6),
    ),
}


def get_model(provider: str, model_id: str) -> Model:
    if provider == "faux":
        model = faux_provider.get_faux_model(model_id)
        if model is not None:
            return model
        raise ValueError(f"Unknown faux model: {model_id}")
    if provider == "openai":
        model = _OPENAI_MODELS.get(model_id)
        if model is not None:
            return model
        raise ValueError(f"Unknown openai model: {model_id}")
    raise ValueError(f"Unknown provider: {provider}")
