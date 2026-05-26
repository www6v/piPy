"""API key resolution and auth storage examples."""

import asyncio
import tempfile
from pathlib import Path

from pi_ai.model_registry import ModelRegistry
from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_coding_agent import CreateAgentSessionOptions, create_agent_session
from pi_coding_agent.auth.storage import get_auth_storage


async def main() -> None:
    registration = register_faux_provider(
        models=[{"id": "demo", "name": "Demo"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("Hello from 09.")]),
    )
    try:
        with tempfile.TemporaryDirectory(prefix="pipy-sdk-auth-") as tmp:
            auth_path = Path(tmp) / "auth.json"
            models_path = Path(tmp) / "models.json"
            models_path.write_text("{\"models\":[]}\n", encoding="utf-8")

            # Route auth storage to a custom path.
            auth = get_auth_storage(auth_path)
            auth.set_api_key("faux", "fake-key-from-auth-storage")

            registry = ModelRegistry(models_path)
            default_auth = await create_agent_session(
                CreateAgentSessionOptions(
                    model="faux/demo",
                    in_memory=True,
                    model_registry=registry,
                )
            )
            await default_auth.session.prompt("hello")
            await default_auth.session.wait_for_idle()
            print("default auth storage session ok")

            # CLI/runtime override has highest priority.
            overridden = await create_agent_session(
                CreateAgentSessionOptions(
                    model="faux/demo",
                    in_memory=True,
                    model_registry=registry,
                    api_key="fake-override-key",
                )
            )
            await overridden.session.prompt("hello")
            await overridden.session.wait_for_idle()
            print("api_key override session ok")

            print("note: OAuth flow is not exposed in Python SDK yet.")
    finally:
        registration.dispose()


if __name__ == "__main__":
    asyncio.run(main())
