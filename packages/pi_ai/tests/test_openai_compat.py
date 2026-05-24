"""OpenAI compat flags on Model."""

from pi_ai.providers.openai import _messages_for_api, _system_role
from pi_ai.types import Context, Model, ModelCost


def test_developer_role_when_supported() -> None:
    model = Model(
        id="gpt",
        name="gpt",
        api="openai-completions",
        provider="openai",
        base_url="https://api.openai.com/v1",
        reasoning=True,
        supports_developer_role=True,
        cost=ModelCost(),
    )
    assert _system_role(model) == "developer"
    messages = _messages_for_api(Context(system_prompt="hi", messages=[]), model)
    assert messages[0]["role"] == "developer"


def test_system_role_when_compat_disabled() -> None:
    model = Model(
        id="qwen",
        name="qwen",
        api="openai-completions",
        provider="dashscope",
        base_url="https://example.com/v1",
        reasoning=True,
        supports_developer_role=False,
        cost=ModelCost(),
    )
    assert _system_role(model) == "system"
    messages = _messages_for_api(Context(system_prompt="hi", messages=[]), model)
    assert messages[0]["role"] == "system"
