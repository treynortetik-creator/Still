"""Lifecycle management for stills - handles expiration and status updates."""
import logging
from datetime import date, timedelta

from app.database import get_db

logger = logging.getLogger(__name__)


async def check_expiring_stills(days_threshold: int = 30) -> int:
    """
    Mark stills as 'needs_review' when expiration is approaching.

    Args:
        days_threshold: Days before expiration to flag (default 30)

    Returns:
        Count of stills flagged
    """
    threshold_date = date.today() + timedelta(days=days_threshold)

    try:
        async with get_db() as db:
            cursor = await db.fetch("""
                UPDATE stills
                SET status = 'needs_review'
                WHERE status = 'active'
                  AND expiration_date IS NOT NULL
                  AND expiration_date <= $1
                RETURNING id
            """, threshold_date)
            return len(cursor)
    except Exception as e:
        logger.error(f"Failed to check expiring stills: {e}")
        raise


async def get_lifecycle_summary(user_id: int) -> dict:
    """
    Get counts by status for dashboard/UI.

    Args:
        user_id: User to get summary for

    Returns:
        Dict with counts per status and expiring_soon count
    """
    try:
        async with get_db() as db:
            row = await db.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'active' OR status IS NULL) as active,
                    COUNT(*) FILTER (WHERE status = 'evergreen') as evergreen,
                    COUNT(*) FILTER (WHERE status = 'needs_review') as needs_review,
                    COUNT(*) FILTER (WHERE status = 'retired') as retired,
                    COUNT(*) FILTER (WHERE expiration_date <= CURRENT_DATE + INTERVAL '7 days') as expiring_soon
                FROM stills
                WHERE user_id = $1
            """, user_id)

            if row is None:
                return {
                    "active": 0,
                    "evergreen": 0,
                    "needs_review": 0,
                    "retired": 0,
                    "expiring_soon": 0,
                }

            return {
                "active": row["active"] or 0,
                "evergreen": row["evergreen"] or 0,
                "needs_review": row["needs_review"] or 0,
                "retired": row["retired"] or 0,
                "expiring_soon": row["expiring_soon"] or 0,
            }
    except Exception as e:
        logger.error(f"Failed to get lifecycle summary for user {user_id}: {e}")
        raise


async def update_still_status(still_id: str, new_status: str) -> bool:
    """
    Update the status of a still.

    Args:
        still_id: ID of still to update
        new_status: New status value

    Returns:
        True if updated, False if not found
    """
    if not still_id:
        raise ValueError("still_id is required")

    valid_statuses = ['active', 'evergreen', 'needs_review', 'retired']
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status: {new_status}")

    try:
        async with get_db() as db:
            result = await db.execute("""
                UPDATE stills SET status = $1 WHERE id = $2
            """, new_status, still_id)
            # PostgreSQL returns a string like "UPDATE 1"
            return result.split()[-1] != '0'
    except Exception as e:
        logger.error(f"Failed to update still {still_id} status to {new_status}: {e}")
        raise
