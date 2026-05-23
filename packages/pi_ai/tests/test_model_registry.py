import json

import pi_ai.model_registry as registry_module
from pi_ai.model_registry import ModelRegistry


def test_registry_merges_custom_model(tmp_path, monkeypatch):
    config = {
        "providers": {
            "dashscope": {
                "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api": "openai-completions",
                "apiKey": "DASHSCOPE_API_KEY",
                "models": [{"id": "qwen-plus"}],
            },
        },
    }
    path = tmp_path / "models.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")

    reg = ModelRegistry(path)
    model = reg.find("dashscope", "qwen-plus")
    assert model is not None
    assert model.api == "openai-completions"
    api_key, _headers = reg.resolve_auth(model)
    assert api_key == "test-key"


def test_registry_applies_anthropic_base_url_override(tmp_path):
    config = {
        "providers": {
            "anthropic": {
                "baseUrl": "https://proxy.example.com",
            },
        },
    }
    path = tmp_path / "models.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    reg = ModelRegistry(path)
    model = reg.find("anthropic", "claude-sonnet-4-5")
    assert model is not None
    assert model.base_url == "https://proxy.example.com"


def test_get_model_uses_registry(tmp_path, monkeypatch):
    config = {
        "providers": {
            "dashscope": {
                "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api": "openai-completions",
                "apiKey": "DASHSCOPE_API_KEY",
                "models": [{"id": "qwen-plus"}],
            },
        },
    }
    path = tmp_path / "models.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    registry_module._default_registry = ModelRegistry(path)

    from pi_ai.models import get_model

    model = get_model("dashscope", "qwen-plus")
    assert model.id == "qwen-plus"
