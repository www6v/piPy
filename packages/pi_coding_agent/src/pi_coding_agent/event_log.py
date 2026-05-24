"""Agent event logging for print mode (--verbose)."""

from __future__ import annotations

import json
import sys
from typing import IO, Any

from pi_agent.types import AgentEvent


def _message_role_label(message: Any) -> str:
    role = getattr(message, "role", None)
    if role:
        return str(role)
    return type(message).__name__


def format_agent_event(event: AgentEvent) -> str | None:
    """
    One-line summary for stderr. Returns None to skip noisy events.
    """
    if event.type == "agent_start":
        return "agent_start"
    if event.type == "agent_end":
        count = len(event.messages)
        return f"agent_end messages={count}"
    if event.type == "turn_start":
        return "turn_start"
    if event.type == "turn_end":
        tools = len(event.tool_results)
        return f"turn_end tool_results={tools}"
    if event.type == "message_start":
        return f"message_start {_message_role_label(event.message)}"
    if event.type == "message_end":
        return f"message_end {_message_role_label(event.message)}"
    if event.type == "tool_execution_start":
        args_json = json.dumps(event.args, ensure_ascii=False)
        return f"tool_execution_start {event.tool_name} id={event.tool_call_id} args={args_json}"
    if event.type == "tool_execution_end":
        status = "error" if event.is_error else "ok"
        return (
            f"tool_execution_end {event.tool_name} id={event.tool_call_id} {status}"
        )
    # message_update: streamed to stdout; omit per-delta noise
    return None


def log_agent_event(
    event: AgentEvent,
    *,
    stream: IO[str] | None = None,
) -> None:
    line = format_agent_event(event)
    if line is None:
        return
    out = stream or sys.stderr
    print(f"[agent] {line}", file=out, flush=True)
