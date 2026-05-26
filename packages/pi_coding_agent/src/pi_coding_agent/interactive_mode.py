"""Minimal interactive REPL (pi: interactive mode subset, no TUI)."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from pi_ai.model_registry import get_registry
from pi_ai.types import AssistantMessage

from pi_coding_agent.agent_session import AgentSession
from pi_coding_agent.auth.storage import AuthStorage, get_auth_storage
from pi_coding_agent.event_log import log_agent_event
from pi_coding_agent.model_resolver import parse_model_pattern
from pi_coding_agent.run_context import AgentRunConfig, create_agent_session_bundle
from pi_coding_agent.session.manager import SessionManager
from pi_coding_agent.session.tree import (
    SessionTree,
    branch_entry_ids,
    build_session_tree,
    infer_active_leaf_id,
)
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
                "  /reload          Reload extensions/skills/prompts",
                "  /model [pattern] Show or switch model",
                "  /login <provider> <key>   Store provider API key",
                "  /logout <provider>        Remove provider API key",
                "  /tree            Show session tree and active leaf",
                "  /clone [entryId] Clone selected branch to a new session",
                "  /new             Start a fresh persisted session",
                "  /name <name>     Set display name for current session",
                "  /copy            Copy last assistant text to clipboard",
                "  /export [file]   Export transcript HTML (optional path)",
                "  /resume          Pick and resume a recent session",
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


def _handle_auth_command(
    line: str,
    auth_storage: AuthStorage,
) -> tuple[bool, str, bool]:
    if line == "/login" or line.startswith("/login "):
        parts = line.split(maxsplit=2)
        if len(parts) < 3:
            return True, "Usage: /login <provider> <key>", True
        provider = parts[1].strip()
        key = parts[2].strip()
        if not provider or not key:
            return True, "Usage: /login <provider> <key>", True
        try:
            auth_storage.set_api_key(provider, key)
        except ValueError as exc:
            return True, f"Login failed: {exc}", True
        return True, f"Stored API key for provider '{provider}'.", False
    if line == "/logout" or line.startswith("/logout "):
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            return True, "Usage: /logout <provider>", True
        provider = parts[1].strip()
        if not provider:
            return True, "Usage: /logout <provider>", True
        try:
            removed = auth_storage.logout(provider)
        except ValueError as exc:
            return True, f"Logout failed: {exc}", True
        if removed:
            return True, f"Removed API key for provider '{provider}'.", False
        return True, f"No stored API key for provider '{provider}'.", False
    return False, "", False


def _entry_summary(entry: dict) -> str:
    entry_type = str(entry.get("type", "entry"))
    if entry_type == "message":
        payload = entry.get("message")
        role = ""
        if isinstance(payload, dict):
            raw_role = payload.get("role")
            if isinstance(raw_role, str) and raw_role:
                role = raw_role
        if role:
            return f"{entry_type}:{role}"
    return entry_type


def _extract_last_assistant_text(session: AgentSession) -> str | None:
    for message in reversed(session.messages):
        if not isinstance(message, AssistantMessage):
            continue
        text = "".join(
            block.text
            for block in message.content
            if getattr(block, "type", "") == "text"
        )
        return text if text else None
    return None


def _copy_text_to_clipboard(text: str) -> tuple[bool, str]:
    commands: list[list[str]] = [
        ["pbcopy"],
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    ]
    attempted: list[str] = []
    for command in commands:
        attempted.append(command[0])
        try:
            subprocess.run(
                command,
                input=text,
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError:
            continue
        return True, "Copied last assistant response to clipboard."
    attempts = ", ".join(attempted)
    return False, f"Clipboard unavailable ({attempts})."


def _read_session_name(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        first_line = path.read_text(encoding="utf-8").splitlines()[:1]
    except OSError:
        return None
    if not first_line:
        return None
    try:
        header = json.loads(first_line[0])
    except json.JSONDecodeError:
        return None
    raw_name = header.get("name")
    if not isinstance(raw_name, str):
        return None
    name = raw_name.strip()
    return name or None


def _set_session_display_name(
    session_path: str | Path,
    name: str,
) -> tuple[bool, str]:
    path = Path(session_path).expanduser()
    if not path.is_file():
        return False, "Cannot name session: session file is missing."
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return False, f"Cannot name session: {exc}"
    if not lines:
        return False, "Cannot name session: session file is empty."
    try:
        header = json.loads(lines[0])
    except json.JSONDecodeError:
        return False, "Cannot name session: invalid session header."
    if not isinstance(header, dict):
        return False, "Cannot name session: invalid session header."
    header["name"] = name
    lines[0] = json.dumps(header, ensure_ascii=False)
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        return False, f"Cannot name session: {exc}"
    return True, f"Session name set to '{name}'."


def _resume_label(path: Path) -> str:
    name = _read_session_name(path)
    if not name:
        return path.name
    return f"{path.name} ({name})"


async def _pick_resume_session_path(
    cwd: Path,
    line_queue: asyncio.Queue[str | None],
) -> str | None:
    sessions = SessionManager.list_paths_for_cwd(cwd)
    if not sessions:
        print("No sessions found for current directory.", file=sys.stderr)
        return None
    if not sys.stdin.isatty() or len(sessions) == 1:
        return str(sessions[0])
    print("Select a session:")
    for idx, path in enumerate(sessions, start=1):
        print(f"  {idx}. {_resume_label(path)}")
    sys.stdout.write("Enter number (blank=latest): ")
    sys.stdout.flush()
    raw = await line_queue.get()
    if raw is None:
        return str(sessions[0])
    value = raw.strip()
    if not value:
        return str(sessions[0])
    try:
        selected = int(value)
    except ValueError:
        print("Invalid selection; using latest session.", file=sys.stderr)
        return str(sessions[0])
    if selected < 1 or selected > len(sessions):
        print("Selection out of range; using latest session.", file=sys.stderr)
        return str(sessions[0])
    return str(sessions[selected - 1])


def _render_tree_lines(
    tree: SessionTree,
    entry_id: str,
    active_leaf_id: str | None,
    prefix: str,
    is_last: bool,
) -> list[str]:
    marker = "`- " if is_last else "|- "
    entry = tree.entries_by_id[entry_id]
    summary = _entry_summary(entry)
    active_suffix = " <active>" if entry_id == active_leaf_id else ""
    lines = [f"{prefix}{marker}{entry_id} ({summary}){active_suffix}"]

    next_prefix = prefix + ("   " if is_last else "|  ")
    children = tree.children.get(entry_id, [])
    for idx, child_id in enumerate(children):
        lines.extend(
            _render_tree_lines(
                tree,
                child_id,
                active_leaf_id,
                next_prefix,
                idx == len(children) - 1,
            ),
        )
    return lines


def format_session_tree(entries: list[dict]) -> str:
    """Render a compact text tree with active leaf metadata."""

    tree = build_session_tree(entries)
    active_leaf_id = infer_active_leaf_id(entries)
    if not tree.entries_by_id:
        return "Session tree: (empty)"

    lines = ["Session tree:"]
    for idx, root_id in enumerate(tree.root_ids):
        lines.extend(
            _render_tree_lines(
                tree,
                root_id,
                active_leaf_id,
                "",
                idx == len(tree.root_ids) - 1,
            ),
        )
    if active_leaf_id is not None:
        lines.append(f"Active leaf: {active_leaf_id}")
    else:
        lines.append("Active leaf: (none)")
    return "\n".join(lines)


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
    auth_storage = get_auth_storage()

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
        if line == "/new":
            if session.is_streaming:
                print("Cannot create a new session while streaming.", file=sys.stderr)
                continue
            await session.new_session(cwd=session.cwd)
            print(f"Started new session: {session.session_file or '(in-memory)'}")
            continue
        if line == "/name" or line.startswith("/name "):
            parts = line.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                print("Usage: /name <name>", file=sys.stderr)
                continue
            if not session.session_file:
                print("Cannot name an in-memory session.", file=sys.stderr)
                continue
            ok, message = _set_session_display_name(
                session.session_file,
                parts[1].strip(),
            )
            if ok:
                print(message)
            else:
                print(message, file=sys.stderr)
            continue
        if line == "/copy":
            text = _extract_last_assistant_text(session)
            if text is None:
                print("No assistant text available to copy.", file=sys.stderr)
                continue
            ok, message = _copy_text_to_clipboard(text)
            if ok:
                print(message)
            else:
                print(message, file=sys.stderr)
            continue
        if line == "/export" or line.startswith("/export "):
            parts = line.split(maxsplit=1)
            output_path = parts[1].strip() if len(parts) > 1 else None
            target = output_path if output_path else None
            try:
                exported = session.export_html(target)
            except OSError as exc:
                print(f"Export failed: {exc}", file=sys.stderr)
                continue
            print(f"Exported: {exported}")
            continue
        if line == "/resume":
            if session.is_streaming:
                print("Cannot resume while the agent is streaming.", file=sys.stderr)
                continue
            selected_session_path = await _pick_resume_session_path(
                session.cwd,
                line_queue,
            )
            if selected_session_path is None:
                continue
            result = await create_agent_session(
                CreateAgentSessionOptions(
                    model=f"{session.model.provider}/{session.model.id}",
                    tools=options.tools,
                    system_prompt=session.agent.state.system_prompt,
                    system_prompt_is_final=True,
                    api_key=options.api_key,
                    provider=options.provider,
                    thinking_level=session.thinking_level,
                    continue_session=False,
                    session_path=selected_session_path,
                )
            )
            if result.warning:
                print(f"Warning: {result.warning}", file=sys.stderr)
            session = result.session
            model_label = f"{session.model.provider}/{session.model.id}"
            if session.thinking_level:
                model_label += f" (thinking: {session.thinking_level})"
            print(f"Resumed: {session.session_file}")
            continue
        if line == "/tools":
            print(", ".join(options.tools))
            continue
        handled_auth, auth_message, auth_is_error = _handle_auth_command(
            line,
            auth_storage,
        )
        if handled_auth:
            if auth_is_error:
                print(auth_message, file=sys.stderr)
            else:
                print(auth_message)
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
        if line == "/tree":
            if not session.session_file:
                print(
                    "Tree requires a persisted session file.",
                    file=sys.stderr,
                )
                continue
            manager = SessionManager.open(session.session_file)
            print(format_session_tree(manager.load_entries()))
            continue
        if line == "/clone" or line.startswith("/clone "):
            if session.is_streaming:
                print("Cannot clone while the agent is streaming.", file=sys.stderr)
                continue
            if not session.session_file:
                print(
                    "Clone requires a persisted session file.",
                    file=sys.stderr,
                )
                continue
            parts = line.split(maxsplit=1)
            selected_leaf_id = parts[1].strip() if len(parts) > 1 else None
            if selected_leaf_id == "":
                selected_leaf_id = None
            source_manager = SessionManager.open(session.session_file)
            source_entries = source_manager.load_entries()
            if selected_leaf_id is None:
                selected_leaf_id = infer_active_leaf_id(source_entries)
            if selected_leaf_id is None:
                print("Cannot clone an empty session.", file=sys.stderr)
                continue
            try:
                tree = build_session_tree(source_entries)
                branch_path = branch_entry_ids(tree, selected_leaf_id)
                branch_manager = SessionManager.fork_from(
                    source_manager.path,
                    session.cwd,
                    leaf_id=selected_leaf_id,
                )
            except ValueError as exc:
                print(f"Clone failed: {exc}", file=sys.stderr)
                continue
            result = await create_agent_session(
                CreateAgentSessionOptions(
                    model=f"{session.model.provider}/{session.model.id}",
                    tools=options.tools,
                    system_prompt=session.agent.state.system_prompt,
                    system_prompt_is_final=True,
                    api_key=options.api_key,
                    provider=options.provider,
                    thinking_level=session.thinking_level,
                    continue_session=False,
                    session_manager=branch_manager,
                )
            )
            if result.warning:
                print(f"Warning: {result.warning}", file=sys.stderr)
            session = result.session
            print(
                f"Cloned branch to {session.session_file} "
                f"(entries={len(branch_path)} leaf={selected_leaf_id})"
            )
            continue
        if line == "/reload":
            if session.is_streaming:
                print("Cannot reload while streaming.", file=sys.stderr)
                continue
            try:
                result = await session.reload_resources()
            except RuntimeError as exc:
                print(f"Reload failed: {exc}", file=sys.stderr)
                continue
            print(
                f"Reloaded resources: {len(result['commands'])} commands, "
                f"{len(result['diagnostics'])} diagnostics"
            )
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
