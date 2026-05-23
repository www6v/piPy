"""Model lookup via registry (built-in + models.json)."""

from __future__ import annotations

from pi_ai.model_registry import get_registry
from pi_ai.providers import faux as faux_provider
from pi_ai.types import Model


def get_model(provider: str, model_id: str) -> Model:
    if provider == "faux":
        model = faux_provider.get_faux_model(model_id)
        if model is not None:
            return model
        raise ValueError(f"Unknown faux model: {model_id}")

    registry = get_registry()
    model = registry.find(provider, model_id)
    if model is not None:
        return model

    hint = ""
    if registry.load_error:
        hint = f" (models.json error: see registry.load_error)"
    elif provider not in {"openai", "anthropic"}:
        hint = (
            f' Add provider "{provider}" in {registry.models_json_path} '
            "(see pi docs/models.md)."
        )
    raise ValueError(f"Unknown model: {provider}/{model_id}{hint}")
