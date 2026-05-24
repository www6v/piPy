import pytest

from pi_ai.providers.google import _extract_candidate_parts, stream_google
from pi_ai.types import Context, Model


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload):
        self._payload = payload

    async def post(self, url, headers=None, json=None):  # noqa: A002
        del url, headers, json
        return _FakeResponse(self._payload)


def _google_model() -> Model:
    return Model(
        id="gemini-2.0-flash",
        name="Gemini",
        api="google-generate-content",
        provider="google",
        base_url="https://generativelanguage.googleapis.com",
    )


def test_extract_candidate_parts_text_and_function_call() -> None:
    payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "hello"},
                        {"functionCall": {"name": "read", "args": {"path": "a.txt"}}},
                    ]
                }
            }
        ]
    }
    text, calls = _extract_candidate_parts(payload)
    assert text == "hello"
    assert len(calls) == 1
    assert calls[0].name == "read"
    assert calls[0].arguments == {"path": "a.txt"}


@pytest.mark.asyncio
async def test_stream_google_missing_key_returns_error(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    model = _google_model()
    events = []
    async for event in stream_google(model, Context()):
        events.append(event)
    assert events[-1].type == "done"
    assert events[-1].message.stop_reason == "error"
    assert "GEMINI_API_KEY not set" in (events[-1].message.error_message or "")


@pytest.mark.asyncio
async def test_stream_google_yields_text_delta_with_fake_client() -> None:
    payload = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "ok"}],
                }
            }
        ]
    }
    model = _google_model()
    events = []
    async for event in stream_google(
        model,
        Context(),
        api_key="test-key",
        client=_FakeClient(payload),
    ):
        events.append(event)
    assert any(e.type == "text_delta" and e.delta == "ok" for e in events)
    assert events[-1].type == "done"
    assert events[-1].message.stop_reason == "stop"
