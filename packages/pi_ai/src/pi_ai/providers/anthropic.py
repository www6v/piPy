"""Anthropic Messages API streaming (pi: anthropic-messages)."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from pi_ai.env_keys import find_env_keys, get_env_api_key
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


@dataclass
class _AnthropicStreamState:
    text_buffer: str = ""
    tool_blocks: dict[int, ToolCall] = field(default_factory=dict)
    tool_args_raw: dict[int, str] = field(default_factory=dict)


def _is_oauth_token(api_key: str) -> bool:
    return "sk-ant-oat" in api_key


def _messages_for_api(context: Context) -> list[dict[str, Any]]:
    params: list[dict[str, Any]] = []
    index = 0
    messages = context.messages
    while index < len(messages):
        message = messages[index]
        if message.role == "user":
            if isinstance(message.content, str):
                params.append({"role": "user", "content": message.content})
            else:
                text = "\n".join(block.text for block in message.content)
                params.append({"role": "user", "content": text})
        elif message.role == "assistant":
            blocks: list[dict[str, Any]] = []
            for block in message.content:
                if block.type == "text" and block.text.strip():
                    blocks.append({"type": "text", "text": block.text})
                elif block.type == "toolCall":
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.arguments or {},
                        }
                    )
            if blocks:
                params.append({"role": "assistant", "content": blocks})
        elif message.role == "toolResult":
            tool_results: list[dict[str, Any]] = []
            while index < len(messages) and messages[index].role == "toolResult":
                result = messages[index]
                text = "\n".join(block.text for block in result.content)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": result.tool_call_id,
                        "content": text,
                        "is_error": result.is_error,
                    }
                )
                index += 1
            params.append({"role": "user", "content": tool_results})
            continue
        index += 1
    return params


def _auth_headers(api_key: str, extra: dict[str, str] | None) -> dict[str, str]:
    headers = {
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    if extra:
        headers.update(extra)
    if _is_oauth_token(api_key):
        headers["authorization"] = f"Bearer {api_key}"
    else:
        headers["x-api-key"] = api_key
    return headers


def _build_content(state: _AnthropicStreamState) -> list[TextContent | ToolCall]:
    content: list[TextContent | ToolCall] = []
    if state.text_buffer:
        content.append(TextContent(text=state.text_buffer))
    for index in sorted(state.tool_blocks):
        content.append(state.tool_blocks[index])
    return content


def _clone_partial(partial: AssistantMessage) -> AssistantMessage:
    return AssistantMessage(
        content=list(partial.content),
        api=partial.api,
        provider=partial.provider,
        model=partial.model,
        usage=partial.usage,
        stop_reason=partial.stop_reason,
        timestamp=partial.timestamp,
        error_message=partial.error_message,
    )


def _apply_event(
    event: dict[str, Any],
    *,
    state: _AnthropicStreamState,
    partial: AssistantMessage,
) -> list[StreamEvent]:
    events: list[StreamEvent] = []
    event_type = event.get("type")
    if event_type == "content_block_delta":
        delta = event.get("delta") or {}
        block_index = int(event.get("index", 0))
        if delta.get("type") == "text_delta":
            text = delta.get("text") or ""
            state.text_buffer += text
            partial.content = _build_content(state)
            events.append(TextDeltaEvent(delta=text, partial=_clone_partial(partial)))
        elif delta.get("type") == "input_json_delta":
            tool = state.tool_blocks.get(block_index)
            if tool is not None:
                merged = state.tool_args_raw.get(block_index, "") + (
                    delta.get("partial_json") or ""
                )
                state.tool_args_raw[block_index] = merged
                try:
                    parsed = json.loads(merged)
                    if isinstance(parsed, dict):
                        tool.arguments = parsed
                except json.JSONDecodeError:
                    pass
    elif event_type == "content_block_start":
        block = event.get("content_block") or {}
        block_index = int(event.get("index", 0))
        if block.get("type") == "tool_use":
            state.tool_blocks[block_index] = ToolCall(
                id=block.get("id") or "",
                name=block.get("name") or "",
                arguments=dict(block.get("input") or {}),
            )
    elif event_type == "message_delta":
        stop = (event.get("delta") or {}).get("stop_reason")
        if stop == "tool_use":
            partial.stop_reason = "toolUse"
        elif stop == "end_turn":
            partial.stop_reason = "stop"
    return events


def parse_anthropic_sse_data(line: str) -> dict[str, Any] | None:
    if not line.startswith("data:"):
        return None
    payload = line[5:].strip()
    if not payload:
        return None
    return json.loads(payload)


async def stream_anthropic(
    model: Model,
    context: Context,
    *,
    api_key: str | None = None,
    request_headers: dict[str, str] | None = None,
    signal: Any = None,
    client: httpx.AsyncClient | None = None,
) -> AsyncIterator[StreamEvent]:
    key = api_key or get_env_api_key(model.provider)
    env_hint = (find_env_keys(model.provider) or ["ANTHROPIC_API_KEY"])[0]
    if not key and not (request_headers and "authorization" in {
        k.lower() for k in request_headers
    }):
        partial = AssistantMessage(
            content=[],
            api=model.api,
            provider=model.provider,
            model=model.id,
            usage=Usage(),
            stop_reason="error",
            error_message=f"{env_hint} not set",
        )
        yield StreamErrorEvent(error=f"{env_hint} not set", partial=partial)
        yield StreamDoneEvent(message=partial)
        return

    body: dict[str, Any] = {
        "model": model.id,
        "max_tokens": model.max_tokens,
        "messages": _messages_for_api(context),
        "stream": True,
    }
    if context.system_prompt:
        body["system"] = context.system_prompt
    if context.tools:
        body["tools"] = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in context.tools
        ]

    stream_state = _AnthropicStreamState()
    partial = AssistantMessage(
        content=[],
        api=model.api,
        provider=model.provider,
        model=model.id,
        usage=Usage(),
        stop_reason="stop",
        timestamp=int(time.time() * 1000),
    )
    yield StreamStartEvent(partial=_clone_partial(partial))

    headers = _auth_headers(key or "", request_headers)
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=120.0)
    url = f"{model.base_url.rstrip('/')}/v1/messages"
    try:
        async with http.stream("POST", url, headers=headers, json=body) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if signal is not None and getattr(signal, "is_set", lambda: False)():
                    partial.stop_reason = "aborted"
                    partial.error_message = "aborted"
                    yield StreamDoneEvent(message=partial)
                    return
                parsed = parse_anthropic_sse_data(line)
                if parsed is None:
                    continue
                for event in _apply_event(
                    parsed,
                    state=stream_state,
                    partial=partial,
                ):
                    yield event
        partial.content = _build_content(stream_state)
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
