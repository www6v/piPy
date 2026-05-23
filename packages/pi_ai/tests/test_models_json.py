import json

from pi_ai.models_json import load_models_json, strip_json_comments


def test_strip_json_comments():
    raw = """
    {
      // provider config
      "providers": {
        "dashscope": {
          "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
          "api": "openai-completions",
          "apiKey": "DASHSCOPE_API_KEY",
          "compat": { "thinkingFormat": "qwen" },
          "models": [
            { "id": "qwen-plus" },
          ],
        },
      },
    }
    """
    parsed = json.loads(strip_json_comments(raw))
    assert "providers" in parsed


def test_load_dashscope_provider(tmp_path):
    config = {
        "providers": {
            "dashscope": {
                "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api": "openai-completions",
                "apiKey": "DASHSCOPE_API_KEY",
                "compat": {"thinkingFormat": "qwen"},
                "models": [
                    {"id": "qwen-plus", "name": "Qwen Plus"},
                ],
            },
        },
    }
    path = tmp_path / "models.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    loaded = load_models_json(str(path))
    assert loaded.error is None
    assert len(loaded.custom_models) == 1
    model = loaded.custom_models[0]
    assert model.provider == "dashscope"
    assert model.api == "openai-completions"
    assert model.thinking_format == "qwen"
    assert loaded.provider_configs["dashscope"].api_key == "DASHSCOPE_API_KEY"


def test_builtin_provider_override(tmp_path):
    config = {
        "providers": {
            "anthropic": {
                "baseUrl": "https://proxy.example.com",
            },
        },
    }
    path = tmp_path / "models.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    loaded = load_models_json(str(path))
    assert loaded.provider_overrides["anthropic"].base_url == "https://proxy.example.com"
