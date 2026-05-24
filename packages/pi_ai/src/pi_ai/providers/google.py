"""Google Gemini GenerateContent provider (pi: google subset)."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
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
)


def _messages_for_api(context: Context) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    if context.system_prompt:
        payload.append(
            {
                "role": "user",
                "parts": [{"text": context.system_prompt}],
            }
        )
    for message in context.messages:
        if message.role == "user":
            text = (
                message.content
                if isinstance(message.content, str)
                else "\n".join(block.text for block in message.content)
            )
            payload.append({"role": "user", "parts": [{"text": text}]})
            continue
        if message.role == "assistant":
            parts: list[dict[str, Any]] = []
            for block in message.content:
                if block.type == "text":
                    parts.append({"text": block.text})
                elif block.type == "toolCall":
                    parts.append(
                        {
                            "functionCall": {
                                "name": block.name,
                                "args": dict(block.arguments),
                            }
                        }
                    )
            if parts:
                payload.append({"role": "model", "parts": parts})
            continue
        text = "\n".join(block.text for block in message.content)
        payload.append(
            {
                "role": "user",
                "parts": [{"text": text}],
            }
        )
    return payload


def _extract_candidate_parts(
    data: dict[str, Any],
) -> tuple[str, list[ToolCall]]:
    candidates = data.get("candidates") or []
    if not candidates:
        return "", []
    first = candidates[0] or {}
    content = first.get("content") or {}
    parts = content.get("parts") or []
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str) and text:
            text_parts.append(text)
        function_call = part.get("functionCall")
        if isinstance(function_call, dict):
            tool_calls.append(
                ToolCall(
                    id="",
                    name=str(function_call.get("name") or ""),
                    arguments=dict(function_call.get("args") or {}),
                )
            )
    return "".join(text_parts), tool_calls


async def stream_google(
    model: Model,
    context: Context,
    *,
    api_key: str | None = None,
    request_headers: dict[str, str] | None = None,
    thinking_level: str | None = None,
    signal: Any = None,
    client: httpx.AsyncClient | None = None,
) -> AsyncIterator[StreamEvent]:
    del thinking_level
    key = api_key or get_env_api_key(model.provider)
    env_hint = (find_env_keys(model.provider) or ["GEMINI_API_KEY"])[0]
    if not key:
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

    partial = AssistantMessage(
        content=[],
        api=model.api,
        provider=model.provider,
        model=model.id,
        usage=Usage(),
        stop_reason="stop",
        timestamp=int(time.time() * 1000),
    )
    yield StreamStartEvent(partial=partial)

    body: dict[str, Any] = {"contents": _messages_for_api(context)}
    if context.tools:
        body["tools"] = [
            {
                "functionDeclarations": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    }
                ]
            }
            for tool in context.tools
        ]
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if request_headers:
        headers.update(request_headers)
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=120.0)
    try:
        if signal is not None and getattr(signal, "is_set", lambda: False)():
            partial.stop_reason = "aborted"
            partial.error_message = "aborted"
            yield StreamDoneEvent(message=partial)
            return
        url = (
            f"{model.base_url.rstrip('/')}/v1beta/models/{model.id}:generateContent"
            f"?key={key}"
        )
        response = await http.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
        text, tool_calls = _extract_candidate_parts(data)
        if text:
            partial.content.append(TextContent(text=text))
            yield TextDeltaEvent(delta=text, partial=partial)
        for call in tool_calls:
            partial.content.append(call)
        if tool_calls:
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
