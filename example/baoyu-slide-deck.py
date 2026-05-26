"""Run baoyu-slide-deck via pi_coding_agent SDK + slide_deck_guard extension."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_EXAMPLE_DIR = Path(__file__).resolve().parent
if str(_EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLE_DIR))

from pi_coding_agent import CreateAgentSessionOptions, create_agent_session
from slide_deck_bootstrap import (
    BootstrapOptions,
    ensure_analysis_md,
    ensure_content_md,
    ensure_extend_md,
)

SLIDE_DECK_SKILL_DIR = Path.home() / ".agents" / "skills" / "baoyu-slide-deck"
DEFAULT_FIXTURE = _EXAMPLE_DIR / "fixtures" / "slide-deck-brief.md"
DEFAULT_WORKSPACE = _EXAMPLE_DIR / ".workspace" / "slide-deck-demo"
GUARD_EXTENSION = _EXAMPLE_DIR / "extensions" / "slide_deck_guard.py"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run baoyu-slide-deck with slide_deck_guard extension "
            "(ensures analysis.md via SDK lifecycle hooks)."
        ),
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE,
        help="agent cwd (default: example/.workspace/slide-deck-demo)",
    )
    parser.add_argument(
        "--content",
        type=Path,
        default=DEFAULT_FIXTURE,
        help="source markdown for the deck",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="full pipeline; default is outline-only",
    )
    parser.add_argument(
        "--lang",
        default="zh",
        help="pass through to skill (default: zh)",
    )
    parser.add_argument(
        "--slides",
        type=int,
        default=6,
        help="target slide count (default: 6)",
    )
    parser.add_argument(
        "--style",
        default=None,
        help="override style preset",
    )
    parser.add_argument(
        "--audience",
        default="general",
        help="audience for analysis.md (default: general)",
    )
    parser.add_argument(
        "--force-analysis",
        action="store_true",
        help="regenerate analysis.md in extension bootstrap",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("PIPY_MODEL"),
        help="provider/model (default: PIPY_MODEL or ~/.pi settings)",
    )
    return parser.parse_args()


def _apply_env_options(args: argparse.Namespace) -> None:
    os.environ["SLIDE_DECK_LANG"] = args.lang
    os.environ["SLIDE_DECK_SLIDES"] = str(args.slides)
    os.environ["SLIDE_DECK_AUDIENCE"] = args.audience
    if args.style:
        os.environ["SLIDE_DECK_STYLE"] = args.style
    elif "SLIDE_DECK_STYLE" in os.environ:
        del os.environ["SLIDE_DECK_STYLE"]
    if args.force_analysis:
        os.environ["SLIDE_DECK_FORCE_ANALYSIS"] = "1"
    else:
        os.environ.pop("SLIDE_DECK_FORCE_ANALYSIS", None)


def _prepare_workspace(workspace: Path, content_src: Path) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    ensure_extend_md(workspace)
    return ensure_content_md(workspace, content_src)


def _build_skill_prompt(
    content_name: str,
    *,
    outline_only: bool,
    lang: str,
    slides: int,
) -> str:
    flags = [f"--lang {lang}", f"--slides {slides}"]
    if outline_only:
        flags.append("--outline-only")
    flag_str = " ".join(flags)
    return f"/skill:baoyu-slide-deck {content_name} {flag_str}"


def _verify_outputs(
    bootstrap,
    *,
    outline_only: bool,
) -> list[str]:
    errors: list[str] = []
    if not bootstrap.analysis_path.is_file():
        errors.append(f"missing analysis.md: {bootstrap.analysis_path}")
    else:
        text = bootstrap.analysis_path.read_text(encoding="utf-8")
        if "step_2_complete: true" not in text:
            errors.append("analysis.md missing step_2_complete marker")
    if outline_only and not (bootstrap.topic_dir / "outline.md").is_file():
        errors.append(f"missing outline.md: {bootstrap.topic_dir / 'outline.md'}")
    return errors


async def main() -> int:
    args = _parse_args()
    skill_file = SLIDE_DECK_SKILL_DIR / "SKILL.md"
    if not skill_file.is_file():
        print(f"Skill not found: {skill_file}", file=sys.stderr)
        print(
            "Install globally, for example:\n"
            "  npx skills add <owner/repo@baoyu-slide-deck> -g -y",
            file=sys.stderr,
        )
        return 1

    if not args.content.is_file():
        print(f"Content not found: {args.content}", file=sys.stderr)
        return 1

    if not GUARD_EXTENSION.is_file():
        print(f"Extension not found: {GUARD_EXTENSION}", file=sys.stderr)
        return 1

    workspace = args.workspace.resolve()
    _apply_env_options(args)
    try:
        content_path = _prepare_workspace(workspace, args.content)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    outline_only = not args.full
    options = BootstrapOptions(
        lang=args.lang,
        slides=args.slides,
        audience=args.audience,
        style=args.style,
        force=args.force_analysis,
    )
    options_kwargs: dict[str, object] = {
        "cwd": str(workspace),
        "in_memory": False,
        "skill_paths": [str(SLIDE_DECK_SKILL_DIR)],
        "extension_paths": [str(GUARD_EXTENSION)],
        "tools": ["read", "write", "bash"],
    }
    if args.model:
        options_kwargs["model"] = args.model

    result = await create_agent_session(
        CreateAgentSessionOptions(**options_kwargs),
    )
    session = result.session
    if result.warning:
        print(f"Warning: {result.warning}", file=sys.stderr)

    print(f"Workspace:  {workspace}", flush=True)
    print(f"Extension:  {GUARD_EXTENSION}", flush=True)
    print(f"Content:    {content_path}", flush=True)

    def on_event(event) -> None:
        if event.type != "message_update":
            return
        for block in event.message.content:
            if block.type != "text":
                continue
            delta = getattr(event.assistant_message_event, "delta", "")
            if delta:
                sys.stdout.write(delta)
                sys.stdout.flush()

    session.subscribe(on_event)
    prompt = _build_skill_prompt(
        content_path.name,
        outline_only=outline_only,
        lang=args.lang,
        slides=args.slides,
    )
    print(f">>> {prompt}\n", flush=True)
    await session.prompt(prompt)
    await session.wait_for_idle()

    assistant = next(
        (message for message in reversed(session.messages) if message.role == "assistant"),
        None,
    )
    if assistant is not None and assistant.stop_reason in ("error", "aborted"):
        error_message = assistant.error_message or "Agent request failed"
        print(f"\nError: {error_message}", file=sys.stderr)
        return 1

    content_text = content_path.read_text(encoding="utf-8")
    bootstrap = ensure_analysis_md(workspace, content_text, options)
    verify_errors = _verify_outputs(bootstrap, outline_only=outline_only)
    if verify_errors:
        print("\nPost-run checks failed:", file=sys.stderr)
        for item in verify_errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    outline = bootstrap.topic_dir / "outline.md"
    print(f"\nTopic dir:  {bootstrap.topic_dir}", flush=True)
    print(f"Analysis:   {bootstrap.analysis_path}", flush=True)
    if outline.is_file():
        print(f"Outline:    {outline}", flush=True)

    if sys.stdout.isatty():
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
