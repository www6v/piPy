"""Extension hook ensures analysis.md before agent start."""

from __future__ import annotations

from pathlib import Path

import pytest
from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_coding_agent import CreateAgentSessionOptions, create_agent_session

from slide_deck_bootstrap import EXTEND_MD, ensure_content_md, ensure_extend_md

GUARD_EXTENSION = Path(__file__).resolve().parent.parent / "extensions" / "slide_deck_guard.py"
FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "slide-deck-brief.md"


@pytest.mark.asyncio
async def test_guard_extension_writes_analysis_on_prompt(tmp_path: Path) -> None:
    registration = register_faux_provider(
        models=[{"id": "guard", "name": "guard"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("ok")]),
    )
    try:
        ensure_extend_md(tmp_path)
        extend = tmp_path / ".baoyu-skills" / "baoyu-slide-deck" / "EXTEND.md"
        extend.write_text(EXTEND_MD, encoding="utf-8")
        ensure_content_md(tmp_path, FIXTURE)
        result = await create_agent_session(
            CreateAgentSessionOptions(
                cwd=tmp_path,
                model="faux/guard",
                provider="faux",
                in_memory=True,
                tools=["read", "write"],
                extension_paths=[str(GUARD_EXTENSION)],
                no_skills=True,
            )
        )
        session = result.session
        await session.prompt(
            "/skill:baoyu-slide-deck content.md --outline-only --slides 6 --lang zh"
        )
        await session.wait_for_idle()
        deck_dirs = list((tmp_path / "slide-deck").iterdir())
        assert deck_dirs
        analysis = deck_dirs[0] / "analysis.md"
        assert analysis.is_file()
        assert "step_2_complete: true" in analysis.read_text(encoding="utf-8")
    finally:
        registration.dispose()
