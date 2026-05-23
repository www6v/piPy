from pi_ai.providers.openai import events_from_openai_chunk, parse_sse_chunk
from pi_ai.types import AssistantMessage, Model, Usage


def test_parse_sse_chunk():
    assert parse_sse_chunk('data: {"choices":[]}') == {"choices": []}
    assert parse_sse_chunk("data: [DONE]") == {"done": True}
    assert parse_sse_chunk("") is None


def test_events_from_text_delta():
    model = Model(
        id="gpt-4o-mini",
        name="mini",
        api="openai",
        provider="openai",
        base_url="https://api.openai.com/v1",
    )
    partial = AssistantMessage(
        content=[],
        api="openai",
        provider="openai",
        model="gpt-4o-mini",
        usage=Usage(),
        stop_reason="stop",
    )
    chunk = {
        "choices": [{"delta": {"content": "hi"}, "finish_reason": None}],
    }
    partial, events = events_from_openai_chunk(
        chunk,
        model=model,
        partial=partial,
    )
    assert events[0].type == "text_delta"
    assert events[0].delta == "hi"
    assert partial.content[0].text == "hi"
