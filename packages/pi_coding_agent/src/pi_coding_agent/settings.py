"""Settings loader (pi: settings-manager.ts subset)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pi_ai.config_paths import CONFIG_DIR_NAME, get_agent_dir
from pi_ai.models_json import strip_json_comments

ThinkingLevel = str  # off | minimal | low | medium | high | xhigh


@dataclass
class CompactionSettings:
    enabled: bool = True
    reserve_tokens: int = 16384
    keep_recent_tokens: int = 20000


@dataclass
class RetrySettings:
    enabled: bool = True
    max_retries: int = 3
    base_delay_ms: int = 2000


@dataclass
class Settings:
    default_provider: str | None = None
    default_model: str | None = None
    default_thinking_level: ThinkingLevel | None = None
    quiet_startup: bool = False
    compaction: CompactionSettings = field(default_factory=CompactionSettings)
    retry: RetrySettings = field(default_factory=RetrySettings)
    steering_mode: str = "one-at-a-time"
    follow_up_mode: str = "one-at-a-time"
    skills: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)
    extensions: list[str] = field(default_factory=list)
    enable_skill_commands: bool = True


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


def _nested_dict(parent: Mapping[str, Any], key: str) -> dict[str, Any]:
    """Return parent[key] if it is a dict, else {}."""
    value = parent.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return bool(value)


def _coerce_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_str(value: Any, default: str) -> str:
    if value is None or not isinstance(value, str):
        return default
    return value


def _coerce_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _parse_compaction(mapping: Mapping[str, Any]) -> CompactionSettings:
    nested = _nested_dict(mapping, "compaction")
    return CompactionSettings(
        enabled=_coerce_bool(nested.get("enabled"), True),
        reserve_tokens=_coerce_int(nested.get("reserveTokens"), 16384),
        keep_recent_tokens=_coerce_int(
            nested.get("keepRecentTokens"),
            20000,
        ),
    )


def _parse_retry(mapping: Mapping[str, Any]) -> RetrySettings:
    nested = _nested_dict(mapping, "retry")
    return RetrySettings(
        enabled=_coerce_bool(nested.get("enabled"), True),
        max_retries=_coerce_int(nested.get("maxRetries"), 3),
        base_delay_ms=_coerce_int(nested.get("baseDelayMs"), 2000),
    )


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
    steering_mode = _coerce_str(
        merged.get("steeringMode"),
        "one-at-a-time",
    )
    follow_up_mode = _coerce_str(
        merged.get("followUpMode"),
        "one-at-a-time",
    )
    return Settings(
        default_provider=merged.get("defaultProvider"),
        default_model=merged.get("defaultModel"),
        default_thinking_level=merged.get("defaultThinkingLevel"),
        quiet_startup=bool(merged.get("quietStartup", False)),
        compaction=_parse_compaction(merged),
        retry=_parse_retry(merged),
        steering_mode=steering_mode,
        follow_up_mode=follow_up_mode,
        skills=_coerce_str_list(merged.get("skills")),
        prompts=_coerce_str_list(merged.get("prompts")),
        extensions=_coerce_str_list(merged.get("extensions")),
        enable_skill_commands=_coerce_bool(
            merged.get("enableSkillCommands"),
            True,
        ),
    )
