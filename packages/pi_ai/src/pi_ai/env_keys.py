"""Environment variable helpers for API keys."""

from __future__ import annotations

import os


def get_openai_api_key() -> str | None:
    return os.environ.get("OPENAI_API_KEY")
