"""Tests for system prompt construction."""

from __future__ import annotations

from pathlib import Path

from pi_coding_agent.context.loader import ContextFile
from pi_coding_agent.context.system_prompt import build_system_prompt


def test_build_system_prompt_includes_project_instructions_and_path_attr(
    tmp_path: Path,
) -> None:
    ctx_path = tmp_path / "AGENTS.md"
    ctx_path.write_text("Be kind to tests.", encoding="utf-8")
    contexts = [
        ContextFile(path=str(ctx_path), content="Be kind to tests."),
    ]
    out = build_system_prompt(
        cwd=tmp_path,
        tools=[],
        context_files=contexts,
    )
    assert "<project_instructions " in out
    assert 'path="' in out
    assert str(ctx_path).replace("\\", "/") in out.replace("\\", "/")
    assert "Be kind to tests." in out
    assert "<project_context>" in out


def test_build_system_prompt_custom_base_appends_context(
    tmp_path: Path,
) -> None:
    ctx = ContextFile(path="/tmp/CLAUDE.md", content="rules")
    out = build_system_prompt(
        cwd=tmp_path,
        tools=["read"],
        context_files=[ctx],
        custom_prompt="CUSTOM ONLY",
        append_sections=["extra"],
    )
    assert out.startswith("CUSTOM ONLY")
    assert "\nextra\n" in out or "extra" in out
    assert "<project_instructions path=\"/tmp/CLAUDE.md\">" in out
    assert "Current working directory:" in out
