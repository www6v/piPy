"""User config paths (aligned with pi coding-agent config.ts)."""

from __future__ import annotations

import os
from pathlib import Path

# pi APP_NAME defaults to "pi" -> PI_CODING_AGENT_DIR
ENV_AGENT_DIR = "PI_CODING_AGENT_DIR"
CONFIG_DIR_NAME = ".pi"
AGENT_SUBDIR = "agent"


def get_agent_dir() -> Path:
    env_dir = os.environ.get(ENV_AGENT_DIR)
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return Path.home() / CONFIG_DIR_NAME / AGENT_SUBDIR


def get_models_path() -> Path:
    return get_agent_dir() / "models.json"
