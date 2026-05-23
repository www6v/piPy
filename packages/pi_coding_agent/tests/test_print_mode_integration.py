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
async def test_print_mode_faux_read_tool(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sample = tmp_path / "data.txt"
    sample.write_text("integration-content", encoding="utf-8")

    register_faux_provider(models=[{"id": "test", "name": "Test"}])
    faux_mod.set_faux_responses(
        [
            faux_assistant_message(
                [faux_tool_call("read", {"path": "data.txt"}, tool_id="t1")],
                stop_reason="toolUse",
            ),
            faux_assistant_message([faux_text("done reading")]),
        ]
    )

    code = await run_print_mode(
        PrintModeOptions(
            prompt="read the file",
            model="faux/test",
            system_prompt="sys",
            tools=["read"],
            api_key=None,
            provider="faux",
        )
    )
    assert code == 0


@pytest.mark.asyncio
async def test_print_mode_faux_bash_tool(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    register_faux_provider(models=[{"id": "test", "name": "Test"}])
    faux_mod.set_faux_responses(
        [
            faux_assistant_message(
                [faux_tool_call("bash", {"command": "echo ok"}, tool_id="t1")],
                stop_reason="toolUse",
            ),
            faux_assistant_message([faux_text("done bash")]),
        ]
    )

    code = await run_print_mode(
        PrintModeOptions(
            prompt="run echo",
            model="faux/test",
            system_prompt="sys",
            tools=["bash"],
            api_key=None,
            provider="faux",
        )
    )
    assert code == 0
