"""High-level Agent API."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pi_agent.agent_loop import run_agent_loop
from pi_agent.message_queue import PendingMessageQueue, QueueMode
from pi_agent.messages import convert_to_llm
from pi_agent.types import (
    AgentContext,
    AgentEvent,
    AgentLoopConfig,
    AgentMessage,
    AgentState,
    AgentTool,
    AgentToolResult,
    user_message,
)
from pi_ai.types import Context, Model, Tool


class AgentBusyError(RuntimeError):
    """Raised when starting a prompt while another run is in progress."""


class Agent:
    def __init__(
        self,
        *,
        system_prompt: str = "",
        model: Model,
        tools: list[AgentTool] | None = None,
        api_key: str | None = None,
        request_headers: dict[str, str] | None = None,
        initial_messages: list[AgentMessage] | None = None,
        convert_to_llm_fn: Callable[..., Any] | None = None,
        thinking_level: str | None = None,
        steering_mode: QueueMode = "all",
        follow_up_mode: QueueMode = "all",
        on_context: Callable[
            [list[AgentMessage]],
            list[AgentMessage] | None | Awaitable[list[AgentMessage] | None],
        ]
        | None = None,
        on_tool_call: Callable[
            [str, str, dict[str, Any]],
            dict[str, Any] | None | Awaitable[dict[str, Any] | None],
        ]
        | None = None,
        on_tool_result: Callable[
            [str, str, dict[str, Any], AgentToolResult],
            AgentToolResult | None | Awaitable[AgentToolResult | None],
        ]
        | None = None,
    ) -> None:
        self._system_prompt = system_prompt
        self._model = model
        self._tools = list(tools or [])
        self._messages: list[AgentMessage] = list(initial_messages or [])
        self._api_key = api_key
        self._request_headers = request_headers
        self._thinking_level = thinking_level
        self._convert_to_llm = convert_to_llm_fn or convert_to_llm
        self._on_context = on_context
        self._on_tool_call = on_tool_call
        self._on_tool_result = on_tool_result
        self.steering_queue = PendingMessageQueue(mode=steering_mode)
        self.follow_up_queue = PendingMessageQueue(mode=follow_up_mode)
        self._subscribers: list[
            Callable[[AgentEvent], None | Awaitable[None]]
        ] = []
        self._abort_event: asyncio.Event | None = None
        self._run_task: asyncio.Task[list[AgentMessage]] | None = None
        self._idle = asyncio.Event()
        self._idle.set()

    @property
    def state(self) -> AgentState:
        return AgentState(
            system_prompt=self._system_prompt,
            model=self._model,
            tools=list(self._tools),
            messages=list(self._messages),
            is_streaming=self._run_task is not None,
        )

    def subscribe(
        self,
        listener: Callable[[AgentEvent], None | Awaitable[None]],
    ) -> Callable[[], None]:
        self._subscribers.append(listener)

        def unsubscribe() -> None:
            self._subscribers.remove(listener)

        return unsubscribe

    async def _emit(self, event: AgentEvent) -> None:
        for listener in self._subscribers:
            result = listener(event)
            if asyncio.iscoroutine(result):
                await result

    def steer(self, text: str) -> None:
        """Enqueue a user steering message drained during tool rounds."""
        self.steering_queue.enqueue(user_message(text))

    def follow_up(self, text: str) -> None:
        """Enqueue follow-up drained when the assistant would stop."""
        self.follow_up_queue.enqueue(user_message(text))

    async def prompt(self, text: str) -> list[AgentMessage]:
        from pi_agent.agent_loop import prompt_text

        if self._run_task is not None:
            raise AgentBusyError("Agent already running")

        return await self._run([prompt_text(text)])

    async def continue_run(self) -> list[AgentMessage]:
        """Run the loop again using queued steering/follow-ups (no prompt)."""
        if self._run_task is not None:
            raise AgentBusyError("Agent already running")

        return await self._run([])

    async def _run(self, prompts: list[AgentMessage]) -> list[AgentMessage]:
        if self._run_task is not None:
            raise AgentBusyError("Agent already running")
        self._abort_event = asyncio.Event()
        self._idle.clear()

        async def emit(event: AgentEvent) -> None:
            await self._emit(event)

        async def get_steering_messages() -> list[AgentMessage]:
            return self.steering_queue.drain()

        async def get_follow_up_messages() -> list[AgentMessage]:
            return self.follow_up_queue.drain()

        config = AgentLoopConfig(
            model=self._model,
            convert_to_llm=self._convert_to_llm,
            api_key=self._api_key,
            request_headers=self._request_headers,
            thinking_level=self._thinking_level,
            get_steering_messages=get_steering_messages,
            get_follow_up_messages=get_follow_up_messages,
            on_context=self._on_context,
            on_tool_call=self._on_tool_call,
            on_tool_result=self._on_tool_result,
        )
        context = AgentContext(
            system_prompt=self._system_prompt,
            messages=list(self._messages),
            tools=[
                Tool(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.parameters,
                )
                for tool in self._tools
            ],
        )

        async def runner() -> list[AgentMessage]:
            return await run_agent_loop(
                prompts,
                context,
                config,
                emit,
                agent_tools=self._tools,
                signal=self._abort_event,
            )

        self._run_task = asyncio.create_task(runner())
        try:
            new_messages = await self._run_task
            self._messages.extend(new_messages)
            return new_messages
        finally:
            self._run_task = None
            self._abort_event = None
            self._idle.set()

    def abort(self) -> None:
        if self._abort_event is not None:
            self._abort_event.set()

    async def wait_for_idle(self) -> None:
        await self._idle.wait()
        if self._run_task is not None:
            await self._run_task
