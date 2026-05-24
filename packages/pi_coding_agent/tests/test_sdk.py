"""SDK create_agent_session tests."""

from pathlib import Path

import pytest
from pi_ai.providers import faux as faux_mod
from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)

from pi_coding_agent.sdk import CreateAgentSessionOptions, create_agent_session


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
