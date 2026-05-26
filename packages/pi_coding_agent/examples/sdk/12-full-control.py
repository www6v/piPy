"""Full-control setup with explicit options."""

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


async def main() -> None:
    registration = register_faux_provider(
        models=[{"id": "demo", "name": "Demo"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("Hello from 12.")]),
    )
    try:
        with tempfile.TemporaryDirectory(prefix="pipy-sdk-full-control-") as tmp:
            root = Path(tmp)
            models_path = root / "models.json"
            models_path.write_text("{\"models\":[]}\n", encoding="utf-8")
            registry = ModelRegistry(models_path)

            result = await create_agent_session(
                CreateAgentSessionOptions(
                    cwd=root,
                    model="faux/demo",
                    provider="faux",
                    model_registry=registry,
                    in_memory=True,
                    tools=["read", "bash"],
                    system_prompt=(
                        "You are a minimal assistant.\n"
                        "Available tools: read, bash.\n"
                        "Be concise."
                    ),
                    system_prompt_is_final=True,
                    no_context_files=True,
                    no_skills=True,
                    no_prompt_templates=True,
                    no_extensions=True,
                    thinking_level="off",
                )
            )
            session = result.session
            await session.prompt("List files in current directory.")
            await session.wait_for_idle()
            print("messages:", len(session.messages))
    finally:
        registration.dispose()


if __name__ == "__main__":
    asyncio.run(main())
