"""Settings management using database for persistence.

This module provides database-backed settings that persist across Railway deploys.
Settings are stored in:
- global_settings table: For boolean/string settings like use_openrouter
- ai_model_config table: For model configuration per pipeline step
"""
import asyncio
import os
import logging
from typing import Dict, Any, Optional
from functools import lru_cache
import threading

logger = logging.getLogger(__name__)

# In-memory cache for synchronous access (refreshed by async operations)
_settings_cache: Dict[str, Any] = {
    "use_openrouter": True,
    "models": {},
    "last_refresh": 0,
}
_cache_lock = threading.Lock()

# Default model configurations
DEFAULT_MODELS = {
    "transcription": "google/gemini-2.5-flash",
    "distillation": "google/gemini-2.5-flash",
    "distillation_pass2": "google/gemini-2.5-flash",
    "summarization": "google/gemini-2.5-flash",
    "atomization": "google/gemini-2.5-flash",
    "drafting": "google/gemini-3-flash-preview",
    "editing": "google/gemini-2.5-flash",
    "factcheck": "google/gemini-2.5-flash",
    "workshop_ai_edit": "google/gemini-2.5-flash",
    "sommelier": "google/gemini-2.5-flash",
}


def get_api_key_status() -> Dict[str, bool]:
    """Check which API keys are configured (from environment)."""
    return {
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY"))
    }


def get_model_for_step(step: str) -> str:
    """
    Get the configured model for a specific pipeline step.

    This is a synchronous function that uses cached values.
    The cache is refreshed by async operations or on app startup.
    """
    with _cache_lock:
        models = _settings_cache.get("models", {})

    # Handle atomization/distillation aliasing - they're the same step
    if step == "distillation":
        return models.get("distillation",
                         models.get("atomization",
                                   DEFAULT_MODELS.get("distillation")))
    elif step == "atomization":
        return models.get("atomization",
                         models.get("distillation",
                                   DEFAULT_MODELS.get("atomization")))

    return models.get(step, DEFAULT_MODELS.get(step, "google/gemini-2.5-flash"))


def is_openrouter_enabled() -> bool:
    """Check if OpenRouter is enabled (synchronous, uses cache)."""
    with _cache_lock:
        return _settings_cache.get("use_openrouter", True)


def get_settings() -> Dict[str, Any]:
    """Get all settings (synchronous, uses cache)."""
    with _cache_lock:
        return {
            "use_openrouter": _settings_cache.get("use_openrouter", True),
            "models": _settings_cache.get("models", DEFAULT_MODELS.copy()),
        }


# ============================================================================
# Async Database Operations
# ============================================================================

async def refresh_settings_cache():
    """Refresh the in-memory cache from database."""
    from app.config import get_settings as get_app_settings
    from app.database import get_db
    from app.db_utils import fetchall, fetchone

    app_settings = get_app_settings()

    try:
        async with get_db() as db:
            # Load global settings
            if app_settings.use_postgres:
                row = await db.fetchrow(
                    "SELECT setting_value FROM global_settings WHERE setting_key = $1",
                    "use_openrouter"
                )
                use_openrouter = row["setting_value"].lower() == "true" if row else True
            else:
                row = await fetchone(
                    db,
                    "SELECT setting_value FROM global_settings WHERE setting_key = ?",
                    ("use_openrouter",)
                )
                use_openrouter = row["setting_value"].lower() == "true" if row else True

            # Load model configurations
            rows = await fetchall(
                db,
                "SELECT service_name, model_id FROM ai_model_config WHERE is_active = ?",
                (True,)
            )

            models = {}
            for row in rows:
                models[row["service_name"]] = row["model_id"]

            # Update cache
            with _cache_lock:
                _settings_cache["use_openrouter"] = use_openrouter
                _settings_cache["models"] = models if models else DEFAULT_MODELS.copy()
                import time
                _settings_cache["last_refresh"] = time.time()

            logger.debug(f"Settings cache refreshed: openrouter={use_openrouter}, models={len(models)}")

    except Exception as e:
        logger.warning(f"Failed to refresh settings from database: {e}. Using defaults.")
        # Keep existing cache values or use defaults
        with _cache_lock:
            if not _settings_cache.get("models"):
                _settings_cache["models"] = DEFAULT_MODELS.copy()


async def get_global_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a global setting value from database.

    Args:
        key: The setting key to look up
        default: Value to return if setting is not found (default: None)

    Returns:
        The setting value if found, otherwise the default value
    """
    from app.config import get_settings as get_app_settings
    from app.database import get_db
    from app.db_utils import fetchone

    app_settings = get_app_settings()

    async with get_db() as db:
        if app_settings.use_postgres:
            row = await db.fetchrow(
                "SELECT setting_value FROM global_settings WHERE setting_key = $1",
                key
            )
        else:
            row = await fetchone(
                db,
                "SELECT setting_value FROM global_settings WHERE setting_key = ?",
                (key,)
            )

        return row["setting_value"] if row else default


async def set_global_setting(key: str, value: str, setting_type: str = "string", description: str = None):
    """Set a global setting value in database."""
    from app.config import get_settings as get_app_settings
    from app.database import get_db
    from app.db_utils import execute, fetchone

    app_settings = get_app_settings()

    async with get_db() as db:
        # Check if exists
        if app_settings.use_postgres:
            exists = await db.fetchrow(
                "SELECT id FROM global_settings WHERE setting_key = $1",
                key
            )
            if exists:
                await db.execute(
                    """
                    UPDATE global_settings
                    SET setting_value = $1, updated_at = NOW()
                    WHERE setting_key = $2
                    """,
                    value, key
                )
            else:
                await db.execute(
                    """
                    INSERT INTO global_settings (setting_key, setting_value, setting_type, description)
                    VALUES ($1, $2, $3, $4)
                    """,
                    key, value, setting_type, description
                )
        else:
            exists = await fetchone(
                db,
                "SELECT id FROM global_settings WHERE setting_key = ?",
                (key,)
            )
            if exists:
                await execute(
                    db,
                    """
                    UPDATE global_settings
                    SET setting_value = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE setting_key = ?
                    """,
                    (value, key)
                )
            else:
                await execute(
                    db,
                    """
                    INSERT INTO global_settings (setting_key, setting_value, setting_type, description)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key, value, setting_type, description)
                )
            await db.commit()

    # Refresh cache
    await refresh_settings_cache()


async def set_openrouter_enabled(enabled: bool):
    """Enable or disable OpenRouter (async, saves to database)."""
    await set_global_setting(
        "use_openrouter",
        "true" if enabled else "false",
        "boolean",
        "Whether to use OpenRouter for AI calls"
    )


async def get_model_config_async(service_name: str) -> Optional[Dict[str, Any]]:
    """Get model configuration for a service from database."""
    from app.config import get_settings as get_app_settings
    from app.database import get_db
    from app.db_utils import fetchone

    app_settings = get_app_settings()

    async with get_db() as db:
        if app_settings.use_postgres:
            row = await db.fetchrow(
                """
                SELECT service_name, model_id, display_name, is_active,
                       cost_per_1k_input, cost_per_1k_output, max_tokens
                FROM ai_model_config WHERE service_name = $1
                """,
                service_name
            )
        else:
            row = await fetchone(
                db,
                """
                SELECT service_name, model_id, display_name, is_active,
                       cost_per_1k_input, cost_per_1k_output, max_tokens
                FROM ai_model_config WHERE service_name = ?
                """,
                (service_name,)
            )

        if row:
            return {
                "service_name": row["service_name"],
                "model_id": row["model_id"],
                "display_name": row["display_name"],
                "is_active": bool(row["is_active"]),
                "cost_per_1k_input": row["cost_per_1k_input"],
                "cost_per_1k_output": row["cost_per_1k_output"],
                "max_tokens": row["max_tokens"],
            }
        return None


async def set_model_config_async(service_name: str, model_id: str, display_name: str = None):
    """Set model configuration for a service in database."""
    from app.config import get_settings as get_app_settings
    from app.database import get_db
    from app.db_utils import execute, fetchone

    app_settings = get_app_settings()

    async with get_db() as db:
        if app_settings.use_postgres:
            exists = await db.fetchrow(
                "SELECT id FROM ai_model_config WHERE service_name = $1",
                service_name
            )
            if exists:
                await db.execute(
                    """
                    UPDATE ai_model_config
                    SET model_id = $1, display_name = $2, updated_at = NOW()
                    WHERE service_name = $3
                    """,
                    model_id, display_name or model_id, service_name
                )
            else:
                await db.execute(
                    """
                    INSERT INTO ai_model_config (service_name, model_id, display_name, is_active)
                    VALUES ($1, $2, $3, true)
                    """,
                    service_name, model_id, display_name or model_id
                )
        else:
            exists = await fetchone(
                db,
                "SELECT id FROM ai_model_config WHERE service_name = ?",
                (service_name,)
            )
            if exists:
                await execute(
                    db,
                    """
                    UPDATE ai_model_config
                    SET model_id = ?, display_name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE service_name = ?
                    """,
                    (model_id, display_name or model_id, service_name)
                )
            else:
                await execute(
                    db,
                    """
                    INSERT INTO ai_model_config (service_name, model_id, display_name, is_active)
                    VALUES (?, ?, ?, 1)
                    """,
                    (service_name, model_id, display_name or model_id)
                )
            await db.commit()

    # Refresh cache
    await refresh_settings_cache()


async def set_model_config(models: Dict[str, str]):
    """Set model configuration for all steps (async, saves to database)."""
    for service_name, model_id in models.items():
        await set_model_config_async(service_name, model_id)


async def init_default_settings():
    """Initialize default settings in database if they don't exist."""
    from app.config import get_settings as get_app_settings
    from app.database import get_db
    from app.db_utils import execute, fetchone

    app_settings = get_app_settings()

    async with get_db() as db:
        # Ensure global_settings table exists and has defaults
        if app_settings.use_postgres:
            # Check if use_openrouter setting exists
            row = await db.fetchrow(
                "SELECT id FROM global_settings WHERE setting_key = $1",
                "use_openrouter"
            )
            if not row:
                await db.execute(
                    """
                    INSERT INTO global_settings (setting_key, setting_value, setting_type, description)
                    VALUES ($1, $2, $3, $4)
                    """,
                    "use_openrouter", "true", "boolean", "Whether to use OpenRouter for AI calls"
                )
        else:
            # SQLite - table created by init_db, just ensure default value
            row = await fetchone(
                db,
                "SELECT id FROM global_settings WHERE setting_key = ?",
                ("use_openrouter",)
            )
            if not row:
                await execute(
                    db,
                    """
                    INSERT INTO global_settings (setting_key, setting_value, setting_type, description)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("use_openrouter", "true", "boolean", "Whether to use OpenRouter for AI calls")
                )
                await db.commit()

        # Initialize default model configs
        for service_name, model_id in DEFAULT_MODELS.items():
            if app_settings.use_postgres:
                row = await db.fetchrow(
                    "SELECT id FROM ai_model_config WHERE service_name = $1",
                    service_name
                )
                if not row:
                    await db.execute(
                        """
                        INSERT INTO ai_model_config (service_name, model_id, display_name, is_active)
                        VALUES ($1, $2, $3, true)
                        """,
                        service_name, model_id, model_id
                    )
            else:
                row = await fetchone(
                    db,
                    "SELECT id FROM ai_model_config WHERE service_name = ?",
                    (service_name,)
                )
                if not row:
                    await execute(
                        db,
                        """
                        INSERT INTO ai_model_config (service_name, model_id, display_name, is_active)
                        VALUES (?, ?, ?, 1)
                        """,
                        (service_name, model_id, model_id)
                    )

        if not app_settings.use_postgres:
            await db.commit()

    # Refresh cache with database values
    await refresh_settings_cache()
    logger.info("Default settings initialized in database")
