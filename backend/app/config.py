"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Settings
    app_name: str = "FHIR Web Service"
    app_version: str = "0.1.0"
    debug: bool = False

    # FHIR Server Settings
    fhir_base_url: str = Field(
        default="https://hapi.fhir.org/baseR4",
        description="FHIR server base URL",
    )
    fhir_auth_token: str | None = Field(
        default=None,
        description="Bearer token for FHIR server authentication",
    )
    fhir_timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
    )

    # CORS Settings
    cors_origins: list[str] | str = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins (JSON array or comma-separated string)",
    )

    # OAuth2/SMART Settings (optional)
    oauth2_enabled: bool = False
    oauth2_token_url: str | None = None
    oauth2_client_id: str | None = None
    oauth2_client_secret: str | None = None

    # Epic Backend Services Authentication (JWT-based)
    epic_backend_services_enabled: bool = Field(
        default=False,
        description="Enable Epic backend services authentication",
    )
    epic_client_id: str | None = Field(
        default=None,
        description="Epic client ID",
    )
    epic_token_url: str | None = Field(
        default=None,
        description="Epic token endpoint",
    )
    epic_private_key_path: str | None = Field(
        default=None,
        description="Path to private key PEM file",
    )
    epic_key_id: str | None = Field(
        default=None,
        description="Key ID (kid) for JWT header",
    )
    epic_scopes: str = Field(
        default="system/*.read",
        description="Space-separated list of scopes",
    )
    epic_jwt_algorithm: str = Field(
        default="RS384",
        description="JWT signing algorithm (RS256, RS384, or RS512)",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
