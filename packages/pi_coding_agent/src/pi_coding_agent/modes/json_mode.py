"""JSON event stream mode (pi: --mode json)."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, is_dataclass
from typing import Any

from pi_agent.types import AgentEvent

from pi_coding_agent.print_mode import PrintModeOptions, _run_agent_session


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_jsonable(val) for key, val in asdict(value).items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(val) for key, val in value.items()}
    return value


def agent_event_to_dict(event: AgentEvent) -> dict[str, Any]:
    if event.type == "agent_start":
        return {"type": "agent_start"}
    if event.type == "agent_end":
        return {
            "type": "agent_end",
            "messages": [_to_jsonable(message) for message in event.messages],
        }
    if event.type == "turn_start":
        return {"type": "turn_start"}
    if event.type == "turn_end":
        return {
            "type": "turn_end",
            "message": _to_jsonable(event.message),
            "toolResults": [_to_jsonable(item) for item in event.tool_results],
        }
    if event.type == "message_start":
        return {"type": "message_start", "message": _to_jsonable(event.message)}
    if event.type == "message_update":
        payload: dict[str, Any] = {
            "type": "message_update",
            "message": _to_jsonable(event.message),
        }
        if event.assistant_message_event is not None:
            payload["assistantMessageEvent"] = _to_jsonable(
                event.assistant_message_event
            )
        return payload
    if event.type == "message_end":
        return {"type": "message_end", "message": _to_jsonable(event.message)}
    if event.type == "tool_execution_start":
        return {
            "type": "tool_execution_start",
            "toolCallId": event.tool_call_id,
            "toolName": event.tool_name,
            "args": event.args,
        }
    if event.type == "tool_execution_end":
        return {
            "type": "tool_execution_end",
            "toolCallId": event.tool_call_id,
            "toolName": event.tool_name,
            "result": _to_jsonable(event.result),
            "isError": event.is_error,
        }
    return {"type": str(event.type)}


async def run_json_mode(options: PrintModeOptions) -> int:
    session_header: dict[str, Any] | None = None

    def on_event(event: AgentEvent) -> None:
        print(json.dumps(agent_event_to_dict(event), ensure_ascii=False), flush=True)

    def on_session_header(header: dict[str, Any]) -> None:
        nonlocal session_header
        session_header = header
        print(json.dumps(header, ensure_ascii=False), flush=True)

    return await _run_agent_session(
        options,
        on_event=on_event,
        stream_text_to_stdout=False,
        on_session_header=on_session_header,
    )
