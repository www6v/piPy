import pytest

from pi_ai.providers import faux as faux_mod
from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    faux_tool_call,
    register_faux_provider,
)
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


@pytest.mark.asyncio
async def test_print_mode_verbose_logs_agent_events(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sample = tmp_path / "note.txt"
    sample.write_text("verbose-test", encoding="utf-8")

    register_faux_provider(models=[{"id": "test", "name": "Test"}])
    faux_mod.set_faux_responses(
        [
            faux_assistant_message(
                [faux_tool_call("read", {"path": "note.txt"}, tool_id="t1")],
                stop_reason="toolUse",
            ),
            faux_assistant_message([faux_text("done")]),
        ]
    )

    code = await run_print_mode(
        PrintModeOptions(
            prompt="read note",
            model="faux/test",
            system_prompt="sys",
            tools=["read"],
            api_key=None,
            provider="faux",
            verbose=True,
        )
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "done" in captured.out
    err = captured.err
    assert "agent_start" in err
    assert "turn_start" in err
    assert "message_start" in err
    assert "message_end" in err
    assert "tool_execution_start read" in err
    assert "tool_execution_end read" in err
    assert "agent_end" in err
    # Structural events only; no per-character message_update spam
    assert "message_update" not in err
