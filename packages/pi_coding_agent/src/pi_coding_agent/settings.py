"""Settings loader (pi: settings-manager.ts subset)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from pi_ai.config_paths import CONFIG_DIR_NAME, get_agent_dir
from pi_ai.models_json import strip_json_comments

ThinkingLevel = str  # off | minimal | low | medium | high | xhigh


@dataclass
class Settings:
    default_provider: str | None = None
    default_model: str | None = None
    default_thinking_level: ThinkingLevel | None = None
    quiet_startup: bool = False


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_json_file(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(strip_json_comments(raw))
        return parsed if isinstance(parsed, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_settings(cwd: str | Path | None = None) -> Settings:
    """Merge global ~/.pi/agent/settings.json with project .pi/settings.json."""
    cwd_path = Path(cwd or ".").resolve()
    global_raw = _load_json_file(get_agent_dir() / "settings.json")
    project_raw = _load_json_file(cwd_path / CONFIG_DIR_NAME / "settings.json")
    merged = _deep_merge(global_raw, project_raw)
    return Settings(
        default_provider=merged.get("defaultProvider"),
        default_model=merged.get("defaultModel"),
        default_thinking_level=merged.get("defaultThinkingLevel"),
        quiet_startup=bool(merged.get("quietStartup", False)),
    )
