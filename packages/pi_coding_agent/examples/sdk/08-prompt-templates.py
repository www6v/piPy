"""Prompt template discovery and expansion."""

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
        handler=lambda _ctx: faux_assistant_message([faux_text("Hello from 08.")]),
    )
    try:
        with tempfile.TemporaryDirectory(prefix="pipy-sdk-prompts-") as tmp:
            prompts_dir = Path(tmp) / "prompts"
            prompts_dir.mkdir(parents=True, exist_ok=True)
            (prompts_dir / "deploy.md").write_text(
                "---\n"
                "description: Deploy helper template\n"
                "---\n\n"
                "Deploy app for $1 in env $2.\n",
                encoding="utf-8",
            )

            result = await create_agent_session(
                CreateAgentSessionOptions(
                    model="faux/demo",
                    in_memory=True,
                    no_prompt_templates=True,
                    prompt_paths=[str(prompts_dir)],
                )
            )
            session = result.session
            prompt_commands = [
                item["name"] for item in session.get_commands() if item["source"] == "prompt"
            ]
            print("prompt commands:", prompt_commands)
            await session.prompt("/deploy api production")
            await session.wait_for_idle()
            print("template execution done")
    finally:
        registration.dispose()


if __name__ == "__main__":
    asyncio.run(main())
