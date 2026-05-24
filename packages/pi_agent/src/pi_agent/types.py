"""Types for pi-agent."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pi_ai.stream import AssistantMessageStream
from pi_ai.types import (
    AssistantMessage,
    Message,
    Model,
    TextContent,
    Tool,
    ToolResultMessage,
    UserMessage,
)

AgentMessage = UserMessage | AssistantMessage | ToolResultMessage

ToolExecutionMode = Literal["parallel", "sequential"]


@dataclass
class AgentToolResult:
    content: list[TextContent]
    details: Any = None
    is_error: bool = False
    terminate: bool = False


class AgentTool(Protocol):
    name: str
    description: str
    parameters: dict[str, Any]
    execution_mode: ToolExecutionMode

    async def execute(
        self,
        tool_call_id: str,
        args: dict[str, Any],
        signal: Any = None,
        on_update: Callable[..., None] | None = None,
    ) -> AgentToolResult: ...


@dataclass
class AgentContext:
    system_prompt: str
    messages: list[AgentMessage]
    tools: list[Tool]


@dataclass
class AgentState:
    system_prompt: str
    model: Model
    tools: list[AgentTool]
    messages: list[AgentMessage]
    is_streaming: bool = False


AgentEventType = Literal[
    "agent_start",
    "agent_end",
    "turn_start",
    "turn_end",
    "message_start",
    "message_update",
    "message_end",
    "tool_execution_start",
    "tool_execution_end",
]


@dataclass
class AgentStartEvent:
    type: Literal["agent_start"] = "agent_start"


@dataclass
class AgentEndEvent:
    messages: list[AgentMessage]
    type: Literal["agent_end"] = "agent_end"


@dataclass
class TurnStartEvent:
    type: Literal["turn_start"] = "turn_start"


@dataclass
class TurnEndEvent:
    message: AssistantMessage
    tool_results: list[ToolResultMessage]
    type: Literal["turn_end"] = "turn_end"


@dataclass
class MessageStartEvent:
    message: AgentMessage
    type: Literal["message_start"] = "message_start"


@dataclass
class MessageUpdateEvent:
    message: AssistantMessage
    type: Literal["message_update"] = "message_update"
    assistant_message_event: Any = None


@dataclass
class MessageEndEvent:
    message: AgentMessage
    type: Literal["message_end"] = "message_end"


@dataclass
class ToolExecutionStartEvent:
    tool_call_id: str
    tool_name: str
    args: dict[str, Any]
    type: Literal["tool_execution_start"] = "tool_execution_start"


@dataclass
class ToolExecutionEndEvent:
    tool_call_id: str
    tool_name: str
    result: AgentToolResult
    is_error: bool
    type: Literal["tool_execution_end"] = "tool_execution_end"


AgentEvent = (
    AgentStartEvent
    | AgentEndEvent
    | TurnStartEvent
    | TurnEndEvent
    | MessageStartEvent
    | MessageUpdateEvent
    | MessageEndEvent
    | ToolExecutionStartEvent
    | ToolExecutionEndEvent
)

StreamFn = Callable[..., AssistantMessageStream | Awaitable[AssistantMessageStream]]

ConvertToLlm = Callable[[list[AgentMessage]], list[Message] | Awaitable[list[Message]]]


@dataclass
class AgentLoopConfig:
    model: Model
    convert_to_llm: ConvertToLlm
    api_key: str | None = None
    request_headers: dict[str, str] | None = None
    thinking_level: str | None = None
    tool_execution: ToolExecutionMode = "parallel"
    get_api_key: Callable[[str], str | None | Awaitable[str | None]] | None = None


def user_message(text: str) -> UserMessage:
    return UserMessage(content=text, timestamp=int(time.time() * 1000))
