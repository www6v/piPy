"""Core types for pi-ai."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

StopReason = Literal["stop", "length", "toolUse", "error", "aborted"]


@dataclass
class ModelCost:
    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0


@dataclass
class Model:
    id: str
    name: str
    api: str
    provider: str
    base_url: str
    reasoning: bool = False
    input: list[str] = field(default_factory=lambda: ["text"])
    cost: ModelCost = field(default_factory=ModelCost)
    context_window: int = 128_000
    max_tokens: int = 16_384
    # From models.json compat.thinkingFormat (openai-completions).
    thinking_format: str | None = None
    # Per-model / merged request headers from models.json.
    headers: dict[str, str] | None = None
    # models.json provider.authHeader -> Authorization: Bearer <key>.
    auth_header: bool = False
    # models.json compat (openai-completions).
    supports_developer_role: bool = True
    supports_reasoning_effort: bool = True


@dataclass
class UsageCost:
    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0
    total: float = 0.0


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    total_tokens: int = 0
    cost: UsageCost = field(default_factory=UsageCost)


@dataclass
class TextContent:
    type: Literal["text"] = "text"
    text: str = ""


@dataclass
class ToolCall:
    type: Literal["toolCall"] = "toolCall"
    id: str = ""
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


AssistantContent = TextContent | ToolCall


@dataclass
class UserMessage:
    content: str | list[TextContent]
    role: Literal["user"] = "user"
    timestamp: int = 0


@dataclass
class AssistantMessage:
    content: list[AssistantContent]
    api: str
    provider: str
    model: str
    usage: Usage
    stop_reason: StopReason
    role: Literal["assistant"] = "assistant"
    timestamp: int = 0
    error_message: str | None = None


@dataclass
class ToolResultMessage:
    tool_call_id: str
    tool_name: str
    content: list[TextContent]
    role: Literal["toolResult"] = "toolResult"
    is_error: bool = False
    timestamp: int = 0


Message = UserMessage | AssistantMessage | ToolResultMessage


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class Context:
    system_prompt: str = ""
    messages: list[Message] = field(default_factory=list)
    tools: list[Tool] | None = None


@dataclass
class StreamStartEvent:
    type: Literal["start"] = "start"
    partial: AssistantMessage = field(default_factory=lambda: _empty_assistant())


@dataclass
class TextDeltaEvent:
    type: Literal["text_delta"] = "text_delta"
    delta: str = ""
    partial: AssistantMessage = field(default_factory=lambda: _empty_assistant())


@dataclass
class StreamDoneEvent:
    type: Literal["done"] = "done"
    message: AssistantMessage = field(default_factory=lambda: _empty_assistant())


@dataclass
class StreamErrorEvent:
    type: Literal["error"] = "error"
    error: str = ""
    partial: AssistantMessage = field(default_factory=lambda: _empty_assistant())


StreamEvent = StreamStartEvent | TextDeltaEvent | StreamDoneEvent | StreamErrorEvent


def _empty_assistant() -> AssistantMessage:
    return AssistantMessage(
        content=[],
        api="",
        provider="",
        model="",
        usage=Usage(),
        stop_reason="stop",
    )
