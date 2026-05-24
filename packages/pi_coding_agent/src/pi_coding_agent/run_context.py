"""Shared agent session setup for print and interactive modes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pi_ai.model_registry import ModelRegistry

from pi_coding_agent.agent_session import AgentSession
from pi_coding_agent.sdk import CreateAgentSessionOptions, create_agent_session


@dataclass
class AgentRunConfig:
    model_pattern: str
    system_prompt: str | None
    tools: list[str]
    api_key: str | None = None
    provider: str | None = None
    thinking_level: str | None = None
    continue_session: bool = False
    session_path: str | None = None
    no_context_files: bool = False


# Backward-compatible alias used by print_mode imports.
AgentSessionBundle = AgentSession


async def create_agent_session_bundle(
    config: AgentRunConfig,
    *,
    registry: ModelRegistry | None = None,
    system_prompt: str | None = None,
) -> AgentSession:
    """Create session for CLI modes (wraps SDK)."""
    result = await create_agent_session(
        CreateAgentSessionOptions(
            cwd=Path(os.getcwd()),
            model=config.model_pattern,
            tools=config.tools,
            system_prompt=system_prompt
            if system_prompt is not None
            else config.system_prompt,
            no_context_files=config.no_context_files,
            api_key=config.api_key,
            provider=config.provider,
            thinking_level=config.thinking_level,
            continue_session=config.continue_session,
            session_path=config.session_path,
            model_registry=registry,
        )
    )
    if result.warning:
        import sys

        print(f"Warning: {result.warning}", file=sys.stderr)
    return result.session

