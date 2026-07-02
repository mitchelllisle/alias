"""Shared model/client factories for the judge layer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIChatModel

    from priveil.settings import Settings

# pydantic-ai accepts str | Model for the agent's model parameter.
JudgeModel = Union[str, "OpenAIChatModel"]


def build_judge_model(settings: "Settings") -> JudgeModel:
    """Return the appropriate pydantic-ai model for the judge layer.

    Args:
        settings: Application settings.

    Returns:
        A provider:model string for built-in providers, or an OpenAIChatModel
        instance configured for a custom OpenAI-compatible endpoint.

    Raises:
        ValueError: If judge_model is not set.
    """
    if not settings.judge_model:
        raise ValueError(
            "PRIVEIL_JUDGE_MODEL must be set. "
            "Use 'provider:model' format (e.g. 'anthropic:claude-sonnet-4-6') "
            "or a deployment name when PRIVEIL_JUDGE_BASE_URL is configured."
        )

    if settings.judge_base_url:
        model_name = settings.judge_model
        assert model_name is not None  # validated at top of this function
        api_key = settings.judge_api_key.get_secret_value() if settings.judge_api_key else "local"
        return _build_openai_compatible_model(
            model_name=model_name,
            base_url=settings.judge_base_url,
            api_key=api_key,
        )

    # Built-in provider — pydantic-ai resolves "anthropic:...", "openai:...", etc.
    model_name = settings.judge_model
    assert model_name is not None  # validated at top of this function
    return model_name


def _build_openai_compatible_model(model_name: str, base_url: str, api_key: str) -> "OpenAIChatModel":
    """Build an OpenAIChatModel for a custom OpenAI-compatible endpoint.

    Args:
        model_name: Validated deployment/model name.
        base_url: The endpoint base URL.
        api_key: Bearer token, already extracted from SecretStr by the caller.
    """
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    return OpenAIChatModel(
        model_name=model_name,
        provider=OpenAIProvider(openai_client=client),
    )


def build_judge_client(settings: "Settings") -> "AsyncOpenAI":
    """Build an AsyncOpenAI client for the span-verdict refiner."""
    from openai import AsyncOpenAI

    if settings.judge_base_url:
        api_key = settings.judge_api_key.get_secret_value() if settings.judge_api_key else "local"
        return AsyncOpenAI(base_url=settings.judge_base_url, api_key=api_key)

    if settings.judge_api_key:
        return AsyncOpenAI(api_key=settings.judge_api_key.get_secret_value())
    return AsyncOpenAI()
