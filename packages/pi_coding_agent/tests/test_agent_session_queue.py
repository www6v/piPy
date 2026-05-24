"""AgentSession steer/follow_up queue semantics."""

from __future__ import annotations

import asyncio

import pytest
from pi_agent.agent import AgentBusyError
from pi_ai.providers import faux as faux_mod
from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)

from pi_coding_agent.agent_session import AgentSession
from pi_coding_agent.sdk import CreateAgentSessionOptions, create_agent_session


async def _make_queue_session(base: pytest.TempPathFactory) -> AgentSession:
    register_faux_provider(
        models=[{"id": "queue-test", "name": "queue-test"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("ack")]),
    )
    faux_mod.set_faux_responses(
        [faux_assistant_message([faux_text("ack")])],
    )
    result = await create_agent_session(
        CreateAgentSessionOptions(
            cwd=base.mktemp("queue"),
            model="faux/queue-test",
            provider="faux",
            tools=[],
            in_memory=True,
            no_context_files=True,
        )
    )
    return result.session


def _simulate_streaming(session: AgentSession) -> asyncio.Task:
    blocker = asyncio.create_task(asyncio.sleep(3600.0))
    session._agent._run_task = blocker
    return blocker


@pytest.mark.asyncio
async def test_prompt_steering_behavior_enqueues_when_busy(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    session = await _make_queue_session(tmp_path_factory)
    blocker = _simulate_streaming(session)
    try:
        out = await session.prompt(
            "steer-msg",
            streaming_behavior="steer",
        )
        assert out == []
        assert session.agent.steering_queue.peek_texts() == ["steer-msg"]
    finally:
        blocker.cancel()
        try:
            await blocker
        except asyncio.CancelledError:
            pass
        session._agent._run_task = None


@pytest.mark.asyncio
async def test_prompt_follow_up_behavior_enqueues_when_busy(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    session = await _make_queue_session(tmp_path_factory)
    blocker = _simulate_streaming(session)
    try:
        out = await session.prompt(
            "fu-msg",
            streaming_behavior="followUp",
        )
        assert out == []
        assert session.agent.follow_up_queue.peek_texts() == ["fu-msg"]
    finally:
        blocker.cancel()
        try:
            await blocker
        except asyncio.CancelledError:
            pass
        session._agent._run_task = None


@pytest.mark.asyncio
async def test_prompt_while_busy_without_behavior_raises_busy(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    session = await _make_queue_session(tmp_path_factory)
    blocker = _simulate_streaming(session)
    try:
        with pytest.raises(AgentBusyError):
            await session.prompt("no-behaviour")
    finally:
        blocker.cancel()
        try:
            await blocker
        except asyncio.CancelledError:
            pass
        session._agent._run_task = None


@pytest.mark.asyncio
async def test_get_rpc_state_pending_and_modes(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    session = await _make_queue_session(tmp_path_factory)
    session.follow_up("f1")
    session.steer("s1")

    raw = session.get_rpc_state()

    assert raw["pendingMessageCount"] >= 2
    assert raw["steeringMode"] in ("all", "one-at-a-time")
    assert raw["followUpMode"] in ("all", "one-at-a-time")


@pytest.mark.asyncio
async def test_set_steering_and_follow_modes_visible_in_state(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    session = await _make_queue_session(tmp_path_factory)
    session.set_steering_mode("all")
    session.set_follow_up_mode("one-at-a-time")
    snap = session.get_rpc_state()
    assert snap["steeringMode"] == "all"
    assert snap["followUpMode"] == "one-at-a-time"


@pytest.mark.asyncio
async def test_subscribe_all_receives_queue_update_on_steer(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    session = await _make_queue_session(tmp_path_factory)
    received: list[dict[str, object]] = []

    async def on_all(event: object) -> None:
        if isinstance(event, dict) and event.get("type") == "queue_update":
            received.append(dict(event))

    unsub = session.subscribe_all(on_all)
    try:
        session.steer("line-a")
        await session.flush_queue_broadcast()
    finally:
        unsub()

    assert received
    last = received[-1]
    assert last["steering"] == ["line-a"]
