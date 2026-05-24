import pytest

from pi_coding_agent.tools.edit import create_edit_tool


@pytest.mark.asyncio
async def test_edit_replaces_text(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text("hello world", encoding="utf-8")
    tool = create_edit_tool(str(tmp_path))
    await tool.execute(
        "t1",
        {"path": "sample.txt", "oldText": "world", "newText": "piPy"},
    )
    assert target.read_text(encoding="utf-8") == "hello piPy"


@pytest.mark.asyncio
async def test_edit_non_unique_raises(tmp_path):
    target = tmp_path / "dup.txt"
    target.write_text("aaa", encoding="utf-8")
    tool = create_edit_tool(str(tmp_path))
    with pytest.raises(Exception, match="not unique"):
        await tool.execute(
            "t2",
            {"path": "dup.txt", "oldText": "a", "newText": "b"},
        )
