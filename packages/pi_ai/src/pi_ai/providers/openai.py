"""OpenAI Chat Completions streaming provider."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from pi_ai.env_keys import get_openai_api_key
from pi_ai.types import (
    AssistantMessage,
    Context,
    Model,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamEvent,
    StreamStartEvent,
    TextContent,
    TextDeltaEvent,
    ToolCall,
    Usage,
    UsageCost,
)


def _usage_from_response(data: dict[str, Any]) -> Usage:
    usage = data.get("usage") or {}
    return Usage(
        input=int(usage.get("prompt_tokens") or 0),
        output=int(usage.get("completion_tokens") or 0),
        total_tokens=int(usage.get("total_tokens") or 0),
        cost=UsageCost(),
    )


def _messages_for_api(context: Context) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if context.system_prompt:
        out.append({"role": "system", "content": context.system_prompt})
    for message in context.messages:
        if message.role == "user":
            content = (
                message.content
                if isinstance(message.content, str)
                else "\n".join(block.text for block in message.content)
            )
            out.append({"role": "user", "content": content})
        elif message.role == "assistant":
            text_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            for block in message.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "toolCall":
                    tool_calls.append(
                        {
                            "id": block.id,
                            "type": "function",
                            "function": {
                                "name": block.name,
                                "arguments": json.dumps(block.arguments),
                            },
                        }
                    )
            entry: dict[str, Any] = {"role": "assistant"}
            if text_parts:
                entry["content"] = "\n".join(text_parts)
            if tool_calls:
                entry["tool_calls"] = tool_calls
            out.append(entry)
        elif message.role == "toolResult":
            text = "\n".join(block.text for block in message.content)
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "content": text,
                }
            )
    return out


def parse_sse_chunk(line: str) -> dict[str, Any] | None:
    if not line.startswith("data: "):
        return None
    payload = line[6:].strip()
    if payload == "[DONE]":
        return {"done": True}
    return json.loads(payload)


def events_from_openai_chunk(
    chunk: dict[str, Any],
    *,
    model: Model,
    partial: AssistantMessage,
) -> tuple[AssistantMessage, list[StreamEvent]]:
    events: list[StreamEvent] = []
    choices = chunk.get("choices") or []
    if not choices:
        return partial, events
    delta = choices[0].get("delta") or {}
    if "content" in delta and delta["content"]:
        text = delta["content"]
        partial.content.append(TextContent(text=text))
        events.append(TextDeltaEvent(delta=text, partial=_clone_assistant(partial)))
    for tool_delta in delta.get("tool_calls") or []:
        index = tool_delta.get("index", 0)
        while len(partial.content) <= index:
            partial.content.append(
                ToolCall(id="", name="", arguments={})
            )
        block = partial.content[index]
        if not isinstance(block, ToolCall):
            continue
        if tool_delta.get("id"):
            block.id = tool_delta["id"]
        function = tool_delta.get("function") or {}
        if function.get("name"):
            block.name = function["name"]
        if function.get("arguments"):
            raw = function["arguments"]
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        block.arguments = parsed
                except json.JSONDecodeError:
                    pass
        events.append(TextDeltaEvent(delta="", partial=_clone_assistant(partial)))
    return partial, events


def _clone_assistant(message: AssistantMessage) -> AssistantMessage:
    content: list[TextContent | ToolCall] = []
    for block in message.content:
        if block.type == "text":
            content.append(TextContent(text=block.text))
        else:
            content.append(
                ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=dict(block.arguments),
                )
            )
    return AssistantMessage(
        content=content,
        api=message.api,
        provider=message.provider,
        model=message.model,
        usage=message.usage,
        stop_reason=message.stop_reason,
        timestamp=message.timestamp,
        error_message=message.error_message,
    )


async def stream_openai(
    model: Model,
    context: Context,
    *,
    api_key: str | None = None,
    signal: Any = None,
    client: httpx.AsyncClient | None = None,
) -> AsyncIterator[StreamEvent]:
    key = api_key or get_openai_api_key()
    if not key:
        partial = AssistantMessage(
            content=[],
            api=model.api,
            provider=model.provider,
            model=model.id,
            usage=Usage(),
            stop_reason="error",
            error_message="OPENAI_API_KEY not set",
        )
        yield StreamErrorEvent(error="OPENAI_API_KEY not set", partial=partial)
        yield StreamDoneEvent(message=partial)
        return

    body: dict[str, Any] = {
        "model": model.id,
        "messages": _messages_for_api(context),
        "stream": True,
    }
    if context.tools:
        body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in context.tools
        ]

    partial = AssistantMessage(
        content=[],
        api=model.api,
        provider=model.provider,
        model=model.id,
        usage=Usage(),
        stop_reason="stop",
        timestamp=int(time.time() * 1000),
    )
    yield StreamStartEvent(partial=_clone_assistant(partial))

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=120.0)
    try:
        async with http.stream(
            "POST",
            f"{model.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=body,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if signal is not None and getattr(signal, "is_set", lambda: False)():
                    partial.stop_reason = "aborted"
                    partial.error_message = "aborted"
                    yield StreamDoneEvent(message=partial)
                    return
                parsed = parse_sse_chunk(line)
                if parsed is None:
                    continue
                if parsed.get("done"):
                    break
                partial, chunk_events = events_from_openai_chunk(
                    parsed, model=model, partial=partial
                )
                for event in chunk_events:
                    yield event
                if choices := parsed.get("choices"):
                    finish = choices[0].get("finish_reason")
                    if finish == "tool_calls":
                        partial.stop_reason = "toolUse"
                    elif finish == "stop":
                        partial.stop_reason = "stop"
                if "usage" in parsed:
                    partial.usage = _usage_from_response(parsed)
        if any(block.type == "toolCall" for block in partial.content):
            partial.stop_reason = "toolUse"
        yield StreamDoneEvent(message=partial)
    except Exception as exc:
        partial.stop_reason = "error"
        partial.error_message = str(exc)
        yield StreamErrorEvent(error=str(exc), partial=partial)
        yield StreamDoneEvent(message=partial)
    finally:
        if owns_client:
            await http.aclose()
