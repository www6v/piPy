# SDK (Programmatic Usage)

Embed piPy in Python apps without the CLI. Mirrors [pi `docs/sdk.md`](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent/docs/sdk.md).

## Quick start

```python
import asyncio

from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_coding_agent import CreateAgentSessionOptions, create_agent_session


async def main() -> None:
    register_faux_provider(
        models=[{"id": "test", "name": "Test"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("hello from sdk")]),
    )
    result = await create_agent_session(
        CreateAgentSessionOptions(
            model="faux/test",
            provider="faux",
            tools=[],
            in_memory=True,
        )
    )
    session = result.session

    def on_event(event):
        if event.type == "message_update":
            delta = getattr(event.assistant_message_event, "delta", "")
            if delta:
                print(delta, end="", flush=True)

    session.subscribe(on_event)
    await session.prompt("Say hello")
    await session.wait_for_idle()
    print()


asyncio.run(main())
```

## `create_agent_session()`

| Option | Description |
|--------|-------------|
| `cwd` | Working directory (default: `os.getcwd()`) |
| `model` | `provider/model` pattern or `Model` instance |
| `tools` | Tool name allowlist (default: `read`, `bash`) |
| `system_prompt` | System prompt override |
| `no_skills` / `no_prompt_templates` / `no_extensions` | Disable resource discovery |
| `skill_paths` / `prompt_paths` / `extension_paths` | Extra resource paths |
| `api_key` | API key override |
| `thinking_level` | `off` / `low` / `medium` / `high` / … |
| `in_memory` | No JSONL session file |
| `continue_session` | Resume latest session for cwd |
| `session_path` | Open specific `.jsonl` session |
| `model_registry` | Custom `ModelRegistry` |

Returns `CreateAgentSessionResult(session=AgentSession, warning=...)`.

## `AgentSession`

- `await session.prompt(text)` — run one turn, persist messages
- `session.subscribe(listener)` — agent events
- `session.abort()` / `await session.wait_for_idle()`
- `await session.set_model(provider, model_id)`
- `session.set_thinking_level(level)`
- `session.messages`, `session.model`, `session.is_streaming`
- `session.session_file`, `session.session_id`
- `session.get_commands()` / `session.get_resource_diagnostics()`
- `await session.reload_resources()`

## Exports

```python
from pi_coding_agent import (
    AgentSession,
    AuthStorage,
    CreateAgentSessionOptions,
    ModelRegistry,
    SessionManager,
    create_agent_session,
    get_registry,
)
```
