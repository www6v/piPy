import pytest

from pi_ai.providers import faux as faux_mod
from pi_ai.providers.faux import faux_assistant_message, faux_text, register_faux_provider
from pi_coding_agent.print_mode import PrintModeOptions, run_print_mode


@pytest.mark.asyncio
async def test_continue_session_keeps_context(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sessions_root = tmp_path / "agent-sessions"
    monkeypatch.setattr(
        "pi_coding_agent.session.manager.get_sessions_dir",
        lambda: sessions_root,
    )
    register_faux_provider(models=[{"id": "test", "name": "Test"}])
    faux_mod.set_faux_responses(
        [
            faux_assistant_message([faux_text("remember ALPHA")]),
            faux_assistant_message([faux_text("ALPHA was the codename")]),
        ]
    )
    await run_print_mode(
        PrintModeOptions(
            prompt="remember codename ALPHA",
            model="faux/test",
            system_prompt="sys",
            tools=[],
            api_key=None,
            provider="faux",
        )
    )
    code = await run_print_mode(
        PrintModeOptions(
            prompt="what codename",
            model="faux/test",
            system_prompt="sys",
            tools=[],
            api_key=None,
            provider="faux",
            continue_session=True,
        )
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "ALPHA" in captured.out
