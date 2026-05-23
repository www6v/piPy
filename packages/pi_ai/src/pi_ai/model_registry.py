"""Model registry: built-in + models.json (pi: model-registry.ts)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from pi_ai.builtin_models import BUILTIN_PROVIDERS, builtin_models
from pi_ai.config_paths import get_models_path
from pi_ai.env_keys import get_env_api_key
from pi_ai.models_json import (
    ModelsJsonLoadResult,
    ProviderRequestConfig,
    _apply_model_override,
    load_models_json,
)
from pi_ai.resolve_config import resolve_config_value, resolve_config_value_or_raise
from pi_ai.types import Model


class ModelRegistry:
    def __init__(self, models_json_path: str | Path | None = None) -> None:
        self._models_json_path = (
            Path(models_json_path) if models_json_path is not None else get_models_path()
        )
        self._load_error: str | None = None
        self._models: list[Model] = []
        self._provider_configs: dict[str, ProviderRequestConfig] = {}
        self._model_headers: dict[str, dict[str, str]] = {}
        self._reload()

    @property
    def load_error(self) -> str | None:
        return self._load_error

    @property
    def models_json_path(self) -> Path:
        return self._models_json_path

    def refresh(self) -> None:
        self._reload()

    def get_all(self) -> list[Model]:
        return list(self._models)

    def find(self, provider: str, model_id: str) -> Model | None:
        for model in self._models:
            if model.provider == provider and model.id == model_id:
                return model
        return None

    def resolve_api_key(self, model: Model, *, override: str | None = None) -> str | None:
        if override:
            return override
        env_key = get_env_api_key(model.provider)
        if env_key:
            return env_key
        provider_config = self._provider_configs.get(model.provider)
        if provider_config and provider_config.api_key:
            try:
                return resolve_config_value_or_raise(
                    provider_config.api_key,
                    f'API key for provider "{model.provider}"',
                )
            except ValueError:
                return None
        return None

    def resolve_request_headers(self, model: Model) -> dict[str, str] | None:
        headers: dict[str, str] = {}
        provider_config = self._provider_configs.get(model.provider)
        if provider_config and provider_config.headers:
            for key, value in provider_config.headers.items():
                resolved = resolve_config_value(str(value))
                if resolved is not None:
                    headers[key] = resolved
        model_key = f"{model.provider}:{model.id}"
        for key, value in self._model_headers.get(model_key, {}).items():
            resolved = resolve_config_value(str(value))
            if resolved is not None:
                headers[key] = resolved
        if model.headers:
            headers.update(model.headers)
        return headers or None

    def resolve_auth(
        self,
        model: Model,
        *,
        api_key_override: str | None = None,
    ) -> tuple[str | None, dict[str, str] | None]:
        api_key = self.resolve_api_key(model, override=api_key_override)
        headers = self.resolve_request_headers(model)
        provider_config = self._provider_configs.get(model.provider)
        if provider_config and provider_config.auth_header and api_key:
            auth_headers = {"Authorization": f"Bearer {api_key}"}
            headers = {**headers, **auth_headers} if headers else auth_headers
            api_key = None
        return api_key, headers

    def _reload(self) -> None:
        loaded = load_models_json(str(self._models_json_path))
        self._load_error = loaded.error
        self._provider_configs = loaded.provider_configs
        self._model_headers = loaded.model_headers

        built_in = self._apply_builtin_overrides(
            builtin_models(),
            loaded,
        )
        self._models = self._merge_custom_models(built_in, loaded.custom_models)

    def _apply_builtin_overrides(
        self,
        models: list[Model],
        loaded: ModelsJsonLoadResult,
    ) -> list[Model]:
        result: list[Model] = []
        for model in models:
            updated = model
            provider_override = loaded.provider_overrides.get(model.provider)
            if provider_override:
                if provider_override.base_url:
                    updated = replace(updated, base_url=provider_override.base_url)
                if provider_override.thinking_format:
                    updated = replace(
                        updated,
                        thinking_format=provider_override.thinking_format,
                    )
            per_provider = loaded.model_overrides.get(model.provider, {})
            override = per_provider.get(model.id)
            if override:
                updated = _apply_model_override(updated, override)
            result.append(updated)
        return result

    def _merge_custom_models(
        self,
        built_in: list[Model],
        custom: list[Model],
    ) -> list[Model]:
        merged = list(built_in)
        for custom_model in custom:
            index = next(
                (
                    i
                    for i, model in enumerate(merged)
                    if model.provider == custom_model.provider
                    and model.id == custom_model.id
                ),
                -1,
            )
            if index >= 0:
                merged[index] = custom_model
            else:
                merged.append(custom_model)
        return merged


_default_registry: ModelRegistry | None = None


def get_registry(
    models_json_path: str | Path | None = None,
    *,
    refresh: bool = False,
) -> ModelRegistry:
    global _default_registry
    if _default_registry is None or models_json_path is not None:
        _default_registry = ModelRegistry(models_json_path)
        return _default_registry
    if refresh:
        _default_registry.refresh()
    return _default_registry
