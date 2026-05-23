from pi_ai.providers.openai import (
    _OpenAIStreamState,
    _apply_openai_delta,
    events_from_openai_chunk,
    parse_sse_chunk,
)
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
    state = _OpenAIStreamState()
    chunk = {
        "choices": [{"delta": {"content": "hi"}, "finish_reason": None}],
    }
    partial, events = events_from_openai_chunk(
        chunk,
        model=model,
        partial=partial,
        state=state,
    )
    assert events[0].type == "text_delta"
    assert events[0].delta == "hi"
    assert partial.content[0].text == "hi"


def test_tool_calls_merge_by_index():
    state = _OpenAIStreamState()
    events_a = _apply_openai_delta(
        state,
        {
            "tool_calls": [
                {
                    "index": 0,
                    "id": "call_1",
                    "function": {"name": "read", "arguments": '{"path":'},
                }
            ]
        },
    )
    events_b = _apply_openai_delta(
        state,
        {
            "tool_calls": [
                {
                    "index": 0,
                    "function": {"arguments": ' "x.txt"}'},
                },
                {
                    "index": 1,
                    "id": "call_2",
                    "function": {"name": "bash", "arguments": "{}"},
                },
            ]
        },
    )
    assert events_a
    assert events_b
    assert len(state.tool_calls) == 2
    assert state.tool_calls[0].name == "read"
    assert state.tool_calls[0].arguments == {"path": "x.txt"}
    assert state.tool_calls[1].name == "bash"
