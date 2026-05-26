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
        entry = self._load_auth_map().get(provider)
        if not isinstance(entry, dict):
            return None
        if entry.get("type") != "api_key":
            return None
        key = entry.get("key")
        return str(key) if key else None

    def set_api_key(self, provider: str, key: str) -> None:
        normalized_provider = provider.strip()
        normalized_key = key.strip()
        if not normalized_provider:
            raise ValueError("provider is required")
        if not normalized_key:
            raise ValueError("key is required")
        raw = self._load_auth_map()
        raw[normalized_provider] = {
            "type": "api_key",
            "key": normalized_key,
        }
        self._write_auth_map(raw)

    def logout(self, provider: str) -> bool:
        normalized_provider = provider.strip()
        if not normalized_provider:
            raise ValueError("provider is required")
        raw = self._load_auth_map()
        removed = raw.pop(normalized_provider, None) is not None
        if removed:
            self._write_auth_map(raw)
        return removed

    def _load_auth_map(self) -> dict[str, object]:
        if not self._path.is_file():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(raw, dict):
            return {}
        return raw

    def _write_auth_map(self, payload: dict[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


_default_auth: AuthStorage | None = None


def get_auth_storage(path: Path | None = None) -> AuthStorage:
    global _default_auth
    if path is not None or _default_auth is None:
        _default_auth = AuthStorage(path)
    return _default_auth
