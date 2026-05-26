"""pi_coding_agent extension: ensure analysis.md before baoyu-slide-deck runs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_EXAMPLE_DIR = Path(__file__).resolve().parent.parent
if str(_EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLE_DIR))

from slide_deck_bootstrap import (  # noqa: E402
    BootstrapOptions,
    bootstrap_from_prompt,
    build_runbook_appendix,
    ensure_analysis_md,
    write_needs_analysis_guard,
)

_STATE: dict[str, object] = {"last_bootstrap": None}


def _options_from_env() -> BootstrapOptions:
    return BootstrapOptions(
        lang=os.environ.get("SLIDE_DECK_LANG", "zh"),
        slides=int(os.environ.get("SLIDE_DECK_SLIDES", "6")),
        audience=os.environ.get("SLIDE_DECK_AUDIENCE", "general"),
        style=os.environ.get("SLIDE_DECK_STYLE") or None,
        force=os.environ.get("SLIDE_DECK_FORCE_ANALYSIS", "").lower()
        in {"1", "true", "yes"},
    )


def _resolve_write_path(workspace: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = workspace / path
    return path.resolve()


def register(api) -> None:
    def on_before_agent_start(event, ctx):
        prompt = str(event.get("prompt", ""))
        system_prompt = str(event.get("systemPrompt", ""))
        workspace = Path(ctx.cwd)
        bootstrap = bootstrap_from_prompt(
            workspace,
            prompt,
            _options_from_env(),
        )
        if bootstrap is None:
            return None
        _STATE["last_bootstrap"] = bootstrap
        return {
            "systemPrompt": system_prompt + build_runbook_appendix(bootstrap),
        }

    def on_tool_call(event, ctx):
        if event.get("toolName") != "write":
            return None
        raw_path = event.get("input", {}).get("path")
        if not isinstance(raw_path, str) or not raw_path:
            return None
        workspace = Path(ctx.cwd)
        write_path = _resolve_write_path(workspace, raw_path)
        if not write_needs_analysis_guard(workspace, write_path):
            return None
        topic_dir = write_path.parent
        if topic_dir.name == "prompts":
            topic_dir = topic_dir.parent
        analysis_path = topic_dir / "analysis.md"
        if analysis_path.is_file():
            return None
        content_path = workspace / "content.md"
        if not content_path.is_file():
            return {
                "block": True,
                "reason": (
                    "Cannot write slide-deck artifact: missing content.md "
                    "and analysis.md. Run baoyu-slide-deck.py bootstrap first."
                ),
            }
        content_text = content_path.read_text(encoding="utf-8")
        bootstrap = ensure_analysis_md(
            workspace,
            content_text,
            _options_from_env(),
        )
        _STATE["last_bootstrap"] = bootstrap
        return None

    api.on("before_agent_start", on_before_agent_start)
    api.on("tool_call", on_tool_call)
