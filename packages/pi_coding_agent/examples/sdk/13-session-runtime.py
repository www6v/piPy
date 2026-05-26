"""Session runtime pattern: replace active session explicitly."""

import asyncio
import tempfile
from pathlib import Path

from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_coding_agent import CreateAgentSessionOptions, SessionManager, create_agent_session


async def main() -> None:
    registration = register_faux_provider(
        models=[{"id": "demo", "name": "Demo"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("Hello from 13.")]),
    )
    try:
        with tempfile.TemporaryDirectory(prefix="pipy-sdk-runtime-") as tmp:
            cwd = Path(tmp)
            initial_manager = SessionManager.create(cwd)
            initial = await create_agent_session(
                CreateAgentSessionOptions(
                    cwd=cwd,
                    model="faux/demo",
                    session_manager=initial_manager,
                )
            )
            session = initial.session
            original_file = session.session_file
            print("initial session:", original_file)

            # Replace active persisted session in-place.
            await session.new_session(cwd=cwd)
            print("after new_session:", session.session_file)

            # Reopen old session path (similar to runtime switch).
            if original_file:
                reopened = await create_agent_session(
                    CreateAgentSessionOptions(
                        cwd=cwd,
                        model="faux/demo",
                        session_path=original_file,
                    )
                )
                print("after switch:", reopened.session.session_file)
    finally:
        registration.dispose()


if __name__ == "__main__":
    asyncio.run(main())
