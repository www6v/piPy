import json

from pi_ai.model_registry import ModelRegistry
from pi_ai.types import Model

from pi_coding_agent.auth.resolve import resolve_auth_for_model
from pi_coding_agent.auth.storage import AuthStorage


def test_auth_json_uses_bearer_when_auth_header_configured(tmp_path):
    models_path = tmp_path / "models.json"
    models_path.write_text(
        json.dumps(
            {
                "providers": {
                    "anthropic": {
                        "baseUrl": "https://proxy.example.com/private/llm",
                        "apiKey": "IGNORED",
                        "authHeader": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(
        json.dumps({"anthropic": {"type": "api_key", "key": "gateway-token"}}),
        encoding="utf-8",
    )
    registry = ModelRegistry(models_path)
    model = Model(
        id="claude-sonnet-4-6",
        name="test",
        api="anthropic-messages",
        provider="anthropic",
        base_url="https://proxy.example.com/private/llm",
    )
    api_key, headers = resolve_auth_for_model(
        registry,
        model,
        auth=AuthStorage(auth_path),
    )
    assert api_key is None
    assert headers is not None
    assert headers.get("Authorization") == "Bearer gateway-token"
