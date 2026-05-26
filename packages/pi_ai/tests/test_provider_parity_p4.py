import pytest

from pi_ai.model_registry import get_registry
from pi_ai.stream import stream_simple
from pi_ai.types import Context, Model


def test_registry_includes_azure_and_bedrock() -> None:
    registry = get_registry(refresh=True)
    providers = {model.provider for model in registry.get_all()}

    assert "azure-openai-responses" in providers
    assert "amazon-bedrock" in providers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("api", "provider"),
    [
        ("azure-openai-responses", "azure-openai-responses"),
        ("amazon-bedrock", "amazon-bedrock"),
    ],
)
async def test_new_provider_streams_emit_explicit_placeholder_errors(
    api: str,
    provider: str,
) -> None:
    model = Model(
        id="parity-test-model",
        name="Parity Test Model",
        api=api,
        provider=provider,
        base_url="https://example.test",
    )

    events = []
    async for event in stream_simple(model, Context()):
        events.append(event)

    assert [event.type for event in events] == ["start", "error", "done"]
    assert "not implemented" in (events[-1].message.error_message or "").lower()
