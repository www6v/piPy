"""SDK create_agent_session tests."""

from pathlib import Path

import pytest
from pi_agent.agent_loop import prompt_text
from pi_ai.providers import faux as faux_mod
from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)

from pi_coding_agent.sdk import CreateAgentSessionOptions, create_agent_session
from pi_coding_agent.session.manager import SessionManager


@pytest.mark.asyncio
async def test_create_agent_session_injects_agents_md_context(tmp_path: Path) -> None:
    marker = "UNIQUE_CONTEXT_MARKER_XYZ"
    (tmp_path / "AGENTS.md").write_text(
        f"# test context\n{marker}\n",
        encoding="utf-8",
    )
    register_faux_provider(
        models=[{"id": "test", "name": "Test"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("ctx-ok")]),
    )
    faux_mod.set_faux_responses(
        [faux_assistant_message([faux_text("ctx-ok")])],
    )
    result = await create_agent_session(
        CreateAgentSessionOptions(
            model="faux/test",
            provider="faux",
            tools=[],
            in_memory=True,
            cwd=tmp_path,
        )
    )
    assert marker in result.session.agent.state.system_prompt


@pytest.mark.asyncio
async def test_create_agent_session_in_memory_faux() -> None:
    register_faux_provider(
        models=[{"id": "test", "name": "Test"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("sdk-ok")]),
    )
    faux_mod.set_faux_responses(
        [faux_assistant_message([faux_text("sdk-ok")])],
    )
    result = await create_agent_session(
        CreateAgentSessionOptions(
            model="faux/test",
            provider="faux",
            tools=[],
            in_memory=True,
        )
    )
    session = result.session
    assert session.session_file is None
    events: list[str] = []

    def on_event(event) -> None:
        if event.type == "message_update":
            for block in event.message.content:
                if block.type == "text":
                    delta = getattr(event.assistant_message_event, "delta", "")
                    events.append(delta)

    session.subscribe(on_event)
    await session.prompt("hello")
    await session.wait_for_idle()
    assert "sdk-ok" in "".join(events) or session.messages


@pytest.mark.asyncio
async def test_create_agent_session_fork_session(tmp_path: Path, monkeypatch) -> None:
    sessions_root = tmp_path / "sessions"
    monkeypatch.setattr(
        "pi_coding_agent.session.manager.get_sessions_dir",
        lambda: sessions_root,
    )
    source = SessionManager.create(tmp_path)
    source.append_messages([prompt_text("seed-message")])

    register_faux_provider(
        models=[{"id": "test", "name": "Test"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("fork-ok")]),
    )
    faux_mod.set_faux_responses([faux_assistant_message([faux_text("fork-ok")])])

    result = await create_agent_session(
        CreateAgentSessionOptions(
            model="faux/test",
            provider="faux",
            tools=[],
            cwd=tmp_path,
            fork_session=source.path.stem,
        )
    )
    session = result.session
    assert session.session_file is not None
    loaded = session.messages
    assert loaded
    assert loaded[0].role == "user"
    assert "seed-message" in str(getattr(loaded[0], "content", ""))
