import pytest

from pi_coding_agent.tools.read import create_read_tool


@pytest.mark.asyncio
async def test_read_file(tmp_path):
    sample = tmp_path / "hello.txt"
    sample.write_text("hello world", encoding="utf-8")
    tool = create_read_tool(str(tmp_path))
    result = await tool.execute("tc1", {"path": "hello.txt"})
    assert "hello world" in result.content[0].text


@pytest.mark.asyncio
async def test_read_rejects_escape(tmp_path):
    tool = create_read_tool(str(tmp_path))
    with pytest.raises(ValueError, match="escapes"):
        await tool.execute("tc2", {"path": "../outside.txt"})
