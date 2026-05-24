"""AgentSession compaction integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from pi_ai.model_registry import get_registry
from pi_ai.models import get_model
from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_ai.types import AssistantMessage, TextContent, Usage, UserMessage

from pi_coding_agent.agent_session import AgentSession, SessionBackend, _read_session_id
from pi_coding_agent.auth.resolve import resolve_auth_for_model
from pi_coding_agent.session.manager import SessionManager
from pi_coding_agent.settings import Settings


@pytest.mark.asyncio
async def test_agent_session_compact_appends_record_and_emits_events(
    tmp_path: Path,
) -> None:
    """Compaction writes a compaction entry and notifies session listeners."""

    marker = "COMPACTION_SYNTHESIS_MARKER_XYZ789"
    register_faux_provider(
        models=[{"id": "compactor", "name": "Compaction model"}],
        handler=lambda _ctx: faux_assistant_message([faux_text(marker)]),
    )

    manager = SessionManager.create(tmp_path)
    filler = "x" * 200
    blob: list[UserMessage | AssistantMessage] = []
    for turn in range(4):
        blob.append(UserMessage(content=f"{filler} user-{turn} {filler}"))
        blob.append(
            AssistantMessage(
                content=[TextContent(text=f"{filler} reply-{turn} {filler}")],
                api="openai-completions",
                provider="faux",
                model="stub",
                usage=Usage(),
                stop_reason="stop",
            ),
        )
    manager.append_messages(blob)

    registry = get_registry()
    model = get_model("faux", "compactor")
    api_key, request_headers = resolve_auth_for_model(
        registry,
        model,
        api_key_override=None,
    )
    backend = SessionBackend(
        manager=manager,
        session_id=_read_session_id(manager.path),
        session_file=str(manager.path),
    )

    compaction_settings = Settings()
    compaction_settings.compaction.keep_recent_tokens = 220

    session = AgentSession.build(
        cwd=tmp_path,
        model=model,
        tools=["read"],
        system_prompt="test",
        thinking_level=None,
        backend=backend,
        registry=registry,
        api_key=api_key,
        request_headers=request_headers,
        settings=compaction_settings,
    )

    events: list[object] = []

    def on_stream(ev: object) -> None:
        events.append(ev)

    session.subscribe_all(on_stream)
    result = await session.compact()

    entries = manager.load_entries()
    assert any(entry.get("type") == "compaction" for entry in entries)

    assert result.summary == marker
    assert any(e.get("type") == "compaction_start" for e in events if isinstance(e, dict))
    ended = [
        e
        for e in events
        if isinstance(e, dict) and e.get("type") == "compaction_end"
    ]
    assert ended
    assert ended[-1].get("result", {}).get("summary") == marker
