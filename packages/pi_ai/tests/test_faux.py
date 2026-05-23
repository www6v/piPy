import pytest

from pi_ai.models import get_model
from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
)
from pi_ai.stream import stream_simple
from pi_ai.types import Context


@pytest.mark.asyncio
async def test_faux_streams_text():
    reg = register_faux_provider(
        provider_id="faux",
        models=[{"id": "test", "name": "Test"}],
        handler=lambda _req: faux_assistant_message([faux_text("ok")]),
    )
    model = get_model("faux", "test")
    chunks = []
    stream = stream_simple(model, context=Context())
    async for event in stream:
        if event.type == "text_delta":
            chunks.append(event.delta)
    assert "".join(chunks) == "ok"
    reg.dispose()
