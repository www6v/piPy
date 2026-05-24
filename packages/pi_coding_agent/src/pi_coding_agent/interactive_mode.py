"""Minimal interactive REPL (pi: interactive mode subset, no TUI)."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from pi_ai.model_registry import get_registry

from pi_coding_agent.agent_session import AgentSession
from pi_coding_agent.event_log import log_agent_event
from pi_coding_agent.model_resolver import parse_model_pattern
from pi_coding_agent.run_context import AgentRunConfig, create_agent_session_bundle
from pi_coding_agent.sdk import CreateAgentSessionOptions, create_agent_session


@dataclass
class InteractiveOptions:
    model_pattern: str
    system_prompt: str | None
    tools: list[str]
    api_key: str | None
    provider: str | None
    thinking_level: str | None
    verbose: bool
    continue_session: bool
    session_path: str | None
    fork_session: str | None = None
    no_context_files: bool = False
    no_skills: bool = False
    no_prompt_templates: bool = False
    no_extensions: bool = False
    skill_paths: list[str] | None = None
    prompt_paths: list[str] | None = None
    extension_paths: list[str] | None = None


def _print_help() -> None:
    print(
        "\n".join(
            [
                "Commands:",
                "  /exit, /quit     Exit",
                "  /help            Show this help",
                "  /compact [instr] Compact session (optional hints)",
                "  /model [pattern] Show or switch model",
                "  /tools           List enabled tools",
                "  /session         Show session file path",
                "",
                "Enter a message to chat. Ctrl+C or Ctrl+D to exit.",
            ]
        )
    )


async def _pump_stdin_lines(queue: asyncio.Queue[str | None]) -> None:
    """Deliver stdin lines concurrently with an in-flight agent turn."""

    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            await queue.put(None)
            return
        stripped = line.rstrip("\n").rstrip("\r")
        await queue.put(stripped)


async def _run_turn(
    session: AgentSession,
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

    unsub = session.subscribe(handle_event)
    try:
        await session.prompt(user_text)
        await session.wait_for_idle()
    finally:
        unsub()

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
        system_prompt=options.system_prompt or None,
        tools=options.tools,
        api_key=options.api_key,
        provider=options.provider,
        thinking_level=options.thinking_level,
        continue_session=options.continue_session,
        session_path=options.session_path,
        fork_session=options.fork_session,
        no_context_files=options.no_context_files,
        no_skills=options.no_skills,
        no_prompt_templates=options.no_prompt_templates,
        no_extensions=options.no_extensions,
        skill_paths=options.skill_paths,
        prompt_paths=options.prompt_paths,
        extension_paths=options.extension_paths,
    )
    session = await create_agent_session_bundle(run_config)
    model_label = f"{session.model.provider}/{session.model.id}"
    if session.thinking_level:
        model_label += f" (thinking: {session.thinking_level})"

    print(f"piPy interactive — model: {model_label}")
    print(f"tools: {', '.join(options.tools)}")
    print("Type /help for commands.\n")

    line_queue: asyncio.Queue[str | None] = asyncio.Queue()
    asyncio.create_task(_pump_stdin_lines(line_queue))
    turn_task: asyncio.Task[int] | None = None

    def print_prompt_marker() -> None:
        sys.stdout.write("> ")
        sys.stdout.flush()

    while True:
        print_prompt_marker()
        try:
            line_raw = await line_queue.get()
        except asyncio.CancelledError:
            raise
        except KeyboardInterrupt:
            print()
            return 0

        if line_raw is None:
            print()
            return 0

        line = line_raw.strip()

        if not line:
            continue

        if line in ("/exit", "/quit"):
            return 0

        if turn_task is not None and not turn_task.done():
            if session.is_streaming and not line.startswith("/"):
                session.steer(line)
                preview = line if len(line) <= 160 else line[:157] + "..."
                print(f"Queued (steer): {preview}")
                continue
            prev = await turn_task
            turn_task = None
            if prev != 0:
                return prev

        if line == "/help":
            _print_help()
            continue
        if line == "/tools":
            print(", ".join(options.tools))
            continue
        if line.startswith("/compact"):
            if session.is_streaming:
                msg = "Cannot compact while the agent is streaming."
                print(msg, file=sys.stderr)
                continue
            remainder = line[len("/compact") :].strip()
            custom_instructions = remainder or None
            try:
                compact_result = await session.compact(
                    custom_instructions=custom_instructions,
                )
            except RuntimeError as exc:
                print(f"Compaction failed: {exc}", file=sys.stderr)
                continue
            print(
                f"Compacted: tokens_before={compact_result.tokens_before}, "
                f"first_kept_entry_id={compact_result.first_kept_entry_id}"
            )
            sys.stdout.flush()
            continue
        if line == "/session":
            print(session.session_file or "(in-memory)")
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
            result = await create_agent_session(
                CreateAgentSessionOptions(
                    model=f"{parsed.provider}/{parsed.model_id}",
                    tools=options.tools,
                    system_prompt=session.agent.state.system_prompt,
                    system_prompt_is_final=True,
                    api_key=options.api_key,
                    provider=options.provider,
                    thinking_level=parsed.thinking_level,
                    continue_session=False,
                    session_path=session.session_file,
                )
            )
            if result.warning:
                print(f"Warning: {result.warning}", file=sys.stderr)
            session = result.session
            model_label = f"{session.model.provider}/{session.model.id}"
            if session.thinking_level:
                model_label += f" (thinking: {session.thinking_level})"
            print(f"Switched to {model_label}")
            continue
        if line.startswith("/"):
            turn_task = asyncio.create_task(
                _run_turn(session, line, verbose=options.verbose),
            )
            continue
        turn_task = asyncio.create_task(
            _run_turn(session, line, verbose=options.verbose),
        )
