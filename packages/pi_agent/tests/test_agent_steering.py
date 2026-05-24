"""Agent steering injected between tool batches."""

from __future__ import annotations

import asyncio

import pytest

from pi_agent.agent import Agent, AgentBusyError
from pi_agent.messages import convert_to_llm
from pi_agent.types import AgentStartEvent, AgentToolResult
from pi_ai.models import get_model
from pi_ai.providers import faux as faux_mod
from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    faux_tool_call,
    register_faux_provider,
)
from pi_ai.types import TextContent

pytestmark = pytest.mark.asyncio


async def echo_tool(tool_call_id, args, signal=None, on_update=None):
    del signal, on_update
    del tool_call_id
    return AgentToolResult(content=[TextContent(text=args["text"])])


class EchoTool:
    name = "echo"
    description = "echo"
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    execution_mode = "parallel"
    execute = echo_tool


async def test_steer_during_tool_run_adds_user_message():
    tool_done = asyncio.Event()

    faux_mod.set_faux_responses(
        [
            faux_assistant_message(
                [faux_tool_call("echo", {"text": "tool-ok"}, tool_id="t1")],
                stop_reason="toolUse",
            ),
            faux_assistant_message([faux_text("done")]),
        ]
    )

    reg = register_faux_provider(models=[{"id": "test", "name": "Test"}])
    agent = Agent(
        model=get_model("faux", "test"),
        tools=[EchoTool()],
        system_prompt="sys",
        convert_to_llm_fn=convert_to_llm,
    )

    def capture_tool_exec(event: object) -> None:
        evt = getattr(event, "type", None)
        if evt == "tool_execution_end":
            tool_done.set()

    agent.subscribe(capture_tool_exec)

    async def inject_steering():
        await tool_done.wait()
        agent.steer("correction-after-tool")

    steering_task = asyncio.create_task(inject_steering())

    await agent.prompt("run tool")

    await steering_task

    users = [
        m for m in agent.state.messages
        if hasattr(m, "role") and getattr(m, "role", None) == "user"
    ]
    texts = [m.content for m in users if isinstance(m.content, str)]
    assert "run tool" in texts
    assert "correction-after-tool" in texts

    reg.dispose()


async def test_prompt_while_busy_raises():
    reg = register_faux_provider(
        models=[{"id": "busy", "name": "Busy"}],
        handler=lambda _ctx: faux_assistant_message("ok"),
    )
    try:
        agent = Agent(
            model=get_model("faux", "busy"),
            convert_to_llm_fn=convert_to_llm,
        )
        started = asyncio.Event()

        def on_start(event: object) -> None:
            if isinstance(event, AgentStartEvent):
                started.set()

        agent.subscribe(on_start)
        runner = asyncio.create_task(agent.prompt("first"))
        await asyncio.wait_for(started.wait(), timeout=5.0)
        with pytest.raises(AgentBusyError):
            await agent.prompt("second")
        await runner
    finally:
        reg.dispose()
