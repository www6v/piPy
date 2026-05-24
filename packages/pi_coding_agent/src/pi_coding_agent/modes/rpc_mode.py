"""RPC mode: JSONL commands on stdin, events on stdout (pi: rpc-mode.ts subset)."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from typing import Any

from pi_ai.model_registry import get_registry

from pi_coding_agent.modes.json_mode import stream_event_to_jsonable
from pi_coding_agent.sdk import CreateAgentSessionOptions, create_agent_session


def _serialize_line(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


def _write_stdout(obj: dict[str, Any]) -> None:
    sys.stdout.write(_serialize_line(obj))
    sys.stdout.flush()


def _success(
    request_id: str | None,
    command: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": request_id,
        "type": "response",
        "command": command,
        "success": True,
    }
    if data is not None:
        payload["data"] = data
    return payload


def _error(
    request_id: str | None,
    command: str,
    message: str,
) -> dict[str, Any]:
    return {
        "id": request_id,
        "type": "response",
        "command": command,
        "success": False,
        "error": message,
    }


async def _read_stdin_lines() -> asyncio.Queue[str | None]:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def reader() -> None:
        while True:
            line = sys.stdin.readline()
            if not line:
                loop.call_soon_threadsafe(queue.put_nowait, None)
                return
            line = line.rstrip("\n").rstrip("\r")
            loop.call_soon_threadsafe(queue.put_nowait, line)

    loop.run_in_executor(None, reader)
    return queue


@dataclass
class RpcModeOptions:
    model: str
    tools: list[str]
    api_key: str | None
    provider: str | None
    thinking_level: str | None
    no_session: bool
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


async def run_rpc_mode(options: RpcModeOptions) -> int:
    registry = get_registry()
    if registry.load_error:
        print(f"Warning: {registry.load_error}", file=sys.stderr)

    result = await create_agent_session(
        CreateAgentSessionOptions(
            model=options.model,
            tools=options.tools,
            api_key=options.api_key,
            provider=options.provider,
            thinking_level=options.thinking_level,
            in_memory=options.no_session,
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
    )
    session = result.session
    if result.warning:
        print(f"Warning: {result.warning}", file=sys.stderr)

    session.subscribe_all(
        lambda event: _write_stdout(stream_event_to_jsonable(event)),
    )

    queue = await _read_stdin_lines()
    prompt_lock = asyncio.Lock()

    async def handle_command(command: dict[str, Any]) -> None:
        request_id = command.get("id")
        cmd_type = command.get("type")
        if not isinstance(cmd_type, str):
            _write_stdout(_error(request_id, "unknown", "Missing command type"))
            return

        if cmd_type == "prompt":
            message = command.get("message")
            if not isinstance(message, str) or not message.strip():
                _write_stdout(_error(request_id, "prompt", "message is required"))
                return
            raw_behavior = command.get("streamingBehavior")
            stream_behavior: str | None = None
            if isinstance(raw_behavior, str):
                trimmed = raw_behavior.strip()
                if trimmed in ("steer", "followUp"):
                    stream_behavior = trimmed
            if session.is_streaming:
                if stream_behavior is None:
                    _write_stdout(
                        _error(
                            request_id,
                            "prompt",
                            "Agent is streaming; set streamingBehavior",
                        )
                    )
                    return
                _write_stdout(_success(request_id, "prompt"))
                async with prompt_lock:
                    try:
                        await session.prompt(
                            message,
                            streaming_behavior=stream_behavior,
                            input_source="rpc",
                        )
                        await session.wait_for_idle()
                    except Exception as exc:
                        _write_stdout(
                            {
                                "type": "rpc_error",
                                "command": "prompt",
                                "error": str(exc),
                            }
                        )
                return
            _write_stdout(_success(request_id, "prompt"))
            async with prompt_lock:
                try:
                    await session.prompt(
                        message,
                        streaming_behavior=None,
                        input_source="rpc",
                    )
                    await session.wait_for_idle()
                except Exception as exc:
                    _write_stdout(
                        {
                            "type": "rpc_error",
                            "command": "prompt",
                            "error": str(exc),
                        }
                    )
            return

        if cmd_type == "abort":
            session.abort()
            _write_stdout(_success(request_id, "abort"))
            return

        if cmd_type == "get_state":
            _write_stdout(
                _success(request_id, "get_state", session.get_rpc_state())
            )
            return

        if cmd_type == "get_messages":
            _write_stdout(
                _success(
                    request_id,
                    "get_messages",
                    {"messages": session.get_messages_json()},
                )
            )
            return

        if cmd_type == "get_commands":
            _write_stdout(
                _success(
                    request_id,
                    "get_commands",
                    {"commands": session.get_commands()},
                )
            )
            return

        if cmd_type == "get_available_models":
            models = [
                {
                    "id": model.id,
                    "name": model.name,
                    "provider": model.provider,
                    "api": model.api,
                }
                for model in registry.get_all()
            ]
            _write_stdout(
                _success(request_id, "get_available_models", {"models": models})
            )
            return

        if cmd_type == "set_model":
            provider = command.get("provider")
            model_id = command.get("modelId")
            if not provider or not model_id:
                _write_stdout(
                    _error(request_id, "set_model", "provider and modelId required")
                )
                return
            try:
                model = await session.set_model(str(provider), str(model_id))
            except Exception as exc:
                _write_stdout(_error(request_id, "set_model", str(exc)))
                return
            from pi_coding_agent.session.serialize import model_to_dict

            _write_stdout(
                _success(request_id, "set_model", model_to_dict(model))
            )
            return

        if cmd_type == "set_thinking_level":
            level = command.get("level")
            if not isinstance(level, str):
                _write_stdout(
                    _error(request_id, "set_thinking_level", "level is required")
                )
                return
            session.set_thinking_level(level)
            _write_stdout(_success(request_id, "set_thinking_level"))
            return

        if cmd_type == "new_session":
            await session.new_session()
            _write_stdout(
                _success(request_id, "new_session", {"cancelled": False})
            )
            return

        if cmd_type == "compact":
            if session.is_streaming:
                _write_stdout(
                    _error(
                        request_id,
                        "compact",
                        "Cannot compact while the agent is streaming",
                    )
                )
                return
            instructions_raw = command.get("customInstructions")
            custom_instructions = None
            if instructions_raw is not None:
                if not isinstance(instructions_raw, str):
                    _write_stdout(
                        _error(
                            request_id,
                            "compact",
                            "customInstructions must be a string",
                        )
                    )
                    return
                stripped = instructions_raw.strip()
                if stripped:
                    custom_instructions = stripped
            async with prompt_lock:
                try:
                    compact_result = await session.compact(
                        custom_instructions=custom_instructions,
                    )
                except Exception as exc:
                    _write_stdout(
                        _error(request_id, "compact", str(exc))
                    )
                    return
            _write_stdout(
                _success(
                    request_id,
                    "compact",
                    {
                        "summary": compact_result.summary,
                        "firstKeptEntryId": (
                            compact_result.first_kept_entry_id
                        ),
                        "tokensBefore": compact_result.tokens_before,
                    },
                )
            )
            return

        if cmd_type == "set_auto_compaction":
            if "enabled" not in command:
                _write_stdout(
                    _error(
                        request_id,
                        "set_auto_compaction",
                        "\"enabled\" is required",
                    )
                )
                return
            enabled_raw = command.get("enabled")
            if not isinstance(enabled_raw, bool):
                _write_stdout(
                    _error(
                        request_id,
                        "set_auto_compaction",
                        "\"enabled\" must be a boolean",
                    )
                )
                return
            session.set_auto_compaction(enabled_raw)
            _write_stdout(
                _success(request_id, "set_auto_compaction")
            )
            return

        if cmd_type == "set_auto_retry":
            if "enabled" not in command:
                _write_stdout(
                    _error(
                        request_id,
                        "set_auto_retry",
                        "\"enabled\" is required",
                    )
                )
                return
            enabled_raw_retry = command.get("enabled")
            if not isinstance(enabled_raw_retry, bool):
                _write_stdout(
                    _error(
                        request_id,
                        "set_auto_retry",
                        "\"enabled\" must be a boolean",
                    )
                )
                return
            session.set_auto_retry(enabled_raw_retry)
            _write_stdout(_success(request_id, "set_auto_retry"))
            return

        if cmd_type == "abort_retry":
            session.abort_retry()
            _write_stdout(_success(request_id, "abort_retry"))
            return

        if cmd_type == "bash":
            command_text = command.get("command")
            if not isinstance(command_text, str) or not command_text.strip():
                _write_stdout(_error(request_id, "bash", "command is required"))
                return
            timeout_raw = command.get("timeout")
            timeout: float | None = None
            if timeout_raw is not None:
                try:
                    timeout = float(timeout_raw)
                except (TypeError, ValueError):
                    _write_stdout(_error(request_id, "bash", "timeout must be a number"))
                    return
            async with prompt_lock:
                result = await session.run_bash_command(
                    command_text,
                    timeout=timeout,
                )
            _write_stdout(_success(request_id, "bash", result))
            return

        if cmd_type == "get_session_stats":
            _write_stdout(
                _success(
                    request_id,
                    "get_session_stats",
                    session.get_session_stats(),
                )
            )
            return

        if cmd_type == "export_html":
            output_path = command.get("outputPath")
            if output_path is not None and not isinstance(output_path, str):
                _write_stdout(
                    _error(
                        request_id,
                        "export_html",
                        "outputPath must be a string",
                    )
                )
                return
            path = session.export_html(output_path=output_path)
            _write_stdout(
                _success(request_id, "export_html", {"path": path})
            )
            return

        if cmd_type == "steer":
            raw_msg = command.get("message")
            if not isinstance(raw_msg, str) or not raw_msg.strip():
                _write_stdout(
                    _error(request_id, "steer", "message is required")
                )
                return
            session.steer(raw_msg)
            await session.flush_queue_broadcast()
            _write_stdout(_success(request_id, "steer"))
            return

        if cmd_type == "follow_up":
            raw_msg = command.get("message")
            if not isinstance(raw_msg, str) or not raw_msg.strip():
                _write_stdout(
                    _error(request_id, "follow_up", "message is required")
                )
                return
            session.follow_up(raw_msg)
            await session.flush_queue_broadcast()
            _write_stdout(_success(request_id, "follow_up"))
            return

        if cmd_type == "set_steering_mode":
            mode = command.get("mode")
            if mode not in ("all", "one-at-a-time"):
                _write_stdout(
                    _error(
                        request_id,
                        "set_steering_mode",
                        '"mode" must be "all" or "one-at-a-time"',
                    )
                )
                return
            session.set_steering_mode(str(mode))
            await session.flush_queue_broadcast()
            _write_stdout(_success(request_id, "set_steering_mode"))
            return

        if cmd_type == "set_follow_up_mode":
            mode = command.get("mode")
            if mode not in ("all", "one-at-a-time"):
                _write_stdout(
                    _error(
                        request_id,
                        "set_follow_up_mode",
                        '"mode" must be "all" or "one-at-a-time"',
                    )
                )
                return
            session.set_follow_up_mode(str(mode))
            await session.flush_queue_broadcast()
            _write_stdout(_success(request_id, "set_follow_up_mode"))
            return

        _write_stdout(_error(request_id, cmd_type, f"Unknown command: {cmd_type}"))

    while True:
        line = await queue.get()
        if line is None:
            break
        if not line.strip():
            continue
        try:
            command = json.loads(line)
        except json.JSONDecodeError as exc:
            _write_stdout(_error(None, "parse", str(exc)))
            continue
        if not isinstance(command, dict):
            _write_stdout(_error(None, "parse", "Command must be a JSON object"))
            continue
        await handle_command(command)

    return 0
