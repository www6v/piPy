"""Search for installable agent skills via ~/.agents/skills/find-skills."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from pi_coding_agent import CreateAgentSessionOptions, create_agent_session

FIND_SKILLS_DIR = Path.home() / ".agents" / "skills" / "find-skills"
DEFAULT_QUERY = "is there a skill for PR reviews?"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Use the find-skills skill to search the open agent skills "
            "ecosystem."
        ),
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=DEFAULT_QUERY,
        help="what to search for",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("PIPY_MODEL"),
        help=(
            "provider/model override "
            "(default: PIPY_MODEL, ~/.pi settings, or "
            "anthropic/claude-sonnet-4-5)"
        ),
    )
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    skill_file = FIND_SKILLS_DIR / "SKILL.md"
    if not skill_file.is_file():
        print(f"Skill not found: {skill_file}", file=sys.stderr)
        print(
            "Install globally, for example:\n"
            "  npx skills add <owner/repo@find-skills> -g -y",
            file=sys.stderr,
        )
        return 1

    options_kwargs: dict[str, object] = {
        "cwd": str(REPO_ROOT),
        "in_memory": True,
        "skill_paths": [str(FIND_SKILLS_DIR)],
        "tools": ["read", "bash"],
    }
    if args.model:
        options_kwargs["model"] = args.model

    result = await create_agent_session(
        CreateAgentSessionOptions(**options_kwargs),
    )
    session = result.session
    if result.warning:
        print(f"Warning: {result.warning}", file=sys.stderr)

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
    prompt = f"/skill:find-skills {args.query}"
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

    if sys.stdout.isatty():
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
