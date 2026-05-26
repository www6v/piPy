"""Session persistence examples."""

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
        handler=lambda _ctx: faux_assistant_message([faux_text("Hello from 11.")]),
    )
    try:
        in_memory = await create_agent_session(
            CreateAgentSessionOptions(model="faux/demo", in_memory=True)
        )
        print("in-memory session file:", in_memory.session.session_file)

        with tempfile.TemporaryDirectory(prefix="pipy-sdk-sessions-") as tmp:
            cwd = Path(tmp)

            created = await create_agent_session(
                CreateAgentSessionOptions(cwd=cwd, model="faux/demo")
            )
            print("created session:", created.session.session_file)

            continued = await create_agent_session(
                CreateAgentSessionOptions(
                    cwd=cwd,
                    model="faux/demo",
                    continue_session=True,
                )
            )
            print("continued session:", continued.session.session_file)

            paths = SessionManager.list_paths_for_cwd(cwd)
            print("found sessions:", len(paths))
            if paths:
                opened = await create_agent_session(
                    CreateAgentSessionOptions(
                        cwd=cwd,
                        model="faux/demo",
                        session_path=str(paths[0]),
                    )
                )
                print("opened session id:", opened.session.session_id)

                forked = await create_agent_session(
                    CreateAgentSessionOptions(
                        cwd=cwd,
                        model="faux/demo",
                        fork_session=str(paths[0]),
                    )
                )
                print("forked session:", forked.session.session_file)
    finally:
        registration.dispose()


if __name__ == "__main__":
    asyncio.run(main())
