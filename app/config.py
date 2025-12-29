"""Application configuration settings."""
import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""  # Alternative to Anthropic

    # API Configuration
    use_openrouter: bool = False  # Set to True to use OpenRouter instead of Anthropic
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Database
    database_url: str = ""  # PostgreSQL connection string from Supabase (set via DATABASE_URL env var)

    # Application
    debug: bool = False  # Default to False for security
    secret_key: str = ""  # REQUIRED - must be set via SECRET_KEY env var
    upload_max_size_mb: int = 100
    environment: str = "development"  # development, production
    port: int = 8000  # Railway sets PORT env var

    # Input validation limits
    max_text_content_chars: int = 500000  # ~500KB of text
    max_campaign_name_chars: int = 200
    max_magic_words_chars: int = 500
    max_content_name_chars: int = 255
    max_persona_name_chars: int = 100

    # Processing limits
    max_batch_files: int = 10
    batch_concurrency_limit: int = 2
    webhook_max_retries: int = 3
    webhook_retry_delay_seconds: int = 5
    webhook_timeout_seconds: int = 30

    # Admin credentials - REQUIRED in production
    admin_username: str = ""  # Must be set via ADMIN_USERNAME env var
    admin_password: str = ""  # Must be set via ADMIN_PASSWORD env var

    # CORS - comma-separated list of allowed origins
    allowed_origins: str = "http://localhost:3000,http://localhost:5000,http://localhost:8000"

    # Railway/Production deployment
    railway_environment: str = ""  # Set automatically by Railway
    railway_public_domain: str = ""  # Set automatically by Railway

    @field_validator("secret_key", mode="before")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Ensure secret_key is set and not the default placeholder."""
        if not v or v == "change-this-in-production":
            # In development, generate a random key with a warning
            import warnings
            warnings.warn(
                "SECRET_KEY not set! Using auto-generated key. "
                "Set SECRET_KEY environment variable for production.",
                UserWarning
            )
            return secrets.token_urlsafe(32)
        return v

    @field_validator("admin_username", "admin_password", mode="before")
    @classmethod
    def validate_admin_credentials(cls, v: str, info) -> str:
        """Warn if admin credentials are not set."""
        if not v:
            import warnings
            field_name = info.field_name.upper()
            warnings.warn(
                f"{field_name} not set! Admin panel will be inaccessible. "
                f"Set {field_name} environment variable.",
                UserWarning
            )
        return v

    # Paths - use RAILWAY_VOLUME_MOUNT_PATH if available for persistent storage
    @property
    def base_dir(self) -> Path:
        return Path(__file__).parent.parent

    @property
    def data_dir(self) -> Path:
        # Railway volume mount path for persistent data
        railway_volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
        if railway_volume:
            return Path(railway_volume) / "data"
        return self.base_dir / "data"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def prompts_dir(self) -> Path:
        # Prompts are part of the codebase, not user data
        return self.base_dir / "data" / "prompts"

    @property
    def clients_dir(self) -> Path:
        return self.data_dir / "clients"

    @property
    def database_dir(self) -> Path:
        # Railway volume mount path for persistent database (only used for SQLite fallback)
        railway_volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
        if railway_volume:
            return Path(railway_volume) / "database"
        return self.base_dir / "database"

    @property
    def use_postgres(self) -> bool:
        """Check if PostgreSQL is configured (vs SQLite fallback)."""
        return bool(self.database_url and self.database_url.startswith("postgresql"))

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
