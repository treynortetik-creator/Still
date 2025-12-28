"""Background task utilities for safe async task execution."""
import asyncio
import logging
from typing import Coroutine, Any, Optional, Set
from functools import wraps

logger = logging.getLogger(__name__)

# Track active background tasks to prevent garbage collection
_active_tasks: Set[asyncio.Task] = set()


def create_background_task(
    coro: Coroutine[Any, Any, Any],
    name: Optional[str] = None,
    log_errors: bool = True
) -> asyncio.Task:
    """
    Create a background task with proper exception handling.

    Unlike raw asyncio.create_task(), this:
    1. Stores task reference to prevent garbage collection
    2. Logs exceptions instead of silently dropping them
    3. Cleans up task reference when complete

    Args:
        coro: The coroutine to run
        name: Optional name for the task (for logging)
        log_errors: Whether to log exceptions (default True)

    Returns:
        The created asyncio.Task
    """
    task = asyncio.create_task(coro, name=name)
    _active_tasks.add(task)

    def on_complete(t: asyncio.Task):
        _active_tasks.discard(t)
        if log_errors:
            try:
                exc = t.exception()
                if exc:
                    task_name = name or t.get_name()
                    logger.error(
                        f"Background task '{task_name}' failed: {type(exc).__name__}: {exc}",
                        exc_info=exc
                    )
            except asyncio.CancelledError:
                pass
            except asyncio.InvalidStateError:
                pass

    task.add_done_callback(on_complete)
    return task


async def run_with_timeout(
    coro: Coroutine[Any, Any, Any],
    timeout: float,
    name: Optional[str] = None
) -> Any:
    """
    Run a coroutine with a timeout.

    Args:
        coro: The coroutine to run
        timeout: Timeout in seconds
        name: Optional name for logging

    Returns:
        The result of the coroutine

    Raises:
        asyncio.TimeoutError: If the coroutine doesn't complete in time
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        task_name = name or "unnamed"
        logger.warning(f"Task '{task_name}' timed out after {timeout}s")
        raise


def get_active_task_count() -> int:
    """Get the number of active background tasks."""
    return len(_active_tasks)


def get_active_task_names() -> list[str]:
    """Get names of all active background tasks."""
    return [t.get_name() for t in _active_tasks if not t.done()]
