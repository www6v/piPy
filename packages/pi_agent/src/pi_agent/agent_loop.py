"""Agent loop with tool execution."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import jsonschema

from pi_agent.messages import convert_to_llm
from pi_agent.types import (
    AgentContext,
    AgentEndEvent,
    AgentEvent,
    AgentLoopConfig,
    AgentMessage,
    AgentStartEvent,
    AgentTool,
    AgentToolResult,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnEndEvent,
    TurnStartEvent,
    user_message,
)
from pi_ai.stream import stream_simple
from pi_ai.types import (
    AssistantMessage,
    Context,
    TextContent,
    Tool,
    ToolCall,
    ToolResultMessage,
)


async def _emit(sink: Any, event: AgentEvent) -> None:
    result = sink(event)
    if asyncio.iscoroutine(result):
        await result


def _validate_args(tool: AgentTool, args: dict[str, Any]) -> None:
    jsonschema.validate(instance=args, schema=tool.parameters)


def _tools_for_llm(tools: list[AgentTool]) -> list[Tool]:
    return [
        Tool(
            name=tool.name,
            description=tool.description,
            parameters=tool.parameters,
        )
        for tool in tools
    ]


async def _execute_tool(
    tool: AgentTool,
    tool_call: ToolCall,
    signal: Any,
) -> AgentToolResult:
    _validate_args(tool, tool_call.arguments)
    try:
        return await tool.execute(tool_call.id, tool_call.arguments, signal)
    except Exception as exc:
        return AgentToolResult(
            content=[TextContent(text=str(exc))],
            is_error=True,
        )


async def _execute_tools(
    context: AgentContext,
    assistant: AssistantMessage,
    agent_tools: list[AgentTool],
    config: AgentLoopConfig,
    signal: Any,
    emit: Any,
) -> tuple[list[ToolResultMessage], bool]:
    tool_calls = [b for b in assistant.content if b.type == "toolCall"]
    if not tool_calls:
        return [], False
    by_name = {tool.name: tool for tool in agent_tools}
    results: list[ToolResultMessage] = []
    exec_results: list[AgentToolResult] = []

    async def run_one(tool_call: ToolCall) -> tuple[ToolResultMessage, AgentToolResult]:
        tool = by_name.get(tool_call.name)
        if tool is None:
            result = AgentToolResult(
                content=[TextContent(text=f"Unknown tool: {tool_call.name}")],
                is_error=True,
            )
        else:
            await _emit(
                emit,
                ToolExecutionStartEvent(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    args=tool_call.arguments,
                ),
            )
            result = await _execute_tool(tool, tool_call, signal)
            await _emit(
                emit,
                ToolExecutionEndEvent(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    result=result,
                    is_error=result.is_error,
                ),
            )
        message = ToolResultMessage(
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            content=result.content,
            is_error=result.is_error,
            timestamp=int(time.time() * 1000),
        )
        return message, result

    if config.tool_execution == "parallel":
        pairs = await asyncio.gather(*(run_one(tc) for tc in tool_calls))
    else:
        pairs = [await run_one(tc) for tc in tool_calls]
    for message, exec_result in pairs:
        results.append(message)
        exec_results.append(exec_result)

    terminate = bool(exec_results) and all(r.terminate for r in exec_results)
    return results, terminate


async def _stream_assistant(
    context: AgentContext,
    config: AgentLoopConfig,
    agent_tools: list[AgentTool],
    signal: Any,
    emit: Any,
    stream_fn: Any = None,
) -> AssistantMessage:
    llm_messages = await _maybe_await(config.convert_to_llm(context.messages))
    llm_context = Context(
        system_prompt=context.system_prompt,
        messages=llm_messages,
        tools=_tools_for_llm(agent_tools),
    )
    api_key = config.api_key
    if config.get_api_key is not None:
        resolved = config.get_api_key(config.model.provider)
        if asyncio.iscoroutine(resolved):
            resolved = await resolved
        api_key = resolved or api_key
    streamer = stream_fn or stream_simple
    response = streamer(
        config.model,
        llm_context,
        tools=llm_context.tools,
        api_key=api_key,
        signal=signal,
    )
    if asyncio.iscoroutine(response):
        response = await response
    final: AssistantMessage | None = None
    async for event in response:
        if event.type == "start":
            await _emit(emit, MessageStartEvent(message=event.partial))
        elif event.type == "text_delta":
            await _emit(
                emit,
                MessageUpdateEvent(
                    message=event.partial,
                    assistant_message_event=event,
                ),
            )
        elif event.type in ("done", "error"):
            final = await response.result()
    if final is None:
        final = await response.result()
    context.messages.append(final)
    await _emit(emit, MessageEndEvent(message=final))
    return final


async def _maybe_await(value: Any) -> Any:
    if asyncio.iscoroutine(value):
        return await value
    return value


async def run_agent_loop(
    prompts: list[AgentMessage],
    context: AgentContext,
    config: AgentLoopConfig,
    emit: Any,
    *,
    agent_tools: list[AgentTool],
    signal: Any = None,
    stream_fn: Any = None,
) -> list[AgentMessage]:
    new_messages: list[AgentMessage] = list(prompts)
    current = AgentContext(
        system_prompt=context.system_prompt,
        messages=list(context.messages) + list(prompts),
        tools=context.tools,
    )
    await _emit(emit, AgentStartEvent())
    await _emit(emit, TurnStartEvent())
    for prompt in prompts:
        await _emit(emit, MessageStartEvent(message=prompt))
        await _emit(emit, MessageEndEvent(message=prompt))

    while True:
        assistant = await _stream_assistant(
            current,
            config,
            agent_tools,
            signal,
            emit,
            stream_fn,
        )
        new_messages.append(assistant)
        if assistant.stop_reason in ("error", "aborted"):
            await _emit(emit, TurnEndEvent(message=assistant, tool_results=[]))
            await _emit(emit, AgentEndEvent(messages=new_messages))
            return new_messages

        tool_results, should_stop = await _execute_tools(
            current,
            assistant,
            agent_tools,
            config,
            signal,
            emit,
        )
        for result in tool_results:
            current.messages.append(result)
            new_messages.append(result)
            await _emit(emit, MessageStartEvent(message=result))
            await _emit(emit, MessageEndEvent(message=result))

        await _emit(emit, TurnEndEvent(message=assistant, tool_results=tool_results))

        has_tool_calls = any(
            block.type == "toolCall" for block in assistant.content
        )
        if not has_tool_calls or should_stop:
            await _emit(emit, AgentEndEvent(messages=new_messages))
            return new_messages

        await _emit(emit, TurnStartEvent())


def prompt_text(text: str) -> UserMessage:
    return user_message(text)
