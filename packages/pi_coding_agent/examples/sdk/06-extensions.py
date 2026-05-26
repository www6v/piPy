"""Extensions configuration and runtime hooks."""

import asyncio
import tempfile
from pathlib import Path

from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_coding_agent import CreateAgentSessionOptions, create_agent_session


def _write_extension(path: Path) -> None:
    path.write_text(
        "def register(api):\n"
        "    def on_input(event, _ctx):\n"
        "        text = event.get('text', '')\n"
        "        if text.startswith('hello'):\n"
        "            return {'action': 'transform', 'text': text + ' from extension'}\n"
        "        return {'action': 'continue'}\n\n"
        "    def showargs(args, ctx):\n"
        "        print('[/showargs]', args)\n"
        "        return None\n\n"
        "    api.on('input', on_input)\n"
        "    api.register_command('showargs', handler=showargs, description='Echo args')\n",
        encoding="utf-8",
    )


async def main() -> None:
    registration = register_faux_provider(
        models=[{"id": "demo", "name": "Demo"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("Hello from 06.")]),
    )
    try:
        with tempfile.TemporaryDirectory(prefix="pipy-sdk-ext-") as tmp:
            ext_file = Path(tmp) / "my_extension.py"
            _write_extension(ext_file)

            result = await create_agent_session(
                CreateAgentSessionOptions(
                    model="faux/demo",
                    in_memory=True,
                    extension_paths=[str(ext_file)],
                )
            )
            session = result.session
            print("commands:", [item["name"] for item in session.get_commands()])
            await session.prompt("/showargs one two")
            await session.prompt("hello")
            await session.wait_for_idle()
            print("extension prompt done")
    finally:
        registration.dispose()


if __name__ == "__main__":
    asyncio.run(main())
