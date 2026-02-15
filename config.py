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

    # Azure Entra ID OAuth (for MCP remote access from Claude.ai/mobile)
    entra_tenant_id: Optional[str] = None
    entra_client_id: Optional[str] = None
    public_base_url: str = "https://haloclaude-proxy.ashysky-0dacd66d.westus.azurecontainerapps.io"

    # Application
    log_level: str = "INFO"

    # Context injection
    context_injection_enabled: bool = True
    context_cache_ttl: int = 0  # seconds (0 = no caching, always fetch fresh)

    # SOP KB article injection
    sop_kb_search_term: Optional[str] = "SOP"  # search term to find SOP articles (None to disable)
    sop_kb_filter_tag: Optional[str] = "ai-context"  # only inject articles with this tag (None = all matches)
    max_sop_articles: int = 10
    max_sop_article_length: int = 2000
    max_contract_doc_length: int = 0  # max characters of extracted PDF text per contract (0 = disabled)

    # Triage pipeline
    triage_enabled: bool = True
    triage_model: str = "claude-opus-4-6"

    # Ticket review pipeline
    review_enabled: bool = True
    review_model: str = "claude-haiku-4-5-20251001"

    # NinjaRMM / NinjaOne
    ninja_enabled: bool = False
    ninja_api_url: str = "https://app.ninjarmm.com"
    ninja_client_id: Optional[str] = None
    ninja_client_secret: Optional[str] = None
    ninja_scope: str = "monitoring"

    # Mesh Email Security
    mesh_enabled: bool = False
    mesh_api_url: str = "https://hub-us.emailsecurity.app"
    mesh_api_key: Optional[str] = None

    # 1Stream (BVOIP call recording)
    onestream_enabled: bool = False
    onestream_api_url: str = "https://portal.1stream.com"
    onestream_api_key: Optional[str] = None

    # OpenAI (Whisper transcription)
    openai_api_key: Optional[str] = None

    # CIPP (CyberDrain Improved Partner Portal)
    cipp_enabled: bool = False
    cipp_api_url: Optional[str] = None
    cipp_client_id: Optional[str] = None
    cipp_client_secret: Optional[str] = None
    cipp_tenant_id: Optional[str] = None
    cipp_application_id: Optional[str] = None  # Defaults to cipp_client_id if not set

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
