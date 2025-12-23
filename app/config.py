"""Application configuration settings."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
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
    database_url: str = "sqlite+aiosqlite:///./database/contentmultiplier.db"

    # Application
    debug: bool = True
    secret_key: str = "change-this-in-production"
    upload_max_size_mb: int = 100

    # Admin
    admin_username: str = "admin"
    admin_password: str = "admin"

    # Paths
    base_dir: Path = Path(__file__).parent.parent
    data_dir: Path = base_dir / "data"
    upload_dir: Path = data_dir / "jobs"
    prompts_dir: Path = data_dir / "prompts"
    clients_dir: Path = data_dir / "clients"
    database_dir: Path = base_dir / "database"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Cost tracking for AI models (per 1M tokens)
MODEL_COSTS = {
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "claude-opus-4-5-20251101": {"input": 15.00, "output": 75.00},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate API cost based on model and token usage."""
    if model not in MODEL_COSTS:
        return 0.0

    costs = MODEL_COSTS[model]
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]

    return input_cost + output_cost
