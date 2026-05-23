"""Environment variable helpers for API keys (pi: env-api-keys.ts)."""

from __future__ import annotations

import os

_API_KEY_ENV: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_OAUTH_TOKEN", "ANTHROPIC_API_KEY"),
    "openrouter": ("OPENROUTER_API_KEY",),
    "groq": ("GROQ_API_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "google": ("GEMINI_API_KEY",),
    "mistral": ("MISTRAL_API_KEY",),
    "together": ("TOGETHER_API_KEY",),
    "dashscope": ("DASHSCOPE_API_KEY",),
}


def find_env_keys(provider: str) -> list[str] | None:
    env_vars = _API_KEY_ENV.get(provider)
    if env_vars is None:
        return None
    found = [name for name in env_vars if os.environ.get(name)]
    return found or None


def get_env_api_key(provider: str) -> str | None:
    env_vars = _API_KEY_ENV.get(provider)
    if env_vars is None:
        return None
    for name in env_vars:
        value = os.environ.get(name)
        if value:
            return value
    return None


def get_openai_api_key() -> str | None:
    return get_env_api_key("openai")
