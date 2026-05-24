"""Pending user-steering and follow-up message queues."""

from __future__ import annotations

from typing import Literal

from pi_agent.types import AgentMessage
from pi_ai.types import TextContent, UserMessage

QueueMode = Literal["all", "one-at-a-time"]


def _message_preview_text(message: AgentMessage) -> str | None:
    """Extract plain text preview for user messages."""
    if not isinstance(message, UserMessage):
        return None
    if isinstance(message.content, str):
        return message.content
    parts: list[str] = []
    for block in message.content:
        if isinstance(block, TextContent):
            parts.append(block.text)
    return "\n".join(parts) if parts else None


class PendingMessageQueue:
    """Buffers agent messages until the agent loop drains them."""

    mode: QueueMode

    def __init__(self, mode: QueueMode = "all") -> None:
        self.mode = mode
        self._items: list[AgentMessage] = []

    def enqueue(self, message: AgentMessage) -> None:
        """Append one message."""
        self._items.append(message)

    def drain(self) -> list[AgentMessage]:
        """Remove and return pending messages respecting ``mode``."""
        if not self._items:
            return []
        if self.mode == "all":
            out = list(self._items)
            self._items.clear()
            return out
        msg = self._items.pop(0)
        return [msg]

    def peek_texts(self) -> list[str]:
        """Return text previews from buffered user messages (no dequeue)."""
        texts: list[str] = []
        for message in self._items:
            preview = _message_preview_text(message)
            if preview is not None:
                texts.append(preview)
        return texts

    def clear(self) -> None:
        """Drop all pending messages."""
        self._items.clear()

    @property
    def has_items(self) -> bool:
        return bool(self._items)

    def __len__(self) -> int:
        """Number of queued messages awaiting drain."""

        return len(self._items)
