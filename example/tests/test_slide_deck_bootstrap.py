"""Tests for example/slide_deck_bootstrap.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from slide_deck_bootstrap import (
    BootstrapOptions,
    bootstrap_from_prompt,
    derive_topic_slug,
    ensure_analysis_md,
    is_slide_deck_prompt,
    write_needs_analysis_guard,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "slide-deck-brief.md"


def test_derive_topic_slug() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    assert derive_topic_slug(text) == "building-reliable-ai-agents"


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


def test_write_needs_analysis_guard(tmp_path: Path) -> None:
    outline = tmp_path / "slide-deck" / "demo" / "outline.md"
    outline.parent.mkdir(parents=True)
    assert write_needs_analysis_guard(tmp_path, outline)
    other = tmp_path / "readme.md"
    assert not write_needs_analysis_guard(tmp_path, other)
