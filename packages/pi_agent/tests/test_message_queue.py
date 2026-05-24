"""Tests for PendingMessageQueue."""

from __future__ import annotations

from pi_agent.message_queue import PendingMessageQueue, QueueMode
from pi_agent.types import user_message


def test_drain_one_at_a_time() -> None:
    q = PendingMessageQueue(mode="one-at-a-time")
    q.enqueue(user_message("a"))
    q.enqueue(user_message("b"))
    batch1 = q.drain()
    batch2 = q.drain()
    assert len(batch1) == 1
    assert len(batch2) == 1
    assert batch1[0].content == "a"
    assert batch2[0].content == "b"
    assert not q.has_items


def test_drain_all() -> None:
    q = PendingMessageQueue(mode="all")
    q.enqueue(user_message("x"))
    q.enqueue(user_message("y"))
    drained = q.drain()
    assert len(drained) == 2
    assert drained[0].content == "x"
    assert drained[1].content == "y"
    assert not q.has_items


def test_peek_texts_user_only_and_clear() -> None:
    from pi_ai.providers.faux import faux_assistant_message, faux_text

    q = PendingMessageQueue(mode="all")
    q.enqueue(user_message("hello"))
    q.enqueue(faux_assistant_message([faux_text("ignored")]))
    previews = q.peek_texts()
    assert previews == ["hello"]
    assert q.has_items

    q.clear()
    assert not q.has_items
    assert q.drain() == []


def test_queue_mode_assignment() -> None:
    q: PendingMessageQueue = PendingMessageQueue(mode="all")
    q.mode = "one-at-a-time"
    q.enqueue(user_message("1"))
    q.enqueue(user_message("2"))
    assert len(q.drain()) == 1
    mode: QueueMode = q.mode
    assert mode == "one-at-a-time"
