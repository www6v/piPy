import pytest

from pi_agent.agent_loop import prompt_text, run_agent_loop
from pi_agent.messages import convert_to_llm
from pi_agent.types import AgentContext, AgentLoopConfig
from pi_ai.models import get_model
from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_ai.types import Tool


@pytest.mark.asyncio
async def test_agent_loop_text_response():
    reg = register_faux_provider(
        models=[{"id": "test", "name": "Test"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("hello")]),
    )
    events: list[str] = []

    async def emit(event) -> None:
        events.append(event.type)

    model = get_model("faux", "test")
    config = AgentLoopConfig(model=model, convert_to_llm=convert_to_llm)
    context = AgentContext(system_prompt="sys", messages=[], tools=[])
    await run_agent_loop(
        [prompt_text("hi")],
        context,
        config,
        emit,
        agent_tools=[],
    )
    assert events[0] == "agent_start"
    assert "message_end" in events
    assert events[-1] == "agent_end"
    reg.dispose()


@pytest.mark.asyncio
async def test_agent_loop_with_tool():
    calls = {"count": 0}

    async def echo_tool(_tool_call_id, args, signal=None, on_update=None):
        del signal, on_update
        calls["count"] += 1
        from pi_agent.types import AgentToolResult
        from pi_ai.types import TextContent

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

    from pi_ai.providers import faux as faux_mod
    from pi_ai.providers.faux import faux_tool_call

    register_faux_provider(models=[{"id": "test", "name": "Test"}])
    faux_mod.set_faux_responses(
        [
            faux_assistant_message(
                [faux_tool_call("echo", {"text": "tool-ok"}, tool_id="t1")],
                stop_reason="toolUse",
            ),
            faux_assistant_message([faux_text("done")]),
        ]
    )

    events: list[str] = []

    async def emit(event) -> None:
        events.append(event.type)

    model = get_model("faux", "test")
    config = AgentLoopConfig(model=model, convert_to_llm=convert_to_llm)
    context = AgentContext(
        system_prompt="sys",
        messages=[],
        tools=[Tool(name="echo", description="echo", parameters=EchoTool.parameters)],
    )
    await run_agent_loop(
        [prompt_text("run tool")],
        context,
        config,
        emit,
        agent_tools=[EchoTool()],
    )
    assert "tool_execution_start" in events
    assert calls["count"] == 1
