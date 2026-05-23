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
