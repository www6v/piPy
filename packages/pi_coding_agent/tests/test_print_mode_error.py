import pytest

from pi_coding_agent.auth.storage import AuthStorage
from pi_coding_agent.print_mode import PrintModeOptions, run_print_mode


@pytest.mark.asyncio
async def test_print_mode_surfaces_missing_api_key(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sessions_root = tmp_path / "agent-sessions"
    monkeypatch.setattr(
        "pi_coding_agent.session.manager.get_sessions_dir",
        lambda: sessions_root,
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_OAUTH_TOKEN", raising=False)
    monkeypatch.setattr(
        "pi_coding_agent.auth.resolve.get_auth_storage",
        lambda: AuthStorage(tmp_path / "missing-auth.json"),
    )
    code = await run_print_mode(
        PrintModeOptions(
            prompt="hello",
            model="anthropic/claude-sonnet-4-5",
            system_prompt="",
            tools=[],
            api_key=None,
            provider=None,
        )
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "Error:" in captured.err
    assert "ANTHROPIC_API_KEY" in captured.err
