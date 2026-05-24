"""Tests for context file discovery and merge ordering."""

from __future__ import annotations

from pathlib import Path

from pi_coding_agent.context.loader import (
    ContextFile,
    load_project_context_files,
    load_system_prompt_files,
)


def test_load_project_context_files_order_global_then_ancestors(tmp_path: Path) -> None:
    agent = tmp_path / "agent"
    agent.mkdir()

    proj = tmp_path / "project"
    root = proj
    mid = proj / "mid"
    leaf = mid / "leaf"
    leaf.mkdir(parents=True)

    (agent / "AGENTS.md").write_text("global-agent", encoding="utf-8")
    (root / "AGENTS.md").write_text("root-proj", encoding="utf-8")
    (mid / "AGENTS.md").write_text("mid-proj", encoding="utf-8")
    (leaf / "AGENTS.md").write_text("leaf-proj", encoding="utf-8")

    files = load_project_context_files(cwd=leaf, agent_dir=agent)
    texts = [f.content for f in files]

    assert texts == ["global-agent", "root-proj", "mid-proj", "leaf-proj"]


def test_load_project_context_files_dedupes_same_path(tmp_path: Path) -> None:
    """If cwd equals agent_dir, global file must not appear twice."""
    agent = tmp_path / "same"
    agent.mkdir()
    (agent / "CLAUDE.md").write_text("once", encoding="utf-8")

    files = load_project_context_files(cwd=agent, agent_dir=agent)
    assert len(files) == 1
    assert files[0] == ContextFile(path=str(agent / "CLAUDE.md"), content="once")


def test_load_system_prompt_files_project_overrides_global(tmp_path: Path) -> (
    None
):
    agent = tmp_path / "agent"
    agent.mkdir()
    cwd = tmp_path / "proj"
    pi = cwd / ".pi"
    pi.mkdir(parents=True)

    (agent / "SYSTEM.md").write_text("global-system", encoding="utf-8")
    (pi / "SYSTEM.md").write_text("project-system", encoding="utf-8")

    system, appends = load_system_prompt_files(cwd=cwd, agent_dir=agent)
    assert system == "project-system"
    assert appends == []


def test_load_system_prompt_files_append_both_locations(tmp_path: Path) -> None:
    agent = tmp_path / "agent"
    agent.mkdir()
    cwd = tmp_path / "proj"
    pi = cwd / ".pi"
    pi.mkdir(parents=True)

    (agent / "APPEND_SYSTEM.md").write_text("A", encoding="utf-8")
    (pi / "APPEND_SYSTEM.md").write_text("B", encoding="utf-8")

    system, appends = load_system_prompt_files(cwd=cwd, agent_dir=agent)
    assert system is None
    assert appends == ["A", "B"]
