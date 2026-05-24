"""Minimal interactive REPL (pi: interactive mode subset, no TUI)."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from pi_ai.model_registry import get_registry

from pi_coding_agent.event_log import log_agent_event
from pi_coding_agent.model_resolver import parse_model_pattern
from pi_coding_agent.print_mode import DEFAULT_SYSTEM
from pi_coding_agent.run_context import AgentRunConfig, create_agent_session


@dataclass
class InteractiveOptions:
    model_pattern: str
    system_prompt: str
    tools: list[str]
    api_key: str | None
    provider: str | None
    thinking_level: str | None
    verbose: bool
    continue_session: bool
    session_path: str | None


def _print_help() -> None:
    print(
        "\n".join(
            [
                "Commands:",
                "  /exit, /quit     Exit",
                "  /help            Show this help",
                "  /model [pattern] Show or switch model",
                "  /tools           List enabled tools",
                "  /session         Show session file path",
                "",
                "Enter a message to chat. Ctrl+C or Ctrl+D to exit.",
            ]
        )
    )


async def _run_turn(
    session_bundle,
    user_text: str,
    *,
    verbose: bool,
) -> int:
    final_assistant = None

    def handle_event(event) -> None:
        nonlocal final_assistant
        if verbose:
            log_agent_event(event)
        if event.type == "message_update":
            for block in event.message.content:
                if block.type == "text":
                    delta = getattr(event.assistant_message_event, "delta", "")
                    if delta:
                        sys.stdout.write(delta)
                        sys.stdout.flush()
        if event.type == "message_end" and event.message.role == "assistant":
            final_assistant = event.message

    session_bundle.agent.subscribe(handle_event)
    new_messages = await session_bundle.agent.prompt(user_text)
    await session_bundle.agent.wait_for_idle()
    session_bundle.session.append_messages(new_messages)
    sys.stdout.write("\n")
    if final_assistant is not None and final_assistant.stop_reason in (
        "error",
        "aborted",
    ):
        error_message = final_assistant.error_message or "Agent request failed"
        print(f"Error: {error_message}", file=sys.stderr)
        return 1
    return 0


async def run_interactive_mode(options: InteractiveOptions) -> int:
    registry = get_registry()
    if registry.load_error:
        print(f"Warning: {registry.load_error}", file=sys.stderr)

    run_config = AgentRunConfig(
        model_pattern=options.model_pattern,
        system_prompt=options.system_prompt or DEFAULT_SYSTEM,
        tools=options.tools,
        api_key=options.api_key,
        provider=options.provider,
        thinking_level=options.thinking_level,
        continue_session=options.continue_session,
        session_path=options.session_path,
    )
    session_bundle = create_agent_session(run_config)
    model_label = (
        f"{session_bundle.model.provider}/{session_bundle.model.id}"
    )
    if session_bundle.thinking_level:
        model_label += f" (thinking: {session_bundle.thinking_level})"

    print(f"piPy interactive — model: {model_label}")
    print(f"tools: {', '.join(options.tools)}")
    print("Type /help for commands.\n")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line in ("/exit", "/quit"):
            return 0
        if line == "/help":
            _print_help()
            continue
        if line == "/tools":
            print(", ".join(options.tools))
            continue
        if line == "/session":
            print(session_bundle.session.path)
            continue
        if line.startswith("/model"):
            parts = line.split(maxsplit=1)
            if len(parts) == 1:
                print(model_label)
                continue
            pattern = parts[1]
            parsed = parse_model_pattern(pattern, registry)
            if parsed is None:
                print(f"Unknown model pattern: {pattern}", file=sys.stderr)
                continue
            run_config.model_pattern = (
                f"{parsed.provider}/{parsed.model_id}"
            )
            run_config.thinking_level = parsed.thinking_level
            if parsed.warning:
                print(f"Warning: {parsed.warning}", file=sys.stderr)
            session_bundle = create_agent_session(
                run_config,
                system_prompt=session_bundle.agent.state.system_prompt,
            )
            model_label = (
                f"{session_bundle.model.provider}/"
                f"{session_bundle.model.id}"
            )
            if session_bundle.thinking_level:
                model_label += f" (thinking: {session_bundle.thinking_level})"
            print(f"Switched to {model_label}")
            continue
        if line.startswith("/"):
            print(f"Unknown command: {line.split()[0]}", file=sys.stderr)
            continue
        code = await _run_turn(session_bundle, line, verbose=options.verbose)
        if code != 0:
            return code
