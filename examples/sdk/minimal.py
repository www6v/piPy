"""Minimal SDK example (pi: examples/sdk/)."""

import asyncio

from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_coding_agent import CreateAgentSessionOptions, create_agent_session


async def main() -> None:
    register_faux_provider(
        models=[{"id": "demo", "name": "Demo"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("SDK works.")]),
    )
    result = await create_agent_session(
        CreateAgentSessionOptions(
            model="faux/demo",
            provider="faux",
            tools=[],
            in_memory=True,
        )
    )
    await result.session.prompt("ping")
    await result.session.wait_for_idle()
    print("done:", len(result.session.messages), "messages")


if __name__ == "__main__":
    asyncio.run(main())
