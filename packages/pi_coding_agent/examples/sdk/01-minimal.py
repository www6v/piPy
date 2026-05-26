"""Minimal SDK usage."""

import asyncio

from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_coding_agent import create_agent_session


async def main() -> None:
    registration = register_faux_provider(
        models=[{"id": "demo", "name": "Demo"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("Hello from 01.")]),
    )
    try:
        result = await create_agent_session()
        session = result.session
        await session.set_model("faux", "demo")
        await session.prompt("Say hello.")
        await session.wait_for_idle()
        print("messages:", len(session.messages))
    finally:
        registration.dispose()


if __name__ == "__main__":
    asyncio.run(main())
