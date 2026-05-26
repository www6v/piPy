"""Skills configuration and discovery."""

import asyncio
import tempfile
from pathlib import Path

from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_coding_agent import CreateAgentSessionOptions, create_agent_session


def _write_skill(skill_dir: Path) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: my-skill\n"
        "description: Custom project instructions\n"
        "---\n\n"
        "# My Skill\n"
        "Always answer briefly.\n",
        encoding="utf-8",
    )


async def main() -> None:
    registration = register_faux_provider(
        models=[{"id": "demo", "name": "Demo"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("Hello from 04.")]),
    )
    try:
        with tempfile.TemporaryDirectory(prefix="pipy-sdk-skills-") as tmp:
            skill_root = Path(tmp) / "skills" / "my-skill"
            _write_skill(skill_root)

            result = await create_agent_session(
                CreateAgentSessionOptions(
                    model="faux/demo",
                    in_memory=True,
                    no_skills=True,
                    skill_paths=[str(skill_root.parent)],
                )
            )
            commands = result.session.get_commands()
            skill_commands = [item["name"] for item in commands if item["source"] == "skill"]
            print("skills:", skill_commands)
            print("diagnostics:", result.session.get_resource_diagnostics())
    finally:
        registration.dispose()


if __name__ == "__main__":
    asyncio.run(main())
