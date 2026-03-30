"""Refresh maintenance tasks service."""
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional

from app.database import get_db
from app.db_utils import execute, fetchall, fetchone
from app.services.settings_manager import get_global_setting
from app.services.library_manager import calculate_similarity

logger = logging.getLogger(__name__)


def get_date_param(dt: datetime) -> date:
    """Convert datetime to date object for database queries.
    PostgreSQL (asyncpg) requires actual date objects, not strings.
    """
    if isinstance(dt, datetime):
        return dt.date()
    return dt


async def get_stills_needing_attention(user_id: int) -> Dict[str, List[dict]]:
    """
    Get all stills that need attention, grouped by reason.

    Categories:
    - expired: expiration_date < today
    - needs_review: status = 'needs_review'
    - never_used: usage_count = 0 AND created_at > 30 days ago
    - low_performance: performance = 'low'
    """
    result = {
        "expired": [],
        "needs_review": [],
        "never_used": [],
        "low_performance": [],
    }

    today = datetime.now().date()
    thirty_days_ago = datetime.now() - timedelta(days=30)

    async with get_db() as db:
        # Expired stills
        rows = await fetchall(db, """
            SELECT s.*, j.campaign_name as source_name
            FROM stills s
            LEFT JOIN jobs j ON s.job_id = j.id
            WHERE s.user_id = ?
            AND s.expiration_date < ?
            AND s.status != 'retired'
            ORDER BY s.expiration_date ASC
        """, (user_id, today))
        result["expired"] = [dict(r) for r in rows]

        # Needs review
        rows = await fetchall(db, """
            SELECT s.*, j.campaign_name as source_name
            FROM stills s
            LEFT JOIN jobs j ON s.job_id = j.id
            WHERE s.user_id = ? AND s.status = 'needs_review'
            ORDER BY s.expiration_date ASC
        """, (user_id,))
        result["needs_review"] = [dict(r) for r in rows]

        # Never used (older than 30 days)
        rows = await fetchall(db, """
            SELECT s.*, j.campaign_name as source_name
            FROM stills s
            LEFT JOIN jobs j ON s.job_id = j.id
            WHERE s.user_id = ?
            AND (s.usage_count = 0 OR s.usage_count IS NULL)
            AND s.created_at < ?
            AND s.status = 'active'
            ORDER BY s.created_at ASC
        """, (user_id, thirty_days_ago))
        result["never_used"] = [dict(r) for r in rows]

        # Low performance
        rows = await fetchall(db, """
            SELECT s.*, j.campaign_name as source_name
            FROM stills s
            LEFT JOIN jobs j ON s.job_id = j.id
            WHERE s.user_id = ? AND s.performance = 'low'
            ORDER BY s.usage_count DESC
        """, (user_id,))
        result["low_performance"] = [dict(r) for r in rows]

    return result


async def get_sources_needing_review(user_id: int, days_threshold: int = 14) -> List[dict]:
    """
    Get sources where review_date has passed or is within threshold days.
    """
    threshold_date = (datetime.now() + timedelta(days=days_threshold)).date()

    async with get_db() as db:
        rows = await fetchall(db, """
            SELECT src.*, j.campaign_name, j.source_summary,
                   (SELECT COUNT(*) FROM stills WHERE job_id = src.job_id) as still_count
            FROM sources src
            JOIN jobs j ON src.job_id = j.id
            WHERE src.user_id = ? AND src.review_date <= ?
            ORDER BY src.review_date ASC
        """, (user_id, threshold_date))

        return [dict(r) for r in rows]


async def get_top_performers(user_id: int, limit: int = 10) -> List[dict]:
    """Get stills with highest usage and/or high performance rating."""
    async with get_db() as db:
        rows = await fetchall(db, """
            SELECT s.*, j.campaign_name as source_name
            FROM stills s
            LEFT JOIN jobs j ON s.job_id = j.id
            WHERE s.user_id = ?
            AND s.status IN ('active', 'evergreen')
            AND (s.performance = 'high' OR s.usage_count > 0)
            ORDER BY
                CASE WHEN s.performance = 'high' THEN 0 ELSE 1 END,
                s.usage_count DESC
            LIMIT ?
        """, (user_id, limit))

        return [dict(r) for r in rows]


async def run_refresh_maintenance(user_id: int = None) -> Dict[str, int]:
    """
    Run all automatic status updates.

    1. Mark stills expiring within N days as needs_review
    2. Auto-retire stills past expiration_date (if enabled)
    3. Count sources needing review

    Returns summary of changes made.
    """
    results = {
        "stills_marked_needs_review": 0,
        "stills_retired": 0,
        "sources_flagged": 0,
    }

    # Get settings
    warning_days = int(await get_global_setting('expiration_warning_days', '30'))
    auto_retire = (await get_global_setting('auto_retire_expired', 'true')).lower() == 'true'

    warning_date = (datetime.now() + timedelta(days=warning_days)).date()
    today = datetime.now().date()

    async with get_db() as db:
        # Build user filter
        user_filter = "AND user_id = ?" if user_id else ""
        user_params = (user_id,) if user_id else ()

        # 1. Mark stills expiring soon as needs_review
        cursor = await db.fetch(f"""
            UPDATE stills
            SET status = 'needs_review'
            WHERE status = 'active'
            AND expiration_type != 'evergreen'
            AND expiration_date IS NOT NULL
            AND expiration_date <= $1
            AND expiration_date > $2
            {user_filter.replace('?', '$3') if user_id else ''}
            RETURNING id
        """, warning_date, today, *user_params)
        results["stills_marked_needs_review"] = len(cursor)

        # 2. Auto-retire expired stills (if enabled)
        if auto_retire:
            cursor = await db.fetch(f"""
                UPDATE stills
                SET status = 'retired'
                WHERE status IN ('active', 'needs_review')
                AND expiration_type != 'evergreen'
                AND expiration_date IS NOT NULL
                AND expiration_date < $1
                {user_filter.replace('?', '$2') if user_id else ''}
                RETURNING id
            """, today, *user_params)
            results["stills_retired"] = len(cursor)

        # 3. Count sources needing review
        row = await fetchone(db, f"""
            SELECT COUNT(*) as count FROM sources
            WHERE review_date <= ?
            {user_filter}
        """, (today,) + user_params)
        results["sources_flagged"] = row["count"] if row else 0

    logger.info(f"Refresh maintenance complete: {results}")
    return results


async def get_refresh_counts(user_id: int) -> Dict[str, int]:
    """Get counts for notification badge."""
    today = datetime.now().date()
    threshold_date = (datetime.now() + timedelta(days=14)).date()

    async with get_db() as db:
        # Sources needing review
        source_row = await fetchone(db, """
            SELECT COUNT(*) as count FROM sources
            WHERE user_id = ? AND review_date <= ?
        """, (user_id, threshold_date))

        # Stills needing attention (needs_review status OR expired)
        still_row = await fetchone(db, """
            SELECT COUNT(*) as count FROM stills
            WHERE user_id = ?
            AND (status = 'needs_review' OR (expiration_date < ? AND status != 'retired'))
        """, (user_id, today))

        return {
            "sources": source_row["count"] if source_row else 0,
            "stills": still_row["count"] if still_row else 0,
        }


async def find_duplicate_stills(user_id: int) -> dict:
    """
    Find duplicate stills in user's library.

    Returns dict with:
    - duplicates: list of {still_a, still_b, similarity} dicts
    - threshold_used: float
    - stills_scanned: int
    """
    threshold = float(await get_global_setting('duplicate_similarity_threshold', '0.90'))

    result = {
        "duplicates": [],
        "threshold_used": threshold,
        "stills_scanned": 0
    }

    async with get_db() as db:
        # Get all active stills for user
        rows = await fetchall(db, """
            SELECT id, content, still_type, usage_count, performance, status,
                   created_at, source_file, job_id
            FROM stills
            WHERE user_id = ? AND status = 'active'
            ORDER BY still_type, created_at
        """, (user_id,))

        stills = [dict(r) for r in rows]
        result["stills_scanned"] = len(stills)

        if len(stills) < 2:
            return result

        # Group by still_type for efficient comparison
        by_type = {}
        for still in stills:
            st = still["still_type"]
            if st not in by_type:
                by_type[st] = []
            by_type[st].append(still)

        # Compare within each type group
        seen_pairs = set()
        for still_type, group in by_type.items():
            for i, still_a in enumerate(group):
                for still_b in group[i+1:]:
                    # Create consistent pair key to avoid duplicates
                    pair_key = tuple(sorted([still_a["id"], still_b["id"]]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    # Calculate similarity
                    score = calculate_similarity(
                        still_a.get("content", ""),
                        still_b.get("content", "")
                    )

                    if score >= threshold:
                        result["duplicates"].append({
                            "still_a": still_a,
                            "still_b": still_b,
                            "similarity": round(score, 3)
                        })

        # Sort by similarity descending
        result["duplicates"].sort(key=lambda x: x["similarity"], reverse=True)

    return result


async def merge_duplicate_stills(winner_id: str, loser_id: str, user_id: int) -> dict:
    """
    Retire the loser still, keeping the winner active.

    Returns dict with:
    - success: bool
    - retired_still_id: str
    - error: str (if failed)
    """
    async with get_db() as db:
        # Verify both stills belong to user and are active
        winner = await fetchone(db,
            "SELECT id, status FROM stills WHERE id = ? AND user_id = ?",
            (winner_id, user_id)
        )
        loser = await fetchone(db,
            "SELECT id, status FROM stills WHERE id = ? AND user_id = ?",
            (loser_id, user_id)
        )

        if not winner:
            return {"success": False, "error": "Winner still not found"}
        if not loser:
            return {"success": False, "error": "Loser still not found"}
        if loser["status"] == "retired":
            return {"success": False, "error": "Still already retired"}

        # Retire the loser
        await execute(db,
            "UPDATE stills SET status = 'retired' WHERE id = ?",
            (loser_id,)
        )


    return {
        "success": True,
        "retired_still_id": loser_id
    }
