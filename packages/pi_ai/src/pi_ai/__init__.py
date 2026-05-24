"""Unified LLM API for piPy."""

from pi_ai.models import get_model
from pi_ai.stream import AssistantMessageStream, complete_simple, stream_simple
from pi_ai.types import (
    AssistantMessage,
    Context,
    Model,
    Tool,
    ToolResultMessage,
    UserMessage,
)

__version__ = "0.0.1"

__all__ = [
    "AssistantMessage",
    "AssistantMessageStream",
    "complete_simple",
    "Context",
    "Model",
    "Tool",
    "ToolResultMessage",
    "UserMessage",
    "get_model",
    "stream_simple",
]
