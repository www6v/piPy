"""Azure OpenAI Responses provider adapter (minimal parity placeholder)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from pi_ai.types import (
    AssistantMessage,
    Context,
    Model,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamEvent,
    StreamStartEvent,
    Usage,
)

_PLACEHOLDER_ERROR = (
    "azure-openai-responses runtime is not implemented yet. "
    "Use models.json to map Azure deployments to openai-completions "
    "for runtime requests."
)


async def stream_azure_openai_responses(
    model: Model,
    context: Context,
    *,
    api_key: str | None = None,
    request_headers: dict[str, str] | None = None,
    thinking_level: str | None = None,
    signal: Any = None,
    client: Any = None,
) -> AsyncIterator[StreamEvent]:
    """Emit explicit placeholder events while keeping stream API contract."""
    del context, api_key, request_headers, thinking_level, client

    partial = AssistantMessage(
        content=[],
        api=model.api,
        provider=model.provider,
        model=model.id,
        usage=Usage(),
        stop_reason="error",
        error_message=_PLACEHOLDER_ERROR,
        timestamp=int(time.time() * 1000),
    )
    yield StreamStartEvent(partial=partial)
    if signal is not None and getattr(signal, "is_set", lambda: False)():
        partial.stop_reason = "aborted"
        partial.error_message = "aborted"
        yield StreamDoneEvent(message=partial)
        return
    yield StreamErrorEvent(error=_PLACEHOLDER_ERROR, partial=partial)
    yield StreamDoneEvent(message=partial)
