"""Bounded auto-retries via ``faux/retry-test``."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pi_ai.providers.faux import faux_assistant_message, register_faux_provider
from pi_ai.types import AssistantMessage, Context

from pi_coding_agent.retry import compute_retry_delay_ms, is_retryable_error
from pi_coding_agent.sdk import CreateAgentSessionOptions, create_agent_session
from pi_coding_agent.settings import RetrySettings, Settings


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("HTTP 529 overloaded", True),
        ("rate limit exceeded", True),
        ("status 429", True),
        ("Server returned 503", True),
        ("ECONNRESET from peer", True),
        ("socket timeout connecting upstream", True),
        ("prompt context overflow exceeded", False),
        ("maximum context exceeded overflow", False),
        ("something failed mysteriously xyz", False),
    ],
)
def test_is_retryable_error_examples(text: str, expected: bool) -> None:
    msg = faux_assistant_message(
        "",
        stop_reason="error",
        error_message=text,
    )
    assert is_retryable_error(msg, 128000) == expected


def test_compute_retry_delay_caps() -> None:
    assert compute_retry_delay_ms(0, 1000) == 1000
    assert compute_retry_delay_ms(1, 1000) == 2000
    giant = compute_retry_delay_ms(40, 1_000_000)
    assert giant == 60 * 60 * 1000


async def _session_with_retries(
    tmp_path: Path,
    *,
    monkeypatch: pytest.MonkeyPatch,
    base_delay_ms: int,
):
    retries = RetrySettings(
        enabled=True,
        max_retries=3,
        base_delay_ms=base_delay_ms,
    )
    settings = Settings(retry=retries)

    def fake_load_settings(cwd=None):
        del cwd  # Mirrors ``load_settings`` signature.
        return settings

    monkeypatch.setattr(
        "pi_coding_agent.sdk.load_settings",
        fake_load_settings,
    )
    result = await create_agent_session(
        CreateAgentSessionOptions(
            model="faux/retry-test",
            provider="faux",
            tools=[],
            in_memory=True,
            cwd=tmp_path,
        )
    )
    return result.session, settings


@pytest.mark.asyncio
async def test_auto_retry_emit_events_and_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _settings = await _session_with_retries(
        tmp_path,
        monkeypatch=monkeypatch,
        base_delay_ms=1,
    )
    bottled: list[dict] = []

    def capture(event):
        if isinstance(event, dict):
            bottled.append(event)

    session.subscribe_all(capture)
    await session.prompt("ping phase")
    await session.wait_for_idle()

    kinds = [item["type"] for item in bottled]
    assert "auto_retry_start" in kinds
    assert "auto_retry_end" in kinds
    assistants = [
        msg for msg in session.messages if isinstance(msg, AssistantMessage)
    ]
    assert assistants[-1].stop_reason == "stop"
    text_blocks = [
        blk.text for blk in assistants[-1].content if blk.type == "text"
    ]
    assert "recovery-ok" in "".join(text_blocks)


@pytest.mark.asyncio
async def test_abort_retry_cancels_backoff(tmp_path: Path, monkeypatch) -> None:
    session, _settings = await _session_with_retries(
        tmp_path,
        monkeypatch=monkeypatch,
        base_delay_ms=60_000,
    )
    bottled: list[dict] = []

    def capture(event):
        if isinstance(event, dict):
            bottled.append(event)

    session.subscribe_all(capture)

    async def trigger_abort():
        await asyncio.sleep(0.05)
        session.abort_retry()

    waiter = asyncio.create_task(trigger_abort())
    await session.prompt("ping abort")
    await waiter
    await session.wait_for_idle()

    endings = [
        item for item in bottled if item.get("type") == "auto_retry_end"
    ]
    assert any(entry.get("cancelled") for entry in endings)


@pytest.mark.asyncio
async def test_auto_retry_budget_exhaustion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retries = RetrySettings(enabled=True, max_retries=2, base_delay_ms=1)
    settings = Settings(retry=retries)

    monkeypatch.setattr(
        "pi_coding_agent.sdk.load_settings",
        lambda cwd=None: settings,
    )
    monkeypatch.setattr(
        "pi_coding_agent.sdk._ensure_faux_model",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "pi_coding_agent.sdk._precreate_unknown_faux_model",
        lambda *_args, **_kwargs: None,
    )

    def doomed(_ctx: Context) -> AssistantMessage:
        return faux_assistant_message(
            "",
            stop_reason="error",
            error_message="HTTP 503 service unavailable",
        )

    register_faux_provider(
        models=[{"id": "retry-doom", "name": "retry-doom"}],
        handler=doomed,
    )
    result = await create_agent_session(
        CreateAgentSessionOptions(
            model="faux/retry-doom",
            provider="faux",
            tools=[],
            in_memory=True,
            cwd=tmp_path,
        )
    )
    session = result.session
    bottled: list[dict] = []

    def capture(event):
        if isinstance(event, dict):
            bottled.append(event)

    session.subscribe_all(capture)
    await session.prompt("always fails")
    await session.wait_for_idle()

    starters = sum(
        1 for row in bottled if row.get("type") == "auto_retry_start"
    )
    assert starters == retries.max_retries

