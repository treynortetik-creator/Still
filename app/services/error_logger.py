"""Error logging service for tracking errors in production."""
import json
import logging
import traceback
from typing import Optional

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute

logger = logging.getLogger(__name__)


async def log_error(
    error_type: str,
    error_message: str,
    source: str = "backend",
    user_id: Optional[int] = None,
    job_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    stack_trace: Optional[str] = None,
    additional_context: Optional[dict] = None
) -> None:
    """
    Log an error to the database. Fire-and-forget, never raises.

    Args:
        error_type: Category (api_error, frontend_error, validation_error, etc.)
        error_message: The error message
        source: 'frontend' or 'backend'
        user_id: User who encountered error (optional)
        job_id: Related job ID (optional)
        endpoint: API endpoint or page URL
        stack_trace: Stack trace if available
        additional_context: Any extra info as dict (stored as JSONB)
    """
    try:
        settings = get_settings()
        context_json = json.dumps(additional_context) if additional_context else None

        async with get_db() as db:
            if settings.use_postgres:
                await db.execute("""
                    INSERT INTO error_logs
                    (error_type, error_message, source, user_id, job_id, endpoint, stack_trace, additional_context)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, error_type or "unknown", error_message or "No message", source,
                    user_id, job_id, endpoint, stack_trace, context_json)
            else:
                await execute(db, """
                    INSERT INTO error_logs
                    (error_type, error_message, source, user_id, job_id, endpoint, stack_trace, additional_context)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (error_type or "unknown", error_message or "No message", source,
                      user_id, job_id, endpoint, stack_trace, context_json))
                await db.commit()
    except Exception as e:
        # Never raise - just log to console as fallback
        logger.error(f"Failed to log error to database: {e}")


async def log_exception(
    error_type: str,
    exception: Exception,
    source: str = "backend",
    user_id: Optional[int] = None,
    job_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    additional_context: Optional[dict] = None
) -> None:
    """Convenience wrapper to log an exception with its stack trace."""
    await log_error(
        error_type=error_type,
        error_message=str(exception),
        source=source,
        user_id=user_id,
        job_id=job_id,
        endpoint=endpoint,
        stack_trace=traceback.format_exc(),
        additional_context=additional_context
    )
