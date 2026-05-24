import pytest

from pi_agent.agent_loop import prompt_text, run_agent_loop
from pi_agent.messages import convert_to_llm
from pi_agent.types import AgentContext, AgentLoopConfig
from pi_ai.models import get_model
from pi_ai.providers import faux as faux_mod
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
    assert "tool_execution_end" in events
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_unknown_tool_emits_execution_events():
    from pi_ai.providers.faux import faux_tool_call

    register_faux_provider(models=[{"id": "test", "name": "Test"}])
    faux_mod.set_faux_responses(
        [
            faux_assistant_message(
                [
                    faux_tool_call(
                        "missing_tool",
                        {"x": 1},
                        tool_id="t-missing",
                    )
                ],
                stop_reason="toolUse",
            ),
            faux_assistant_message([faux_text("handled")]),
        ]
    )

    events: list[str] = []

    async def emit(event) -> None:
        events.append(event.type)

    model = get_model("faux", "test")
    config = AgentLoopConfig(model=model, convert_to_llm=convert_to_llm)
    context = AgentContext(system_prompt="sys", messages=[], tools=[])
    await run_agent_loop(
        [prompt_text("go")],
        context,
        config,
        emit,
        agent_tools=[],
    )
    assert "tool_execution_start" in events
    assert "tool_execution_end" in events


@pytest.mark.asyncio
async def test_agent_loop_callbacks_context_tool_call_tool_result():
    from pi_ai.providers.faux import faux_tool_call

    class EchoTool:
        name = "echo"
        description = "echo"
        parameters = {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }
        execution_mode = "parallel"

        async def execute(self, _tool_call_id, args, signal=None, on_update=None):
            del signal, on_update
            from pi_agent.types import AgentToolResult
            from pi_ai.types import TextContent

            return AgentToolResult(content=[TextContent(text=args["text"])])

    register_faux_provider(models=[{"id": "test", "name": "Test"}])
    faux_mod.set_faux_responses(
        [
            faux_assistant_message(
                [faux_tool_call("echo", {"text": "base"}, tool_id="t-cb")],
                stop_reason="toolUse",
            ),
            faux_assistant_message([faux_text("done")]),
        ]
    )

    model = get_model("faux", "test")

    async def on_context(messages):
        from pi_agent.agent_loop import prompt_text

        return [*messages, prompt_text("injected-context")]

    async def on_tool_call(tool_name, tool_call_id, args):
        assert tool_name == "echo"
        assert tool_call_id == "t-cb"
        return {"args": {**args, "text": "mutated"}}

    async def on_tool_result(tool_name, tool_call_id, args, result):
        del tool_name, tool_call_id, args
        from pi_agent.types import AgentToolResult
        from pi_ai.types import TextContent

        return AgentToolResult(
            content=[TextContent(text=f"{result.content[0].text}-patched")],
            details=result.details,
            is_error=result.is_error,
            terminate=result.terminate,
        )

    config = AgentLoopConfig(
        model=model,
        convert_to_llm=convert_to_llm,
        on_context=on_context,
        on_tool_call=on_tool_call,
        on_tool_result=on_tool_result,
    )
    context = AgentContext(
        system_prompt="sys",
        messages=[],
        tools=[Tool(name="echo", description="echo", parameters=EchoTool.parameters)],
    )
    messages = await run_agent_loop(
        [prompt_text("run tool")],
        context,
        config,
        lambda _event: None,
        agent_tools=[EchoTool()],
    )
    tool_results = [item for item in messages if getattr(item, "role", "") == "toolResult"]
    assert len(tool_results) == 1
    assert tool_results[0].content[0].text == "mutated-patched"
