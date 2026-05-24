import shutil

import pytest

from pi_coding_agent.tools.grep import create_grep_tool


@pytest.mark.asyncio
async def test_grep_finds_pattern(tmp_path):
    if shutil.which("rg") is None:
        pytest.skip("ripgrep not installed")
    (tmp_path / "a.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    tool = create_grep_tool(str(tmp_path))
    result = await tool.execute("t1", {"pattern": "def foo", "path": "."})
    assert "def foo" in result.content[0].text
