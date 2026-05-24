"""Credential storage from auth.json (pi: auth-storage.ts)."""

from __future__ import annotations

import json
from pathlib import Path

from pi_ai.config_paths import get_auth_path


class AuthStorage:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or get_auth_path()

    @property
    def path(self) -> Path:
        return self._path

    def get_api_key(self, provider: str) -> str | None:
        if not self._path.is_file():
            return None
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        entry = raw.get(provider)
        if not isinstance(entry, dict):
            return None
        if entry.get("type") != "api_key":
            return None
        key = entry.get("key")
        return str(key) if key else None


_default_auth: AuthStorage | None = None


def get_auth_storage(path: Path | None = None) -> AuthStorage:
    global _default_auth
    if path is not None or _default_auth is None:
        _default_auth = AuthStorage(path)
    return _default_auth
