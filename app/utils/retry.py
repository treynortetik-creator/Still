"""Retry utilities with exponential backoff."""
import asyncio
import functools
import logging
import traceback
from typing import TypeVar, Callable, Optional

from app.database import get_db

logger = logging.getLogger(__name__)
from app.db_utils import execute

T = TypeVar('T')

# Errors that should trigger a retry
RETRYABLE_ERRORS = (
    ConnectionError,
    TimeoutError,
    asyncio.TimeoutError,
)


async def log_error(
    error_type: str,
    error_message: str,
    job_id: Optional[str] = None,
    user_id: Optional[int] = None,
    context: Optional[str] = None,
):
    """Log an error to the database for monitoring."""
    try:
        async with get_db() as db:
            await execute(
                db,
                """
                INSERT INTO error_logs (job_id, user_id, error_type, error_message, source, endpoint, additional_context)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, user_id, error_type, error_message[:2000], "backend", context, None)
            )
    except Exception as e:
        # Don't let error logging failures break the app
        logger.error(f"Failed to log error: {e}")


async def retry_async(
    func: Callable[..., T],
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_errors: tuple = RETRYABLE_ERRORS,
    job_id: Optional[str] = None,
    user_id: Optional[int] = None,
    context: Optional[str] = None,
    **kwargs,
) -> T:
    """
    Execute an async function with retry logic and exponential backoff.

    Args:
        func: The async function to execute
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        retryable_errors: Tuple of exception types that should trigger a retry
        job_id: Optional job ID for error logging
        user_id: Optional user ID for error logging
        context: Optional context string for error logging

    Returns:
        The result of the function call

    Raises:
        The last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except retryable_errors as e:
            last_exception = e

            if attempt < max_retries:
                # Calculate delay with exponential backoff
                delay = min(base_delay * (exponential_base ** attempt), max_delay)

                # Log the retry attempt
                error_msg = f"Attempt {attempt + 1}/{max_retries + 1} failed: {str(e)}"
                logger.warning(f"[Retry] {context or 'Unknown'}: {error_msg}, retrying in {delay:.1f}s")

                await log_error(
                    error_type="retry",
                    error_message=error_msg,
                    job_id=job_id,
                    user_id=user_id,
                    context=context,
                )

                await asyncio.sleep(delay)
            else:
                # Log final failure
                await log_error(
                    error_type="failure",
                    error_message=f"All {max_retries + 1} attempts failed: {str(e)}\n{traceback.format_exc()}",
                    job_id=job_id,
                    user_id=user_id,
                    context=context,
                )

        except Exception as e:
            # Non-retryable error - log and re-raise
            await log_error(
                error_type="error",
                error_message=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}",
                job_id=job_id,
                user_id=user_id,
                context=context,
            )
            raise

    # All retries exhausted
    raise last_exception


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_errors: tuple = RETRYABLE_ERRORS,
):
    """
    Decorator to add retry logic to an async function.

    Usage:
        @with_retry(max_retries=3, base_delay=2.0)
        async def call_api():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                func,
                *args,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                retryable_errors=retryable_errors,
                context=func.__name__,
                **kwargs,
            )
        return wrapper
    return decorator


