"""Tests for example/slide_deck_bootstrap.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from slide_deck_bootstrap import (
    BootstrapOptions,
    analysis_step2_complete,
    bootstrap_from_prompt,
    build_runbook_appendix,
    derive_topic_slug,
    ensure_analysis_md,
    ensure_image_gen_extend_md,
    is_slide_deck_prompt,
    list_slide_images,
    resolve_topic_dir,
    write_needs_analysis_guard,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "slide-deck-brief.md"


def test_derive_topic_slug() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    assert derive_topic_slug(text) == "a-state-of-the"


def test_resolve_topic_dir_prefers_outline_location(tmp_path: Path) -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    bootstrap = ensure_analysis_md(tmp_path, text, BootstrapOptions(force=True))
    agent_dir = tmp_path / "slide-deck" / "rlvr-text2sql"
    agent_dir.mkdir(parents=True)
    (agent_dir / "outline.md").write_text("# Outline\n", encoding="utf-8")
    (agent_dir / "analysis.md").write_text(
        "## Confirmed Preferences\n",
        encoding="utf-8",
    )
    resolved = resolve_topic_dir(
        tmp_path,
        bootstrap,
        prefer_artifact="outline.md",
    )
    assert resolved == agent_dir


def test_analysis_step2_complete_accepts_skill_format() -> None:
    sdk = "step_2_complete: true\n"
    skill = "## Confirmed Preferences\n- Style: blueprint\n"
    assert analysis_step2_complete(sdk)
    assert analysis_step2_complete(skill)
    assert not analysis_step2_complete("draft only\n")


def test_is_slide_deck_prompt() -> None:
    assert is_slide_deck_prompt("/skill:baoyu-slide-deck content.md --outline-only")
    assert not is_slide_deck_prompt("hello world")


def test_ensure_analysis_md_creates_file(tmp_path: Path) -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    (tmp_path / "content.md").write_text(text, encoding="utf-8")
    bootstrap = ensure_analysis_md(tmp_path, text, BootstrapOptions(force=True))
    assert bootstrap.analysis_path.is_file()
    body = bootstrap.analysis_path.read_text(encoding="utf-8")
    assert "step_2_complete: true" in body
    assert (bootstrap.topic_dir / "source.md").is_file()


def test_bootstrap_from_prompt(tmp_path: Path) -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    (tmp_path / "content.md").write_text(text, encoding="utf-8")
    bootstrap = bootstrap_from_prompt(
        tmp_path,
        "/skill:baoyu-slide-deck content.md --slides 6 --lang zh",
        BootstrapOptions(force=True),
    )
    assert bootstrap is not None
    assert bootstrap.analysis_path.is_file()


def test_list_slide_images(tmp_path: Path) -> None:
    topic = tmp_path / "slide-deck" / "demo"
    topic.mkdir(parents=True)
    (topic / "01-slide-cover.png").write_bytes(b"png")
    (topic / "notes.txt").write_text("skip", encoding="utf-8")
    names = [path.name for path in list_slide_images(topic)]
    assert names == ["01-slide-cover.png"]


def test_build_runbook_appendix_full_pipeline(tmp_path: Path) -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    bootstrap = ensure_analysis_md(tmp_path, text, BootstrapOptions(force=True))
    appendix = build_runbook_appendix(
        bootstrap,
        full_pipeline=True,
        slide_count=3,
    )
    assert "/skill:baoyu-image-gen" in appendix
    assert "Steps 3–9" in appendix


def test_ensure_image_gen_extend_md(tmp_path: Path) -> None:
    ensure_image_gen_extend_md(tmp_path)
    extend = tmp_path / ".baoyu-skills" / "baoyu-image-gen" / "EXTEND.md"
    assert extend.is_file()
    assert "default_provider" in extend.read_text(encoding="utf-8")


def test_write_needs_analysis_guard(tmp_path: Path) -> None:
    outline = tmp_path / "slide-deck" / "demo" / "outline.md"
    outline.parent.mkdir(parents=True)
    assert write_needs_analysis_guard(tmp_path, outline)
    other = tmp_path / "readme.md"
    assert not write_needs_analysis_guard(tmp_path, other)
