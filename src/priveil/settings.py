from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All vars are prefixed with PRIVEIL_ (e.g. PRIVEIL_DEBUG=true).
    """

    model_config = SettingsConfigDict(
        env_prefix="PRIVEIL_",
        env_file=".env",
        extra="ignore",
    )

    debug: bool = False
    # en_core_web_sm is the default (dev/test). Production deployments that
    # need higher accuracy should set PRIVEIL_SPACY_MODEL=en_core_web_lg and
    # ensure the model is available in the container.
    spacy_model: str = "en_core_web_sm"
    executor_max_workers: int = 4
    # LLM judge — set PRIVEIL_JUDGE_MODEL to enable refinement and /assess.
    # When unset: mode='judge' falls back to 'fast' (with surfaced mode_used); /assess returns 503.
    judge_model: str | None = None
    judge_temperature: float = 0.0
    # Custom OpenAI-compatible endpoint (e.g. local vLLM).
    # When set, judge_model is treated as the endpoint model/deployment name.
    judge_base_url: str | None = None
    judge_api_key: SecretStr | None = None
    # Presidio's default recogniser confidence floor is 0.85; anything at or above
    # that is treated as certain and bypasses the judge. Set below 0.85 to send
    # Presidio's default-confidence detections to the judge for verification.
    judge_score_threshold: float = 0.7
    judge_eligible_types: frozenset[str] = frozenset({"PERSON", "LOCATION", "DATE_TIME", "AU_BSB", "AU_ACCOUNT_NUMBER"})
    judge_context_chars: int = 60
    judge_timeout_ms: int = 250
    judge_max_tokens: int = 64
    # Key used for HMAC audit hashes. Set this explicitly for stable hashes across
    # restarts and environments where audit correlation matters.
    audit_hash_key: SecretStr | None = None
