"""In-memory faux provider for tests."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pi_ai.types import (
    AssistantContent,
    AssistantMessage,
    Context,
    Model,
    ModelCost,
    TextContent,
    ToolCall,
    Usage,
    UsageCost,
)

DEFAULT_USAGE = Usage(cost=UsageCost())


@dataclass
class FauxModelDefinition:
    id: str
    name: str | None = None


FauxHandler = Callable[[Context], AssistantMessage]


def faux_text(text: str) -> TextContent:
    return TextContent(text=text)


def faux_tool_call(
    name: str,
    arguments: dict[str, Any],
    *,
    tool_id: str | None = None,
) -> ToolCall:
    return ToolCall(
        id=tool_id or f"tool:{time.time_ns()}",
        name=name,
        arguments=arguments,
    )


def faux_assistant_message(
    content: str | AssistantContent | list[AssistantContent],
    *,
    stop_reason: str = "stop",
    error_message: str | None = None,
) -> AssistantMessage:
    if stop_reason == "stop" and not isinstance(content, str):
        blocks_check = content if isinstance(content, list) else [content]
        if any(getattr(b, "type", None) == "toolCall" for b in blocks_check):
            stop_reason = "toolUse"
    if isinstance(content, str):
        blocks: list[AssistantContent] = [faux_text(content)]
    elif isinstance(content, list):
        blocks = content
    else:
        blocks = [content]
    return AssistantMessage(
        content=blocks,
        api="faux",
        provider="faux",
        model="faux-1",
        usage=DEFAULT_USAGE,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        timestamp=int(time.time() * 1000),
        error_message=error_message,
    )


@dataclass
class FauxRegistration:
    dispose: Callable[[], None]


@dataclass
class _FauxState:
    models: dict[str, Model] = field(default_factory=dict)
    handler: FauxHandler | None = None
    responses: list[AssistantMessage] = field(default_factory=list)
    call_count: int = 0


_state = _FauxState()


def register_faux_provider(
    *,
    provider_id: str = "faux",
    models: list[dict[str, str] | FauxModelDefinition],
    handler: FauxHandler | None = None,
) -> FauxRegistration:
    del provider_id
    _state.models.clear()
    for entry in models:
        model_id = entry["id"] if isinstance(entry, dict) else entry.id
        name = entry.get("name", model_id) if isinstance(entry, dict) else (
            entry.name or model_id
        )
        _state.models[model_id] = Model(
            id=model_id,
            name=name,
            api="faux",
            provider="faux",
            base_url="http://localhost:0",
            cost=ModelCost(),
        )
    _state.handler = handler
    if handler is not None:
        _state.responses.clear()
    _state.call_count = 0

    def dispose() -> None:
        _state.models.clear()
        _state.handler = None
        _state.responses.clear()
        _state.call_count = 0

    return FauxRegistration(dispose=dispose)


def get_faux_model(model_id: str) -> Model | None:
    return _state.models.get(model_id)


def set_faux_responses(responses: list[AssistantMessage]) -> None:
    _state.responses = list(responses)
    _state.handler = None


def next_faux_response(context: Context) -> AssistantMessage:
    _state.call_count += 1
    if _state.handler is not None:
        return _state.handler(context)
    if _state.responses:
        index = min(_state.call_count - 1, len(_state.responses) - 1)
        return _state.responses[index]
    return faux_assistant_message("")
