"""Print (single-shot) mode for pi-coding-agent."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pi_agent.types import AgentEvent

from pi_coding_agent.event_log import log_agent_event
from pi_coding_agent.run_context import AgentRunConfig, create_agent_session

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
    thinking_level: str | None = None
    verbose: bool = False
    mode: str = "text"
    continue_session: bool = False
    session_path: str | None = None


def _to_run_config(options: PrintModeOptions) -> AgentRunConfig:
    return AgentRunConfig(
        model_pattern=options.model,
        system_prompt=options.system_prompt or DEFAULT_SYSTEM,
        tools=options.tools,
        api_key=options.api_key,
        provider=options.provider,
        thinking_level=options.thinking_level,
        continue_session=options.continue_session,
        session_path=options.session_path,
    )


async def _run_agent_session(
    options: PrintModeOptions,
    *,
    on_event: Callable[[AgentEvent], None],
    stream_text_to_stdout: bool = True,
    on_session_header: Callable[[dict[str, Any]], None] | None = None,
) -> int:
    import json
    from pi_ai.model_registry import get_registry

    registry = get_registry()
    if registry.load_error:
        print(f"Warning: {registry.load_error}", file=sys.stderr)

    session_bundle = create_agent_session(_to_run_config(options))
    session = session_bundle.session
    agent = session_bundle.agent

    if on_session_header is not None and session.path.is_file():
        first_line = session.path.read_text(encoding="utf-8").splitlines()[:1]
        if first_line:
            header = json.loads(first_line[0])
            if header.get("type") == "session":
                on_session_header(header)

    final_text = ""
    final_assistant = None

    def handle_event(event: AgentEvent) -> None:
        nonlocal final_text, final_assistant
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
            final_assistant = event.message
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

    if final_assistant is not None and final_assistant.stop_reason in (
        "error",
        "aborted",
    ):
        error_message = final_assistant.error_message or "Agent request failed"
        print(f"Error: {error_message}", file=sys.stderr)
        return 1
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
