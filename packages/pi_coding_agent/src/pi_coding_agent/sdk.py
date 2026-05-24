"""Public SDK (pi: createAgentSession)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pi_ai.config_paths import get_agent_dir
from pi_ai.model_registry import ModelRegistry, get_registry
from pi_ai.types import Model

from pi_coding_agent.agent_session import (
    AgentSession,
    InMemorySessionBackend,
    SessionBackend,
    _ensure_faux_model,
    _read_session_id,
)
from pi_coding_agent.auth.resolve import resolve_auth_for_model
from pi_coding_agent.context.loader import (
    ContextFile,
    load_project_context_files,
    load_system_prompt_files,
)
from pi_coding_agent.context.system_prompt import build_system_prompt
from pi_coding_agent.defaults import DEFAULT_SYSTEM
from pi_coding_agent.model_resolver import resolve_model_reference
from pi_coding_agent.session.manager import SessionManager
from pi_coding_agent.settings import load_settings


@dataclass
class CreateAgentSessionOptions:
    cwd: str | Path | None = None
    model: str | Model | None = None
    tools: list[str] | None = None
    system_prompt: str | None = None
    system_prompt_is_final: bool = False
    no_context_files: bool = False
    api_key: str | None = None
    provider: str | None = None
    thinking_level: str | None = None
    session_manager: SessionManager | None = None
    in_memory: bool = False
    continue_session: bool = False
    session_path: str | None = None
    fork_session: str | None = None
    model_registry: ModelRegistry | None = None


@dataclass
class CreateAgentSessionResult:
    session: AgentSession
    warning: str | None = None


def _resolve_backend(
    cwd: Path,
    options: CreateAgentSessionOptions,
) -> SessionBackend:
    if options.in_memory:
        return InMemorySessionBackend()
    if options.session_manager is not None:
        manager = options.session_manager
        return SessionBackend(
            manager=manager,
            session_id=_read_session_id(manager.path),
            session_file=str(manager.path),
        )
    if options.session_path:
        manager = SessionManager.open(options.session_path)
        return SessionBackend(
            manager=manager,
            session_id=_read_session_id(manager.path),
            session_file=str(manager.path),
        )
    if options.fork_session:
        source = SessionManager.resolve_session_reference(cwd, options.fork_session)
        if source is None:
            msg = f"Unable to resolve fork session: {options.fork_session}"
            raise ValueError(msg)
        manager = SessionManager.fork_from(source, cwd)
        return SessionBackend(
            manager=manager,
            session_id=_read_session_id(manager.path),
            session_file=str(manager.path),
        )
    if options.continue_session:
        existing = SessionManager.latest_for_cwd(cwd)
        if existing is not None:
            return SessionBackend(
                manager=existing,
                session_id=_read_session_id(existing.path),
                session_file=str(existing.path),
            )
    manager = SessionManager.create(cwd)
    return SessionBackend(
        manager=manager,
        session_id=_read_session_id(manager.path),
        session_file=str(manager.path),
    )


def _resolve_system_prompt_for_session(
    *,
    cwd: Path,
    tools: list[str],
    opts: CreateAgentSessionOptions,
) -> str:
    if opts.system_prompt is not None and opts.system_prompt_is_final:
        return opts.system_prompt

    agent_dir = get_agent_dir()
    system_replace, append_list = load_system_prompt_files(cwd, agent_dir)
    explicit_user_system = opts.system_prompt is not None

    context_files_seq: list[ContextFile]
    if opts.no_context_files:
        context_files_seq = []
    else:
        context_files_seq = load_project_context_files(cwd, agent_dir)

    custom_prompt = opts.system_prompt if explicit_user_system else system_replace

    return build_system_prompt(
        cwd=cwd,
        tools=tools,
        context_files=context_files_seq,
        custom_prompt=custom_prompt,
        append_sections=append_list,
    )


def _precreate_unknown_faux_model(pattern: str, provider_override: str | None) -> None:
    """Register dynamic faux model ids before resolver calls ``get_model``."""

    trimmed = pattern.strip()
    if "/" in trimmed:
        maybe_provider, _, maybe_id = trimmed.partition("/")
        provider = maybe_provider.strip()
        model_id = maybe_id.strip()
    else:
        pov = provider_override.strip() if provider_override else ""
        provider, model_id = pov, trimmed
    if provider != "faux" or not model_id:
        return
    _ensure_faux_model(model_id)


async def create_agent_session(
    options: CreateAgentSessionOptions | None = None,
) -> CreateAgentSessionResult:
    """Create an agent session for programmatic use (pi: createAgentSession)."""
    opts = options or CreateAgentSessionOptions()
    cwd = Path(opts.cwd or os.getcwd()).resolve()
    registry = opts.model_registry or get_registry()
    settings = load_settings(cwd)

    model_pattern = opts.model
    if model_pattern is None:
        if settings.default_model:
            provider = settings.default_provider
            if provider and "/" not in settings.default_model:
                model_pattern = f"{provider}/{settings.default_model}"
            else:
                model_pattern = settings.default_model
        else:
            model_pattern = "anthropic/claude-sonnet-4-5"

    if isinstance(model_pattern, Model):
        resolved_model = model_pattern
        thinking = opts.thinking_level or settings.default_thinking_level
        warning = None
    else:
        _precreate_unknown_faux_model(
            str(model_pattern),
            opts.provider,
        )
        resolved = resolve_model_reference(
            str(model_pattern),
            registry,
            provider_override=opts.provider,
        )
        thinking = opts.thinking_level or resolved.thinking_level
        if thinking is None:
            thinking = settings.default_thinking_level
        resolved_model = resolved.model
        warning = resolved.warning

    if resolved_model.provider == "faux":
        _ensure_faux_model(resolved_model.id)

    api_key, request_headers = resolve_auth_for_model(
        registry,
        resolved_model,
        api_key_override=opts.api_key,
    )
    tools = opts.tools if opts.tools is not None else ["read", "bash"]
    backend = _resolve_backend(cwd, opts)
    resolved_system_prompt = _resolve_system_prompt_for_session(
        cwd=cwd,
        tools=tools,
        opts=opts,
    )
    session = AgentSession.build(
        cwd=cwd,
        model=resolved_model,
        tools=tools,
        system_prompt=resolved_system_prompt or DEFAULT_SYSTEM,
        thinking_level=thinking,
        backend=backend,
        registry=registry,
        api_key=api_key,
        request_headers=request_headers,
        provider_override=opts.provider,
        settings=settings,
    )
    return CreateAgentSessionResult(session=session, warning=warning)
