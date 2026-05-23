"""Resolve models.json config values (pi: resolve-config-value.ts)."""

from __future__ import annotations

import os
import subprocess


def resolve_config_value(config: str) -> str | None:
    """
    Resolve apiKey / header values from models.json.

    - ``!command`` runs a shell command (stdout, trimmed).
    - Otherwise use env var if set, else treat as literal.
    """
    if config.startswith("!"):
        command = config[1:]
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        value = (result.stdout or "").strip()
        return value or None
    env_value = os.environ.get(config)
    if env_value:
        return env_value
    return config


def resolve_config_value_or_raise(config: str, label: str) -> str:
    value = resolve_config_value(config)
    if value is None:
        raise ValueError(f"Could not resolve {label} from config value {config!r}")
    return value
