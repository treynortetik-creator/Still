"""Lifecycle management for stills - handles expiration and status updates."""
import logging
from datetime import date, timedelta

from app.database import get_db
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


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
            if settings.use_postgres:
                # PostgreSQL: use RETURNING to get count
                cursor = await db.fetch("""
                    UPDATE stills
                    SET status = 'needs_review'
                    WHERE status = 'active'
                      AND expiration_date IS NOT NULL
                      AND expiration_date <= $1
                    RETURNING id
                """, threshold_date)
                return len(cursor)
            else:
                # SQLite: run UPDATE then count affected rows
                cursor = await db.execute("""
                    UPDATE stills
                    SET status = 'needs_review'
                    WHERE status = 'active'
                      AND expiration_date IS NOT NULL
                      AND expiration_date <= ?
                """, (threshold_date.isoformat(),))
                await db.commit()
                return cursor.rowcount
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
            if settings.use_postgres:
                # PostgreSQL: use FILTER syntax
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
            else:
                # SQLite: use SUM(CASE WHEN ...) syntax
                cursor = await db.execute("""
                    SELECT
                        SUM(CASE WHEN status = 'active' OR status IS NULL THEN 1 ELSE 0 END) as active,
                        SUM(CASE WHEN status = 'evergreen' THEN 1 ELSE 0 END) as evergreen,
                        SUM(CASE WHEN status = 'needs_review' THEN 1 ELSE 0 END) as needs_review,
                        SUM(CASE WHEN status = 'retired' THEN 1 ELSE 0 END) as retired,
                        SUM(CASE WHEN expiration_date <= date('now', '+7 days') THEN 1 ELSE 0 END) as expiring_soon
                    FROM stills
                    WHERE user_id = ?
                """, (user_id,))
                row = await cursor.fetchone()

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
            if settings.use_postgres:
                result = await db.execute("""
                    UPDATE stills SET status = $1 WHERE id = $2
                """, new_status, still_id)
                # PostgreSQL returns a string like "UPDATE 1"
                return result.split()[-1] != '0'
            else:
                cursor = await db.execute("""
                    UPDATE stills SET status = ? WHERE id = ?
                """, (new_status, still_id))
                await db.commit()
                return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update still {still_id} status to {new_status}: {e}")
        raise
