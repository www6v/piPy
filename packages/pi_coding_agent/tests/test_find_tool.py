"""Tests for find tool."""

import pytest

from pi_coding_agent.tools.find import create_find_tool


@pytest.mark.asyncio
async def test_find_glob_pattern(tmp_path) -> None:
    (tmp_path / "one.py").write_text("x", encoding="utf-8")
    (tmp_path / "two.txt").write_text("y", encoding="utf-8")
    tool = create_find_tool(str(tmp_path))
    result = await tool.execute("call-1", {"pattern": "*.py"})
    assert not result.is_error
    assert "one.py" in result.content[0].text
