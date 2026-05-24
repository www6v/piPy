"""Print (single-shot) mode for pi-coding-agent."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from pi_agent.types import AgentEvent

from pi_coding_agent.event_log import log_agent_event
from pi_coding_agent.run_context import AgentRunConfig, create_agent_session_bundle


@dataclass
class PrintModeOptions:
    prompt: str
    model: str
    system_prompt: str | None
    tools: list[str]
    api_key: str | None
    provider: str | None
    thinking_level: str | None = None
    verbose: bool = False
    mode: str = "text"
    continue_session: bool = False
    session_path: str | None = None
    no_context_files: bool = False


def _to_run_config(options: PrintModeOptions) -> AgentRunConfig:
    return AgentRunConfig(
        model_pattern=options.model,
        system_prompt=options.system_prompt or None,
        tools=options.tools,
        api_key=options.api_key,
        provider=options.provider,
        thinking_level=options.thinking_level,
        continue_session=options.continue_session,
        session_path=options.session_path,
        no_context_files=options.no_context_files,
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

    session_bundle = await create_agent_session_bundle(_to_run_config(options))

    if on_session_header is not None and session_bundle.session_file:
        session_path = session_bundle.session_file
        first_line = Path(session_path).read_text(encoding="utf-8").splitlines()[:1]
        if first_line:
            header = json.loads(first_line[0])
            if header.get("type") == "session":
                on_session_header(header)

    final_text = ""
    final_assistant = None

    def handle_event(event: AgentEvent | dict[str, Any]) -> None:
        nonlocal final_text, final_assistant
        if isinstance(event, dict):
            from pi_coding_agent.modes.json_mode import stream_event_to_jsonable

            wrapped = json.dumps(
                stream_event_to_jsonable(event),
                ensure_ascii=False,
            )
            print(wrapped, flush=True)
            return
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

    session_bundle.subscribe_all(handle_event)
    await session_bundle.prompt(options.prompt)
    await session_bundle.wait_for_idle()

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
