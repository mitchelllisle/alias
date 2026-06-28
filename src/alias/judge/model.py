"""Shared model factory for the judge layer.

Returns the right pydantic-ai model object depending on settings:

- ALIAS_JUDGE_BASE_URL unset → pass judge_model string directly to Agent;
  pydantic-ai resolves the provider prefix (e.g. 'anthropic:claude-sonnet-4-6').

- ALIAS_JUDGE_BASE_URL set → construct an OpenAIChatModel pointed at a custom
  OpenAI-compatible endpoint (e.g. Databricks Serving Endpoints, Azure AI,
  Ollama). ALIAS_JUDGE_MODEL becomes the deployment/model name on that endpoint
  and ALIAS_JUDGE_API_KEY is the bearer token (e.g. a Databricks PAT).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from pydantic_ai.models.openai import OpenAIChatModel

    from alias.settings import Settings

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
        ValueError: If judge_model is not set, or if judge_base_url is set
            without judge_api_key.
    """
    if not settings.judge_model:
        raise ValueError(
            "ALIAS_JUDGE_MODEL must be set. "
            "Use 'provider:model' format (e.g. 'anthropic:claude-sonnet-4-6') "
            "or a deployment name when ALIAS_JUDGE_BASE_URL is configured."
        )

    if settings.judge_base_url:
        if not settings.judge_api_key:
            raise ValueError(
                "ALIAS_JUDGE_API_KEY must be set when ALIAS_JUDGE_BASE_URL is configured "
                "(e.g. a Databricks personal access token)."
            )
        return _build_openai_compatible_model(settings)

    # Built-in provider — pydantic-ai resolves "anthropic:...", "openai:...", etc.
    return settings.judge_model


def _build_openai_compatible_model(settings: "Settings") -> "OpenAIChatModel":
    """Build an OpenAIChatModel for a custom OpenAI-compatible endpoint."""
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    client = AsyncOpenAI(
        base_url=settings.judge_base_url,
        api_key=settings.judge_api_key,
    )
    return OpenAIChatModel(
        model_name=settings.judge_model,  # type: ignore[arg-type]
        provider=OpenAIProvider(openai_client=client),
    )
