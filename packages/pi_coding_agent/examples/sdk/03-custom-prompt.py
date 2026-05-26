"""Custom system prompt examples."""

import asyncio

from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_coding_agent import CreateAgentSessionOptions, create_agent_session


async def main() -> None:
    registration = register_faux_provider(
        models=[{"id": "demo", "name": "Demo"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("Hello from 03.")]),
    )
    try:
        # Replace the full system prompt.
        replaced = await create_agent_session(
            CreateAgentSessionOptions(
                model="faux/demo",
                in_memory=True,
                system_prompt=(
                    "You are a pirate assistant.\n"
                    "Always end with Arrr!"
                ),
                system_prompt_is_final=True,
            )
        )
        await replaced.session.prompt("What is 2 + 2?")
        await replaced.session.wait_for_idle()
        print("replace prompt done")

        # Inject custom prompt into normal prompt assembly.
        merged = await create_agent_session(
            CreateAgentSessionOptions(
                model="faux/demo",
                in_memory=True,
                system_prompt="Be concise and use bullet points.",
                system_prompt_is_final=False,
            )
        )
        await merged.session.prompt("List three TypeScript benefits.")
        await merged.session.wait_for_idle()
        print("merged prompt done")
    finally:
        registration.dispose()


if __name__ == "__main__":
    asyncio.run(main())
