"""Message conversion helpers."""

from __future__ import annotations

from pi_agent.types import AgentMessage
from pi_ai.types import Message


def convert_to_llm(messages: list[AgentMessage]) -> list[Message]:
    out: list[Message] = []
    for message in messages:
        if message.role in ("user", "assistant", "toolResult"):
            out.append(message)  # type: ignore[arg-type]
    return out
