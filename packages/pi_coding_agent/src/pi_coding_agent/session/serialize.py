"""Serialize AgentMessage for JSONL sessions."""

from __future__ import annotations

from typing import Any

from pi_agent.types import AgentMessage
from pi_ai.types import (
    AssistantMessage,
    Model,
    TextContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)


def model_to_dict(model: Model) -> dict[str, Any]:
    return {
        "id": model.id,
        "name": model.name,
        "api": model.api,
        "provider": model.provider,
        "baseUrl": model.base_url,
        "reasoning": model.reasoning,
        "contextWindow": model.context_window,
        "maxTokens": model.max_tokens,
    }


def message_to_dict(message: AgentMessage) -> dict[str, Any]:
    if message.role == "user":
        content = message.content
        if isinstance(content, str):
            payload: Any = content
        else:
            payload = [{"type": "text", "text": block.text} for block in content]
        return {
            "role": "user",
            "content": payload,
            "timestamp": message.timestamp,
        }
    if message.role == "toolResult":
        return {
            "role": "toolResult",
            "toolCallId": message.tool_call_id,
            "toolName": message.tool_name,
            "content": [{"type": "text", "text": block.text} for block in message.content],
            "isError": message.is_error,
            "timestamp": message.timestamp,
        }
    assert isinstance(message, AssistantMessage)
    blocks: list[dict[str, Any]] = []
    for block in message.content:
        if block.type == "text":
            blocks.append({"type": "text", "text": block.text})
        else:
            blocks.append(
                {
                    "type": "toolCall",
                    "id": block.id,
                    "name": block.name,
                    "arguments": dict(block.arguments),
                }
            )
    return {
        "role": "assistant",
        "content": blocks,
        "api": message.api,
        "provider": message.provider,
        "model": message.model,
        "stopReason": message.stop_reason,
        "timestamp": message.timestamp,
        "errorMessage": message.error_message,
    }


def message_from_dict(data: dict[str, Any]) -> AgentMessage:
    role = data.get("role")
    if role == "user":
        content = data.get("content", "")
        if isinstance(content, list):
            content = [
                TextContent(text=str(item.get("text", "")))
                for item in content
                if item.get("type") == "text"
            ]
        return UserMessage(content=content, timestamp=int(data.get("timestamp") or 0))
    if role == "toolResult":
        content = [
            TextContent(text=str(item.get("text", "")))
            for item in data.get("content") or []
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return ToolResultMessage(
            tool_call_id=str(data.get("toolCallId") or ""),
            tool_name=str(data.get("toolName") or ""),
            content=content,
            is_error=bool(data.get("isError")),
            timestamp=int(data.get("timestamp") or 0),
        )
    from pi_ai.types import Usage

    blocks: list[TextContent | ToolCall] = []
    for item in data.get("content") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            blocks.append(TextContent(text=str(item.get("text", ""))))
        elif item.get("type") == "toolCall":
            blocks.append(
                ToolCall(
                    id=str(item.get("id") or ""),
                    name=str(item.get("name") or ""),
                    arguments=dict(item.get("arguments") or {}),
                )
            )
    return AssistantMessage(
        content=blocks,
        api=str(data.get("api") or ""),
        provider=str(data.get("provider") or ""),
        model=str(data.get("model") or ""),
        usage=Usage(),
        stop_reason=data.get("stopReason") or "stop",
        timestamp=int(data.get("timestamp") or 0),
        error_message=data.get("errorMessage"),
    )
