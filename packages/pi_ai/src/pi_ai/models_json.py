"""Parse and validate ~/.pi/agent/models.json (pi: model-registry.ts)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from pi_ai.builtin_models import BUILTIN_PROVIDERS
from pi_ai.types import Model, ModelCost


@dataclass
class ProviderRequestConfig:
    api_key: str | None = None
    headers: dict[str, str] | None = None
    auth_header: bool = False


@dataclass
class ProviderOverride:
    base_url: str | None = None
    thinking_format: str | None = None


@dataclass
class ModelsJsonLoadResult:
    custom_models: list[Model] = field(default_factory=list)
    provider_overrides: dict[str, ProviderOverride] = field(
        default_factory=dict
    )
    model_overrides: dict[str, dict[str, dict[str, Any]]] = field(
        default_factory=dict
    )
    provider_configs: dict[str, ProviderRequestConfig] = field(
        default_factory=dict
    )
    model_headers: dict[str, dict[str, str]] = field(default_factory=dict)
    error: str | None = None


def strip_json_comments(text: str) -> str:
    """Strip // comments and trailing commas (pi model-registry stripJsonComments)."""
    text = re.sub(
        r'"(?:\\.|[^"\\])*"|//[^\n]*',
        lambda match: match.group(0) if match.group(0).startswith('"') else "",
        text,
    )
    return re.sub(
        r'"(?:\\.|[^"\\])*"|,(\s*[}\]])',
        lambda match: match.group(1) if match.group(1) else match.group(0),
        text,
    )


def _merge_thinking_format(
    provider_compat: dict[str, Any] | None,
    model_compat: dict[str, Any] | None,
) -> str | None:
    if model_compat and model_compat.get("thinkingFormat"):
        return str(model_compat["thinkingFormat"])
    if provider_compat and provider_compat.get("thinkingFormat"):
        return str(provider_compat["thinkingFormat"])
    return None


def _parse_cost(raw: dict[str, Any] | None) -> ModelCost:
    if not raw:
        return ModelCost()
    return ModelCost(
        input=float(raw.get("input", 0)),
        output=float(raw.get("output", 0)),
        cache_read=float(raw.get("cacheRead", 0)),
        cache_write=float(raw.get("cacheWrite", 0)),
    )


def _apply_model_override(model: Model, override: dict[str, Any]) -> Model:
    if override.get("name") is not None:
        model.name = str(override["name"])
    if override.get("reasoning") is not None:
        model.reasoning = bool(override["reasoning"])
    if override.get("contextWindow") is not None:
        model.context_window = int(override["contextWindow"])
    if override.get("maxTokens") is not None:
        model.max_tokens = int(override["maxTokens"])
    if override.get("input") is not None:
        model.input = list(override["input"])
    if override.get("cost"):
        cost = override["cost"]
        model.cost = ModelCost(
            input=float(cost.get("input", model.cost.input)),
            output=float(cost.get("output", model.cost.output)),
            cache_read=float(cost.get("cacheRead", model.cost.cache_read)),
            cache_write=float(cost.get("cacheWrite", model.cost.cache_write)),
        )
    compat = override.get("compat")
    if compat and compat.get("thinkingFormat"):
        model.thinking_format = str(compat["thinkingFormat"])
    headers = override.get("headers")
    if headers:
        model.headers = {**model.headers, **headers} if model.headers else dict(headers)
    return model


def validate_and_parse(config: dict[str, Any]) -> ModelsJsonLoadResult:
    providers = config.get("providers")
    if not isinstance(providers, dict):
        return ModelsJsonLoadResult(
            error='Invalid models.json: root must have "providers" object',
        )

    result = ModelsJsonLoadResult()
    builtin_defaults: dict[str, dict[str, str]] = {}

    for provider_name, provider_config in providers.items():
        if not isinstance(provider_config, dict):
            return ModelsJsonLoadResult(
                error=f"Provider {provider_name}: must be an object",
            )

        is_builtin = provider_name in BUILTIN_PROVIDERS
        models = provider_config.get("models") or []
        model_overrides = provider_config.get("modelOverrides") or {}
        has_models = isinstance(models, list) and len(models) > 0
        has_overrides = bool(model_overrides)

        if not has_models:
            if (
                not provider_config.get("baseUrl")
                and not provider_config.get("headers")
                and not provider_config.get("compat")
                and not has_overrides
            ):
                return ModelsJsonLoadResult(
                    error=(
                        f'Provider {provider_name}: must specify "baseUrl", '
                        '"headers", "compat", "modelOverrides", or "models".'
                    ),
                )
        elif not is_builtin:
            if not provider_config.get("baseUrl"):
                return ModelsJsonLoadResult(
                    error=(
                        f'Provider {provider_name}: "baseUrl" is required '
                        "when defining custom models."
                    ),
                )
            if not provider_config.get("apiKey"):
                return ModelsJsonLoadResult(
                    error=(
                        f'Provider {provider_name}: "apiKey" is required '
                        "when defining custom models."
                    ),
                )

        if provider_config.get("baseUrl") or provider_config.get("compat"):
            compat = provider_config.get("compat") or {}
            result.provider_overrides[provider_name] = ProviderOverride(
                base_url=provider_config.get("baseUrl"),
                thinking_format=_merge_thinking_format(compat, None),
            )

        api_key = provider_config.get("apiKey")
        headers = provider_config.get("headers")
        auth_header = bool(provider_config.get("authHeader"))
        if api_key or headers or auth_header:
            result.provider_configs[provider_name] = ProviderRequestConfig(
                api_key=str(api_key) if api_key else None,
                headers=dict(headers) if headers else None,
                auth_header=auth_header,
            )

        if has_overrides:
            result.model_overrides[provider_name] = dict(model_overrides)
            for model_id, override in model_overrides.items():
                if isinstance(override, dict) and override.get("headers"):
                    result.model_headers[f"{provider_name}:{model_id}"] = dict(
                        override["headers"]
                    )

        if not has_models:
            continue

        provider_api = provider_config.get("api")
        provider_base = provider_config.get("baseUrl")
        provider_compat = provider_config.get("compat")

        if is_builtin and provider_name not in builtin_defaults:
            from pi_ai.builtin_models import builtin_models

            built = [m for m in builtin_models() if m.provider == provider_name]
            if built:
                builtin_defaults[provider_name] = {
                    "api": built[0].api,
                    "baseUrl": built[0].base_url,
                }

        for model_def in models:
            if not isinstance(model_def, dict) or not model_def.get("id"):
                return ModelsJsonLoadResult(
                    error=f"Provider {provider_name}: each model needs an id",
                )
            model_id = str(model_def["id"])
            api = (
                model_def.get("api")
                or provider_api
                or builtin_defaults.get(provider_name, {}).get("api")
            )
            base_url = (
                model_def.get("baseUrl")
                or provider_base
                or builtin_defaults.get(provider_name, {}).get("baseUrl")
            )
            if not api:
                return ModelsJsonLoadResult(
                    error=(
                        f"Provider {provider_name}, model {model_id}: "
                        'no "api" specified.'
                    ),
                )
            if not base_url:
                return ModelsJsonLoadResult(
                    error=(
                        f"Provider {provider_name}, model {model_id}: "
                        "no baseUrl available."
                    ),
                )
            thinking_format = _merge_thinking_format(
                provider_compat if isinstance(provider_compat, dict) else None,
                model_def.get("compat")
                if isinstance(model_def.get("compat"), dict)
                else None,
            )
            model_headers = model_def.get("headers")
            if model_headers:
                result.model_headers[f"{provider_name}:{model_id}"] = dict(
                    model_headers
                )
            result.custom_models.append(
                Model(
                    id=model_id,
                    name=str(model_def.get("name") or model_id),
                    api=str(api),
                    provider=provider_name,
                    base_url=str(base_url),
                    reasoning=bool(model_def.get("reasoning", False)),
                    input=list(model_def.get("input") or ["text"]),
                    cost=_parse_cost(model_def.get("cost")),
                    context_window=int(model_def.get("contextWindow", 128_000)),
                    max_tokens=int(model_def.get("maxTokens", 16_384)),
                    thinking_format=thinking_format,
                )
            )

    return result


def load_models_json(path: str) -> ModelsJsonLoadResult:
    from pathlib import Path

    file_path = Path(path)
    if not file_path.is_file():
        return ModelsJsonLoadResult()

    try:
        raw = file_path.read_text(encoding="utf-8")
        parsed = json.loads(strip_json_comments(raw))
    except json.JSONDecodeError as exc:
        return ModelsJsonLoadResult(
            error=f"Failed to parse models.json: {exc}\n\nFile: {path}",
        )
    except OSError as exc:
        return ModelsJsonLoadResult(
            error=f"Failed to read models.json: {exc}\n\nFile: {path}",
        )

    if not isinstance(parsed, dict):
        return ModelsJsonLoadResult(
            error=f"Invalid models.json: expected object at root\n\nFile: {path}",
        )

    result = validate_and_parse(parsed)
    if result.error:
        result.error = f"{result.error}\n\nFile: {path}"
    return result
