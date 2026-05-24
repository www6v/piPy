"""Tests for ls tool."""

import pytest

from pi_coding_agent.tools.ls import create_ls_tool


@pytest.mark.asyncio
async def test_ls_lists_directory(tmp_path) -> None:
    (tmp_path / "alpha.txt").write_text("a", encoding="utf-8")
    (tmp_path / "subdir").mkdir()
    tool = create_ls_tool(str(tmp_path))
    result = await tool.execute("call-1", {"path": "."})
    assert not result.is_error
    text = result.content[0].text
    assert "alpha.txt" in text
    assert "subdir/" in text
