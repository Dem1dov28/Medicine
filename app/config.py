from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values are read from the environment (prefix ``MKI_``)."""

    model_config = SettingsConfigDict(env_prefix="MKI_", env_file=".env", extra="ignore")

    # Local default keeps v0 runnable with zero external services (RFC-0001 §1).
    database_url: str = "sqlite+pysqlite:///./mki.db"

    # --- LLM via OpenRouter (RFC-0002) ---------------------------------------
    # When the key is empty, extraction and verification run in deterministic
    # stub mode (no network calls), so tests and local dev work offline.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Single model does extraction; a different-family ensemble verifies
    # (RFC-0002: extractor != verifier).
    extractor_model: str = "openai/gpt-5.1"
    # NoDecode: parse the raw env string ourselves (comma-separated), instead of
    # letting pydantic-settings try to JSON-decode it.
    verifier_models: Annotated[list[str], NoDecode] = [
        "anthropic/claude-sonnet-4.5",
        "google/gemini-2.5-pro",
        "openai/gpt-4o",
    ]

    # Voting: publish only when all models pass and mean confidence >= threshold.
    verify_threshold: float = 0.75

    @field_validator("verifier_models", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        # Allow MKI_VERIFIER_MODELS="a,b,c" in addition to JSON list form.
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openrouter_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
