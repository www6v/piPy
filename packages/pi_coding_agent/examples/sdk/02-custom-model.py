"""Custom model selection and thinking level."""

import asyncio

from pi_ai.model_registry import get_registry
from pi_ai.models import get_model
from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_coding_agent import CreateAgentSessionOptions, create_agent_session


async def main() -> None:
    registration = register_faux_provider(
        models=[
            {"id": "demo", "name": "Demo"},
            {"id": "custom", "name": "Custom"},
        ],
        handler=lambda _ctx: faux_assistant_message([faux_text("Hello from 02.")]),
    )
    try:
        model = get_model("faux", "demo")
        print("model:", f"{model.provider}/{model.id}")

        registry = get_registry()
        found = registry.find("faux", "custom")
        if found is not None:
            print("registry model:", f"{found.provider}/{found.id}")

        result = await create_agent_session(
            CreateAgentSessionOptions(
                model="faux/demo",
                thinking_level="medium",
                in_memory=True,
            )
        )
        await result.session.prompt("One-line greeting.")
        await result.session.wait_for_idle()
        print("thinking:", result.session.thinking_level)
    finally:
        registration.dispose()


if __name__ == "__main__":
    asyncio.run(main())
