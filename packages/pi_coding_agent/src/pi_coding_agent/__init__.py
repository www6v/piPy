"""Coding agent for piPy — CLI, SDK, and RPC."""

from pi_coding_agent.agent_session import AgentSession, InMemorySessionBackend
from pi_coding_agent.auth.storage import AuthStorage
from pi_coding_agent.sdk import (
    CreateAgentSessionOptions,
    CreateAgentSessionResult,
    create_agent_session,
)
from pi_coding_agent.session.manager import SessionManager
from pi_ai.model_registry import ModelRegistry, get_registry

__version__ = "0.0.1"

__all__ = [
    "AgentSession",
    "AuthStorage",
    "CreateAgentSessionOptions",
    "CreateAgentSessionResult",
    "InMemorySessionBackend",
    "ModelRegistry",
    "SessionManager",
    "create_agent_session",
    "get_registry",
]
