import pytest

from pi_agent.agent import Agent
from pi_ai.models import get_model
from pi_ai.providers.faux import faux_assistant_message, faux_text, register_faux_provider


@pytest.mark.asyncio
async def test_subscribe_and_wait_for_idle():
    reg = register_faux_provider(
        models=[{"id": "test", "name": "Test"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("ok")]),
    )
    model = get_model("faux", "test")
    agent = Agent(system_prompt="sys", model=model, tools=[])
    order: list[str] = []

    async def listener(event) -> None:
        order.append(event.type)

    agent.subscribe(listener)
    await agent.prompt("hello")
    await agent.wait_for_idle()
    assert order[0] == "agent_start"
    assert order[-1] == "agent_end"
    reg.dispose()
