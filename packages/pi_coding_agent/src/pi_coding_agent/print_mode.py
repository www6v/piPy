"""Print (single-shot) mode for pi-coding-agent."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from pi_agent.agent import Agent
from pi_ai.model_registry import get_registry
from pi_ai.models import get_model
from pi_ai.types import TextContent

from pi_coding_agent.event_log import log_agent_event
from pi_coding_agent.tools.registry import create_tools_for_names


@dataclass
class PrintModeOptions:
    prompt: str
    model: str
    system_prompt: str
    tools: list[str]
    api_key: str | None
    provider: str | None
    verbose: bool = False


DEFAULT_SYSTEM = (
    "You are a helpful coding assistant with read and bash tools. "
    "Use tools when needed to inspect the workspace."
)


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


async def run_print_mode(options: PrintModeOptions) -> int:
    provider, _, model_id = _parse_model(options.model, options.provider)
    registry = get_registry()
    if registry.load_error:
        print(f"Warning: {registry.load_error}", file=sys.stderr)
    if provider == "faux":
        _ensure_faux_model(model_id)
    model = get_model(provider, model_id)
    api_key, request_headers = registry.resolve_auth(
        model,
        api_key_override=options.api_key,
    )
    cwd = os.getcwd()
    agent = Agent(
        system_prompt=options.system_prompt or DEFAULT_SYSTEM,
        model=model,
        tools=create_tools_for_names(cwd, options.tools),
        api_key=api_key,
        request_headers=request_headers,
    )

    final_text = ""

    def on_event(event) -> None:
        nonlocal final_text
        if options.verbose:
            log_agent_event(event)
        if event.type == "message_update":
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

    agent.subscribe(on_event)
    await agent.prompt(options.prompt)
    await agent.wait_for_idle()
    if final_text and not final_text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _parse_model(model: str, provider_override: str | None) -> tuple[str, str, str]:
    if "/" in model:
        provider, model_id = model.split("/", 1)
    else:
        provider = provider_override or "openai"
        model_id = model
    if provider_override is not None:
        provider = provider_override
    return provider, provider, model_id
