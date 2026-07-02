"""Unit tests for priveil.judge.model.build_judge_model.

Tests cover:
- Built-in provider string returned as-is (anthropic/openai/bedrock prefix)
- Databricks / custom endpoint returns OpenAIChatModel
- Validation errors for missing required config
"""

import pytest

from priveil.judge.model import build_judge_client, build_judge_model
from priveil.settings import Settings


def _settings(**kwargs: object) -> Settings:
    """Build a Settings with env-file and spacy loading disabled."""
    return Settings(_env_file=None, spacy_model="en_core_web_sm", **kwargs)  # type: ignore[call-arg]


# ── Built-in provider path ────────────────────────────────────────────────────

def test_anthropic_string_returned_as_is() -> None:
    settings = _settings(judge_model="anthropic:claude-sonnet-4-6")
    result = build_judge_model(settings)
    assert result == "anthropic:claude-sonnet-4-6"


def test_openai_string_returned_as_is() -> None:
    settings = _settings(judge_model="openai:gpt-4o")
    result = build_judge_model(settings)
    assert result == "openai:gpt-4o"


def test_bedrock_string_returned_as_is() -> None:
    settings = _settings(judge_model="bedrock:anthropic.claude-sonnet-4-5-20250929-v1:0")
    result = build_judge_model(settings)
    assert result == "bedrock:anthropic.claude-sonnet-4-5-20250929-v1:0"


# ── Databricks / custom endpoint path ────────────────────────────────────────

def test_databricks_returns_openai_chat_model() -> None:
    from pydantic_ai.models.openai import OpenAIChatModel

    settings = _settings(
        judge_model="databricks-meta-llama-3-3-70b-instruct",
        judge_base_url="https://adb-123.azuredatabricks.net/serving-endpoints",
        judge_api_key="dapi-abc123",
    )
    result = build_judge_model(settings)
    assert isinstance(result, OpenAIChatModel)


def test_custom_endpoint_returns_openai_chat_model() -> None:
    from pydantic_ai.models.openai import OpenAIChatModel

    settings = _settings(
        judge_model="my-deployment",
        judge_base_url="https://custom.endpoint/v1",
        judge_api_key="secret",
    )
    result = build_judge_model(settings)
    assert isinstance(result, OpenAIChatModel)
    assert result.model_name == "my-deployment"


# ── Validation ────────────────────────────────────────────────────────────────

def test_no_model_raises_value_error() -> None:
    settings = _settings()  # judge_model defaults to None
    with pytest.raises(ValueError, match="PRIVEIL_JUDGE_MODEL must be set"):
        build_judge_model(settings)


def test_base_url_without_api_key_uses_local_default() -> None:
    settings = _settings(
        judge_model="some-deployment",
        judge_base_url="https://adb-123.azuredatabricks.net/serving-endpoints",
    )
    result = build_judge_model(settings)
    from pydantic_ai.models.openai import OpenAIChatModel
    assert isinstance(result, OpenAIChatModel)


def test_api_key_without_base_url_uses_builtin_path() -> None:
    """judge_api_key alone (no base_url) is harmless — treated as built-in provider."""
    settings = _settings(
        judge_model="anthropic:claude-sonnet-4-6",
        judge_api_key="ignored-without-base-url",
    )
    result = build_judge_model(settings)
    # Still the raw string — base_url is what triggers the custom path
    assert result == "anthropic:claude-sonnet-4-6"


def test_build_judge_client_with_base_url() -> None:
    settings = _settings(judge_model="openai:gpt-4o", judge_base_url="http://localhost:8001/v1")
    client = build_judge_client(settings)
    assert str(client.base_url) == "http://localhost:8001/v1/"
