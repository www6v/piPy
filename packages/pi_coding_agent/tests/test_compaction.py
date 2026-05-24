"""Compaction unit tests."""

import pytest

from pi_ai.models import get_model
from pi_ai.providers.faux import faux_assistant_message, faux_text, register_faux_provider
from pi_ai.types import AssistantMessage, TextContent, Usage, UserMessage

from pi_coding_agent.compaction.compaction import find_cut_point, compact_session
from pi_coding_agent.session.serialize import message_to_dict


def _fixture_session() -> tuple[list[dict], list, list[str]]:
    filler = "x" * 200
    entries: list[dict] = []
    chronological = []
    ids: list[str] = []

    for turn in range(3):
        uid = f"id-user-{turn}"
        aid = f"id-asst-{turn}"
        ids.extend([uid, aid])
        user_msg = UserMessage(content=f"{filler} user-{turn} {filler}")
        asst_msg = AssistantMessage(
            content=[TextContent(text=f"{filler} asst-{turn} {filler}")],
            api="openai-completions",
            provider="anthropic",
            model="stub",
            usage=Usage(),
            stop_reason="stop",
        )
        chronological.append(user_msg)
        chronological.append(asst_msg)
        entries.append({
            "type": "message",
            "id": uid,
            "parentId": None,
            "message": message_to_dict(user_msg),
        })
        entries.append({
            "type": "message",
            "id": aid,
            "parentId": uid,
            "message": message_to_dict(asst_msg),
        })

    return entries, chronological, ids


@pytest.fixture
def compact_fixture() -> tuple[list[dict], list, list[str]]:
    return _fixture_session()


def test_find_cut_point_basic(compact_fixture: tuple[list[dict], list, list[str]]) -> None:
    entries, chronological, ids = compact_fixture
    iq = iter(chronological)
    mq = {
        row["id"]: next(iq)
        for row in entries
        if row.get("type") == "message" and isinstance(row.get("id"), str)
    }

    cut_id = find_cut_point(entries, 180, mq)

    assert cut_id is not None
    assert cut_id in ids


@pytest.mark.asyncio
async def test_compact_session_returns_summary_and_first_kept(
    compact_fixture: tuple[list[dict], list, list[str]],
) -> None:
    entries, chronological, ids = compact_fixture
    marker = "SYNTH_SUMMARY_MARKER_ABC123"

    register_faux_provider(
        models=[{"id": "compactor", "name": "Compactor"}],
        handler=lambda _ctx: faux_assistant_message([faux_text(marker)]),
    )

    model = get_model("faux", "compactor")
    iq = iter(chronological)
    by_id_compact = {
        row["id"]: next(iq)
        for row in entries
        if row.get("type") == "message" and isinstance(row.get("id"), str)
    }

    result = await compact_session(
        entries=entries,
        messages=chronological,
        model=model,
        api_key=None,
        keep_recent_tokens=180,
    )

    assert result.summary == marker

    assert find_cut_point(entries, 180, by_id_compact) == result.first_kept_entry_id
    assert result.first_kept_entry_id in ids


