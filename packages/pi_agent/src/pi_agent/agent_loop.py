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
    UserMessage,
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
        call_args = dict(tool_call.arguments)
        await _emit(
            emit,
            ToolExecutionStartEvent(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                args=call_args,
            ),
        )
        if config.on_tool_call is not None:
            hook_result = await _maybe_await(
                config.on_tool_call(tool_call.name, tool_call.id, call_args),
            )
            if isinstance(hook_result, dict):
                if hook_result.get("block"):
                    reason = str(hook_result.get("reason") or "Blocked by extension")
                    result = AgentToolResult(
                        content=[TextContent(text=reason)],
                        is_error=True,
                    )
                    await _emit(
                        emit,
                        ToolExecutionEndEvent(
                            tool_call_id=tool_call.id,
                            tool_name=tool_call.name,
                            result=result,
                            is_error=True,
                        ),
                    )
                    message = ToolResultMessage(
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                        content=result.content,
                        is_error=True,
                        timestamp=int(time.time() * 1000),
                    )
                    return message, result
                if isinstance(hook_result.get("args"), dict):
                    call_args = dict(hook_result["args"])
        if tool is None:
            result = AgentToolResult(
                content=[TextContent(text=f"Unknown tool: {tool_call.name}")],
                is_error=True,
            )
        else:
            _validate_args(tool, call_args)
            try:
                result = await tool.execute(tool_call.id, call_args, signal)
            except Exception as exc:
                result = AgentToolResult(
                    content=[TextContent(text=str(exc))],
                    is_error=True,
                )
        if config.on_tool_result is not None:
            hook_result = await _maybe_await(
                config.on_tool_result(tool_call.name, tool_call.id, call_args, result),
            )
            if isinstance(hook_result, AgentToolResult):
                result = hook_result
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
        request_headers=config.request_headers,
        thinking_level=config.thinking_level,
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
    steer_fn = config.get_steering_messages
    follow_fn = config.get_follow_up_messages

    async def pull_steering() -> list[AgentMessage]:
        if steer_fn is None:
            return []
        return await steer_fn()

    async def pull_follow_ups() -> list[AgentMessage]:
        if follow_fn is None:
            return []
        return await follow_fn()

    await _emit(emit, AgentStartEvent())

    outer_continue = True
    first_turn = True

    while outer_continue:
        outer_continue = False

        steer_at_outer = await pull_steering()

        await _emit(emit, TurnStartEvent())

        if first_turn:
            for prompt in prompts:
                await _emit(emit, MessageStartEvent(message=prompt))
                await _emit(emit, MessageEndEvent(message=prompt))
            first_turn = False

        for message in steer_at_outer:
            current.messages.append(message)
            new_messages.append(message)
            await _emit(emit, MessageStartEvent(message=message))
            await _emit(emit, MessageEndEvent(message=message))

        inner_continue = True
        while inner_continue:
            if config.on_context is not None:
                rewritten = await _maybe_await(config.on_context(list(current.messages)))
                if isinstance(rewritten, list):
                    current.messages = rewritten
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
                await _emit(
                    emit,
                    TurnEndEvent(message=assistant, tool_results=[]),
                )
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

            await _emit(
                emit,
                TurnEndEvent(message=assistant, tool_results=tool_results),
            )

            has_tool_calls = any(
                block.type == "toolCall" for block in assistant.content
            )
            if has_tool_calls and not should_stop:
                steer_after_tools = await pull_steering()
                for message in steer_after_tools:
                    current.messages.append(message)
                    new_messages.append(message)
                    await _emit(emit, MessageStartEvent(message=message))
                    await _emit(emit, MessageEndEvent(message=message))

                await _emit(emit, TurnStartEvent())
                continue

            inner_continue = False

        follow_batch = await pull_follow_ups()
        if follow_batch:
            for message in follow_batch:
                current.messages.append(message)
                new_messages.append(message)
                await _emit(emit, MessageStartEvent(message=message))
                await _emit(emit, MessageEndEvent(message=message))
            outer_continue = True

    await _emit(emit, AgentEndEvent(messages=new_messages))
    return new_messages


def prompt_text(text: str) -> UserMessage:
    return user_message(text)
