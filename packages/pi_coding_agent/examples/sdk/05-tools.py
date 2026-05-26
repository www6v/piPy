"""Tool allowlist examples."""

import asyncio
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
        handler=lambda _ctx: faux_assistant_message([faux_text("Hello from 05.")]),
    )
    try:
        read_only = await create_agent_session(
            CreateAgentSessionOptions(
                model="faux/demo",
                in_memory=True,
                tools=["read", "grep", "find", "ls"],
            )
        )
        print("read-only tools:", [tool.name for tool in read_only.session.agent._tools])

        custom_tools = await create_agent_session(
            CreateAgentSessionOptions(
                model="faux/demo",
                in_memory=True,
                tools=["read", "bash", "grep"],
            )
        )
        print("custom tools:", [tool.name for tool in custom_tools.session.agent._tools])

        custom_cwd = str(Path.cwd())
        with_cwd = await create_agent_session(
            CreateAgentSessionOptions(
                cwd=custom_cwd,
                model="faux/demo",
                in_memory=True,
                tools=["read", "bash", "edit", "write"],
            )
        )
        print("cwd tools:", [tool.name for tool in with_cwd.session.agent._tools])
    finally:
        registration.dispose()


if __name__ == "__main__":
    asyncio.run(main())
