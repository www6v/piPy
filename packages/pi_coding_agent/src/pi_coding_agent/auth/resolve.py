"""Resolve API auth: CLI override > auth.json > env > models.json."""

from __future__ import annotations

from pi_ai.model_registry import ModelRegistry
from pi_ai.types import Model

from pi_coding_agent.auth.storage import AuthStorage, get_auth_storage


def resolve_auth_for_model(
    registry: ModelRegistry,
    model: Model,
    *,
    api_key_override: str | None = None,
    auth: AuthStorage | None = None,
) -> tuple[str | None, dict[str, str] | None]:
    if api_key_override:
        return registry.resolve_auth(model, api_key_override=api_key_override)
    storage = auth or get_auth_storage()
    stored = storage.get_api_key(model.provider)
    if stored:
        # Apply models.json authHeader (Bearer) and headers like env-based keys.
        return registry.resolve_auth(model, api_key_override=stored)
    return registry.resolve_auth(model)
