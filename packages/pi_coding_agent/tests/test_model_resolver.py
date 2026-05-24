"""Tests for model pattern resolution."""

from pi_ai.model_registry import ModelRegistry
from pi_ai.types import Model, ModelCost

from pi_coding_agent.model_resolver import parse_model_pattern


def _registry_with_model() -> ModelRegistry:
    registry = ModelRegistry(models_json_path="/nonexistent/models.json")
    registry._models = [
        Model(
            id="claude-sonnet-4-5",
            name="Claude Sonnet 4.5",
            api="anthropic-messages",
            provider="anthropic",
            base_url="https://api.anthropic.com",
            reasoning=True,
            cost=ModelCost(),
        ),
    ]
    return registry


def test_parse_model_with_thinking_suffix() -> None:
    registry = _registry_with_model()
    result = parse_model_pattern("anthropic/claude-sonnet-4-5:high", registry)
    assert result is not None
    assert result.model_id == "claude-sonnet-4-5"
    assert result.thinking_level == "high"


def test_parse_exact_model() -> None:
    registry = _registry_with_model()
    result = parse_model_pattern("anthropic/claude-sonnet-4-5", registry)
    assert result is not None
    assert result.thinking_level is None
