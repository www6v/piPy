import pytest

from pi_coding_agent.tools.write import create_write_tool


@pytest.mark.asyncio
async def test_write_creates_file(tmp_path):
    tool = create_write_tool(str(tmp_path))
    await tool.execute("t1", {"path": "new.txt", "content": "created"})
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "created"


@pytest.mark.asyncio
async def test_write_overwrites(tmp_path):
    path = tmp_path / "x.txt"
    path.write_text("old", encoding="utf-8")
    tool = create_write_tool(str(tmp_path))
    await tool.execute("t2", {"path": "x.txt", "content": "new"})
    assert path.read_text(encoding="utf-8") == "new"
