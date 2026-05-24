"""Shared agent session setup for print and interactive modes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pi_agent.agent import Agent
from pi_ai.model_registry import ModelRegistry, get_registry
from pi_ai.types import Model

from pi_coding_agent.auth.resolve import resolve_auth_for_model
from pi_coding_agent.model_resolver import ResolvedModel, resolve_model_reference
from pi_coding_agent.session.manager import SessionManager
from pi_coding_agent.tools.registry import create_tools_for_names


@dataclass
class AgentRunConfig:
    model_pattern: str
    system_prompt: str
    tools: list[str]
    api_key: str | None = None
    provider: str | None = None
    thinking_level: str | None = None
    continue_session: bool = False
    session_path: str | None = None


@dataclass
class AgentSession:
    agent: Agent
    model: Model
    thinking_level: str | None
    session: SessionManager
    cwd: Path


def _ensure_faux_model(model_id: str) -> None:
    from pi_ai.providers import faux as faux_mod
    from pi_ai.providers.faux import (
        faux_assistant_message,
        faux_text,
        register_faux_provider,
    )

    if faux_mod.get_faux_model(model_id) is None:
        register_faux_provider(
            models=[{"id": model_id, "name": model_id}],
            handler=lambda _ctx: faux_assistant_message([faux_text("ok")]),
        )


def _resolve_session(config: AgentRunConfig, cwd: Path) -> SessionManager:
    if config.session_path:
        return SessionManager.open(config.session_path)
    if config.continue_session:
        existing = SessionManager.latest_for_cwd(cwd)
        if existing is not None:
            return existing
    return SessionManager.create(cwd)


def resolve_run_model(
    config: AgentRunConfig,
    registry: ModelRegistry | None = None,
) -> ResolvedModel:
    reg = registry or get_registry()
    resolved = resolve_model_reference(
        config.model_pattern,
        reg,
        provider_override=config.provider,
    )
    if config.thinking_level:
        resolved.thinking_level = config.thinking_level
    return resolved


def create_agent_session(
    config: AgentRunConfig,
    *,
    registry: ModelRegistry | None = None,
    system_prompt: str | None = None,
) -> AgentSession:
    reg = registry or get_registry()
    resolved = resolve_run_model(config, reg)
    if resolved.warning:
        import sys

        print(f"Warning: {resolved.warning}", file=sys.stderr)
    if resolved.provider == "faux":
        _ensure_faux_model(resolved.model_id)

    cwd = Path(os.getcwd())
    api_key, request_headers = resolve_auth_for_model(
        reg,
        resolved.model,
        api_key_override=config.api_key,
    )
    session = _resolve_session(config, cwd)
    agent = Agent(
        system_prompt=system_prompt or config.system_prompt,
        model=resolved.model,
        tools=create_tools_for_names(str(cwd), config.tools),
        api_key=api_key,
        request_headers=request_headers,
        initial_messages=session.load_messages(),
        thinking_level=resolved.thinking_level,
    )
    return AgentSession(
        agent=agent,
        model=resolved.model,
        thinking_level=resolved.thinking_level,
        session=session,
        cwd=cwd,
    )
