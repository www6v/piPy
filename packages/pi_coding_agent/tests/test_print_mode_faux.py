import pytest

from pi_ai.providers.faux import faux_assistant_message, faux_text, register_faux_provider
from pi_coding_agent.print_mode import PrintModeOptions, run_print_mode


@pytest.mark.asyncio
async def test_print_mode_faux(capsys):
    reg = register_faux_provider(
        models=[{"id": "test", "name": "Test"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("final-answer")]),
    )
    code = await run_print_mode(
        PrintModeOptions(
            prompt="say ok",
            model="faux/test",
            system_prompt="sys",
            tools=[],
            api_key=None,
            provider="faux",
        )
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "final-answer" in captured.out
    reg.dispose()
