"""Tests for settings loader."""

import json
from pathlib import Path

from pi_coding_agent.settings import load_settings


def test_load_settings_merges_project_over_global(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "settings.json").write_text(
        json.dumps({"defaultModel": "global-model"}),
        encoding="utf-8",
    )
    project_pi = tmp_path / "proj" / ".pi"
    project_pi.mkdir(parents=True)
    (project_pi / "settings.json").write_text(
        json.dumps({"defaultModel": "project-model"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "pi_coding_agent.settings.get_agent_dir",
        lambda: agent_dir,
    )
    settings = load_settings(tmp_path / "proj")
    assert settings.default_model == "project-model"


def test_project_overrides_global_compaction_reserve_tokens(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "settings.json").write_text(
        json.dumps(
            {
                "compaction": {
                    "reserveTokens": 16384,
                },
            },
        ),
        encoding="utf-8",
    )
    project_pi = tmp_path / "proj" / ".pi"
    project_pi.mkdir(parents=True)
    (project_pi / "settings.json").write_text(
        json.dumps(
            {
                "compaction": {
                    "reserveTokens": 8192,
                },
            },
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "pi_coding_agent.settings.get_agent_dir",
        lambda: agent_dir,
    )
    settings = load_settings(tmp_path / "proj")
    assert settings.compaction.reserve_tokens == 8192
