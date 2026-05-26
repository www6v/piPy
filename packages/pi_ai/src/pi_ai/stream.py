"""Streaming helpers for pi-ai."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from pi_ai.providers import faux as faux_provider
from pi_ai.providers.amazon_bedrock import stream_amazon_bedrock
from pi_ai.providers.anthropic import stream_anthropic
from pi_ai.providers.azure_openai_responses import stream_azure_openai_responses
from pi_ai.providers.google import stream_google
from pi_ai.providers.openai import stream_openai
from pi_ai.types import (
    AssistantMessage,
    Context,
    Model,
    StreamDoneEvent,
    StreamEvent,
    StreamStartEvent,
    TextDeltaEvent,
)


@dataclass
class AssistantMessageStream:
    """Async stream of assistant events with a final result."""

    _events: AsyncIterator[StreamEvent]
    _result: AssistantMessage | None = None

    def __aiter__(self) -> AsyncIterator[StreamEvent]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[StreamEvent]:
        async for event in self._events:
            if event.type == "done":
                self._result = event.message
            yield event

    async def result(self) -> AssistantMessage:
        if self._result is not None:
            return self._result
        async for event in self._events:
            if event.type == "done":
                self._result = event.message
                return event.message
        raise RuntimeError("Stream ended without done event")


async def _faux_events(
    model: Model,
    context: Context,
) -> AsyncIterator[StreamEvent]:
    message = faux_provider.next_faux_response(context)
    message.api = model.api
    message.provider = model.provider
    message.model = model.id
    partial = AssistantMessage(
        content=[],
        api=model.api,
        provider=model.provider,
        model=model.id,
        usage=message.usage,
        stop_reason=message.stop_reason,
        timestamp=message.timestamp,
        error_message=message.error_message,
    )
    yield StreamStartEvent(partial=partial)
    text = "".join(
        block.text for block in message.content if block.type == "text"
    )
    if text:
        partial.content = [faux_provider.faux_text("")]
        for char in text:
            partial.content[0].text += char
            yield TextDeltaEvent(delta=char, partial=partial)
    tool_blocks = [b for b in message.content if b.type == "toolCall"]
    if tool_blocks:
        partial.content = list(message.content)
        partial.stop_reason = message.stop_reason
    else:
        partial.content = list(message.content)
        partial.stop_reason = message.stop_reason
    yield StreamDoneEvent(message=partial)


def stream_simple(
    model: Model,
    context: Context,
    *,
    tools: list[Any] | None = None,
    api_key: str | None = None,
    request_headers: dict[str, str] | None = None,
    thinking_level: str | None = None,
    signal: Any = None,
    client: Any = None,
) -> AssistantMessageStream:
    ctx = Context(
        system_prompt=context.system_prompt,
        messages=list(context.messages),
        tools=tools if tools is not None else context.tools,
    )
    if model.provider == "faux":
        return AssistantMessageStream(_events=_faux_events(model, ctx))
    if model.api == "openai-completions":
        return AssistantMessageStream(
            _events=stream_openai(
                model,
                ctx,
                api_key=api_key,
                request_headers=request_headers,
                thinking_level=thinking_level,
                signal=signal,
                client=client,
            )
        )
    if model.api == "anthropic-messages":
        return AssistantMessageStream(
            _events=stream_anthropic(
                model,
                ctx,
                api_key=api_key,
                request_headers=request_headers,
                thinking_level=thinking_level,
                signal=signal,
                client=client,
            )
        )
    if model.api == "google-generate-content":
        return AssistantMessageStream(
            _events=stream_google(
                model,
                ctx,
                api_key=api_key,
                request_headers=request_headers,
                thinking_level=thinking_level,
                signal=signal,
                client=client,
            )
        )
    if model.api == "azure-openai-responses":
        return AssistantMessageStream(
            _events=stream_azure_openai_responses(
                model,
                ctx,
                api_key=api_key,
                request_headers=request_headers,
                thinking_level=thinking_level,
                signal=signal,
                client=client,
            )
        )
    if model.api == "amazon-bedrock":
        return AssistantMessageStream(
            _events=stream_amazon_bedrock(
                model,
                ctx,
                api_key=api_key,
                request_headers=request_headers,
                thinking_level=thinking_level,
                signal=signal,
                client=client,
            )
        )
    raise ValueError(
        f"Unsupported API {model.api!r} for provider {model.provider!r}"
    )


async def complete_simple(
    model: Model,
    context: Context,
    *,
    tools: list[Any] | None = None,
    api_key: str | None = None,
    request_headers: dict[str, str] | None = None,
    thinking_level: str | None = None,
    signal: Any = None,
    client: Any = None,
) -> AssistantMessage:
    """Consume a non-streaming completion via stream_simple."""

    stream = stream_simple(
        model,
        context,
        tools=tools,
        api_key=api_key,
        request_headers=request_headers,
        thinking_level=thinking_level,
        signal=signal,
        client=client,
    )
    return await stream.result()
