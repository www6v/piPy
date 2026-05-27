"""Run one agent turn via pi-coding-agent SDK."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from pi_coding_agent import CreateAgentSessionOptions, create_agent_session

APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE = APP_ROOT / "workspace"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minimal pi-coding-agent SDK app.",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Say hello in one short sentence.",
        help="user message for the agent",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE,
        help="agent cwd (skills, sessions, context files)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("PIPY_MODEL"),
        help=(
            "provider/model (default: PIPY_MODEL, then faux/demo for offline)"
        ),
    )
    parser.add_argument(
        "--tools",
        default="read,bash",
        help="comma-separated tool allowlist",
    )
    return parser.parse_args()


def _register_faux_if_needed(model: str | None) -> object | None:
    if model:
        return None
    from pi_ai.providers.faux import (
        faux_assistant_message,
        faux_text,
        register_faux_provider,
    )

    return register_faux_provider(
        models=[{"id": "demo", "name": "Demo"}],
        handler=lambda _ctx: faux_assistant_message(
            [faux_text("Hello from my-app template (faux provider).")],
        ),
    )


async def main() -> int:
    args = _parse_args()
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    model = args.model or "faux/demo"
    registration = _register_faux_if_needed(args.model)
    try:
        result = await create_agent_session(
            CreateAgentSessionOptions(
                cwd=str(workspace),
                model=model,
                tools=[t.strip() for t in args.tools.split(",") if t.strip()],
                in_memory=True,
            ),
        )
        session = result.session
        if result.warning:
            print(f"Warning: {result.warning}", file=sys.stderr)

        def on_event(event) -> None:
            if event.type != "message_update":
                return
            delta = getattr(event.assistant_message_event, "delta", "")
            if delta:
                sys.stdout.write(delta)
                sys.stdout.flush()

        session.subscribe(on_event)
        await session.prompt(args.prompt)
        await session.wait_for_idle()
        sys.stdout.write("\n")
        print(f"messages: {len(session.messages)}", file=sys.stderr)
        return 0
    finally:
        if registration is not None:
            registration.dispose()


def cli_main() -> None:
    raise SystemExit(asyncio.run(main()))


if __name__ == "__main__":
    cli_main()
