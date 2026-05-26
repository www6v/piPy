"""Settings from .pi/settings.json and runtime overrides."""

import asyncio
import json
import tempfile
from pathlib import Path

from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_coding_agent import CreateAgentSessionOptions, create_agent_session
from pi_coding_agent.settings import load_settings


async def main() -> None:
    registration = register_faux_provider(
        models=[{"id": "demo", "name": "Demo"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("Hello from 10.")]),
    )
    try:
        with tempfile.TemporaryDirectory(prefix="pipy-sdk-settings-") as tmp:
            cwd = Path(tmp)
            pi_dir = cwd / ".pi"
            pi_dir.mkdir(parents=True, exist_ok=True)
            (pi_dir / "settings.json").write_text(
                json.dumps(
                    {
                        "defaultModel": "demo",
                        "defaultProvider": "faux",
                        "defaultThinkingLevel": "low",
                        "retry": {"enabled": True, "maxRetries": 5, "baseDelayMs": 1000},
                        "compaction": {"enabled": False},
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            settings = load_settings(cwd)
            print("default model:", settings.default_provider, settings.default_model)
            print("retry max:", settings.retry.max_retries)

            from_settings = await create_agent_session(
                CreateAgentSessionOptions(cwd=cwd, in_memory=True)
            )
            print("thinking from settings:", from_settings.session.thinking_level)

            overridden = await create_agent_session(
                CreateAgentSessionOptions(
                    cwd=cwd,
                    in_memory=True,
                    thinking_level="high",
                )
            )
            print("thinking override:", overridden.session.thinking_level)
    finally:
        registration.dispose()


if __name__ == "__main__":
    asyncio.run(main())
