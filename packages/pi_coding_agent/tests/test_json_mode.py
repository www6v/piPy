import json

import pytest

from pi_ai.providers import faux as faux_mod
from pi_ai.providers.faux import faux_assistant_message, faux_text, register_faux_provider
from pi_coding_agent.modes.json_mode import agent_event_to_dict
from pi_coding_agent.print_mode import PrintModeOptions, run_print_mode
from pi_agent.types import AgentStartEvent


def test_agent_event_to_dict():
    payload = agent_event_to_dict(AgentStartEvent())
    assert payload == {"type": "agent_start"}


@pytest.mark.asyncio
async def test_json_mode_stdout(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sessions_root = tmp_path / "agent-sessions"
    monkeypatch.setattr(
        "pi_coding_agent.session.manager.get_sessions_dir",
        lambda: sessions_root,
    )
    register_faux_provider(models=[{"id": "test", "name": "Test"}])
    faux_mod.set_faux_responses(
        [faux_assistant_message([faux_text("json-ok")])],
    )
    code = await run_print_mode(
        PrintModeOptions(
            prompt="hi",
            model="faux/test",
            system_prompt="",
            tools=[],
            api_key=None,
            provider="faux",
            mode="json",
        )
    )
    captured = capsys.readouterr()
    assert code == 0
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert lines
    first = json.loads(lines[0])
    assert first["type"] == "session"
    types = {json.loads(line)["type"] for line in lines[1:]}
    assert "agent_start" in types
    assert "agent_end" in types
