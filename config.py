"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import Optional

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Anthropic
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-5-20250929"

    # Halo PSA
    halo_api_url: str
    halo_client_id: str
    halo_client_secret: str

    # Proxy
    litellm_master_key: str

    # Application
    log_level: str = "INFO"

    # Context injection
    context_injection_enabled: bool = True
    context_cache_ttl: int = 0  # seconds (0 = no caching, always fetch fresh)

    # SOP KB article injection
    sop_kb_search_term: Optional[str] = "SOP"  # search term to find SOP articles (None to disable)
    max_sop_articles: int = 10
    max_sop_article_length: int = 2000

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
