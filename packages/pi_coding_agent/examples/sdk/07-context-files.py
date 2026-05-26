"""Context files (AGENTS.md / CLAUDE.md)."""

import asyncio
import tempfile
from pathlib import Path

from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_coding_agent import CreateAgentSessionOptions, create_agent_session


async def main() -> None:
    registration = register_faux_provider(
        models=[{"id": "demo", "name": "Demo"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("Hello from 07.")]),
    )
    try:
        with tempfile.TemporaryDirectory(prefix="pipy-sdk-context-") as tmp:
            cwd = Path(tmp)
            (cwd / "AGENTS.md").write_text(
                "# Project Guidelines\n\n- Always return bullet points.\n",
                encoding="utf-8",
            )

            with_context = await create_agent_session(
                CreateAgentSessionOptions(
                    cwd=cwd,
                    model="faux/demo",
                    in_memory=True,
                )
            )
            without_context = await create_agent_session(
                CreateAgentSessionOptions(
                    cwd=cwd,
                    model="faux/demo",
                    in_memory=True,
                    no_context_files=True,
                )
            )

            marker = "Project Guidelines"
            has_context = marker in with_context.session.agent._system_prompt
            no_context = marker in without_context.session.agent._system_prompt
            print("with context:", has_context)
            print("without context:", no_context)
    finally:
        registration.dispose()


if __name__ == "__main__":
    asyncio.run(main())
