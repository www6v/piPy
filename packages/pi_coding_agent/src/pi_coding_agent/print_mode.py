"""Print (single-shot) mode for pi-coding-agent."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pi_agent.agent import Agent
from pi_agent.types import AgentEvent
from pi_ai.model_registry import get_registry
from pi_ai.models import get_model

from pi_coding_agent.auth.resolve import resolve_auth_for_model
from pi_coding_agent.event_log import log_agent_event
from pi_coding_agent.session.manager import SessionManager
from pi_coding_agent.tools.registry import create_tools_for_names

DEFAULT_SYSTEM = (
    "You are a helpful coding assistant with read and bash tools. "
    "Use tools when needed to inspect the workspace."
)


@dataclass
class PrintModeOptions:
    prompt: str
    model: str
    system_prompt: str
    tools: list[str]
    api_key: str | None
    provider: str | None
    verbose: bool = False
    mode: str = "text"
    continue_session: bool = False
    session_path: str | None = None


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


def _resolve_session(options: PrintModeOptions, cwd: Path) -> SessionManager:
    if options.session_path:
        return SessionManager.open(options.session_path)
    if options.continue_session:
        existing = SessionManager.latest_for_cwd(cwd)
        if existing is not None:
            return existing
    return SessionManager.create(cwd)


async def _run_agent_session(
    options: PrintModeOptions,
    *,
    on_event: Callable[[AgentEvent], None],
    stream_text_to_stdout: bool = True,
    on_session_header: Callable[[dict[str, Any]], None] | None = None,
) -> int:
    provider, _, model_id = _parse_model(options.model, options.provider)
    registry = get_registry()
    if registry.load_error:
        print(f"Warning: {registry.load_error}", file=sys.stderr)

    cwd = Path(os.getcwd())
    if provider == "faux":
        _ensure_faux_model(model_id)
    model = get_model(provider, model_id)
    api_key, request_headers = resolve_auth_for_model(
        registry,
        model,
        api_key_override=options.api_key,
    )

    session = _resolve_session(options, cwd)
    if on_session_header is not None and session.path.is_file():
        first_line = session.path.read_text(encoding="utf-8").splitlines()[:1]
        if first_line:
            import json

            header = json.loads(first_line[0])
            if header.get("type") == "session":
                on_session_header(header)

    initial_messages = session.load_messages()
    agent = Agent(
        system_prompt=options.system_prompt or DEFAULT_SYSTEM,
        model=model,
        tools=create_tools_for_names(str(cwd), options.tools),
        api_key=api_key,
        request_headers=request_headers,
        initial_messages=initial_messages,
    )

    final_text = ""

    def handle_event(event: AgentEvent) -> None:
        nonlocal final_text
        if options.verbose and options.mode == "text":
            log_agent_event(event)
        on_event(event)
        if event.type == "message_update" and stream_text_to_stdout:
            for block in event.message.content:
                if block.type == "text":
                    delta = getattr(event.assistant_message_event, "delta", "")
                    if delta:
                        sys.stdout.write(delta)
                        sys.stdout.flush()
        if event.type == "message_end" and event.message.role == "assistant":
            parts = [
                block.text
                for block in event.message.content
                if block.type == "text"
            ]
            final_text = "".join(parts)

    agent.subscribe(handle_event)
    new_messages = await agent.prompt(options.prompt)
    await agent.wait_for_idle()
    session.append_messages(new_messages)

    if stream_text_to_stdout and final_text and not final_text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


async def run_print_mode(options: PrintModeOptions) -> int:
    if options.mode == "json":
        from pi_coding_agent.modes.json_mode import run_json_mode

        return await run_json_mode(options)

    return await _run_agent_session(
        options,
        on_event=lambda _event: None,
        stream_text_to_stdout=True,
    )


def _parse_model(model: str, provider_override: str | None) -> tuple[str, str, str]:
    if "/" in model:
        provider, model_id = model.split("/", 1)
    else:
        provider = provider_override or "openai"
        model_id = model
    if provider_override is not None:
        provider = provider_override
    return provider, provider, model_id
