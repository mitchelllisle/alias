from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All vars are prefixed with ALIAS_ (e.g. ALIAS_DEBUG=true).
    """

    model_config = SettingsConfigDict(
        env_prefix="ALIAS_",
        env_file=".env",
        extra="ignore",
    )

    debug: bool = False
    # en_core_web_sm is the default (dev/test). Production deployments that
    # need higher accuracy should set ALIAS_SPACY_MODEL=en_core_web_lg and
    # ensure the model is available in the container.
    spacy_model: str = "en_core_web_sm"
    executor_max_workers: int = 4
    # LLM judge — set ALIAS_JUDGE_MODEL to enable refinement and /assess.
    # When unset: mode='judge' degrades silently to 'fast'; /assess returns 503.
    judge_model: str | None = None
    judge_temperature: float = 0.0
    # Custom OpenAI-compatible endpoint (e.g. Databricks Serving Endpoints).
    # When set, judge_model is the deployment name and judge_api_key is required.
    # When unset, judge_model uses pydantic-ai's provider:model string (e.g. anthropic:...).
    judge_base_url: str | None = None
    judge_api_key: str | None = None
