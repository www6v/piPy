import asyncio

import pytest

from pi_coding_agent.tools.bash import create_bash_tool


@pytest.mark.asyncio
async def test_bash_echo(tmp_path):
    tool = create_bash_tool(str(tmp_path))
    result = await tool.execute("tc1", {"command": "echo hello"})
    assert "hello" in result.content[0].text


@pytest.mark.asyncio
async def test_bash_nonzero_exit_is_error(tmp_path):
    tool = create_bash_tool(str(tmp_path))
    with pytest.raises(Exception, match="exited"):
        await tool.execute("tc2", {"command": "exit 1"})


@pytest.mark.asyncio
async def test_bash_timeout(tmp_path):
    tool = create_bash_tool(str(tmp_path))
    with pytest.raises(Exception, match="timed out"):
        await tool.execute(
            "tc3",
            {"command": "sleep 2", "timeout": 0.1},
        )


@pytest.mark.asyncio
async def test_bash_abort(tmp_path):
    tool = create_bash_tool(str(tmp_path))
    abort = asyncio.Event()

    async def trigger_abort() -> None:
        await asyncio.sleep(0.1)
        abort.set()

    asyncio.create_task(trigger_abort())
    with pytest.raises(Exception, match="aborted"):
        await tool.execute(
            "tc4",
            {"command": "sleep 5"},
            signal=abort,
        )
