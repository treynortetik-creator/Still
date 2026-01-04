"""Tests for refresh maintenance tasks."""
import pytest
from datetime import datetime, timedelta
from app.services.refresh_tasks import (
    run_refresh_maintenance,
    get_stills_needing_attention,
    get_sources_needing_review,
    find_duplicate_stills,
    merge_duplicate_stills,
)


@pytest.mark.asyncio
async def test_get_stills_needing_attention_empty(test_db):
    """Returns empty structure when no stills need attention."""
    result = await get_stills_needing_attention(user_id=1)
    assert "expired" in result
    assert "needs_review" in result
    assert "never_used" in result
    assert "low_performance" in result
    assert result["expired"] == []


@pytest.mark.asyncio
async def test_get_sources_needing_review_empty(test_db):
    """Returns empty list when no sources need review."""
    result = await get_sources_needing_review(user_id=1)
    assert result == []


@pytest.mark.asyncio
async def test_run_refresh_maintenance_returns_summary(test_db):
    """Maintenance returns summary of actions taken."""
    result = await run_refresh_maintenance(user_id=1)
    assert "stills_marked_needs_review" in result
    assert "stills_retired" in result
    assert "sources_flagged" in result


@pytest.mark.asyncio
async def test_find_duplicate_stills_empty(test_db):
    """Returns empty list when no stills exist."""
    result = await find_duplicate_stills(user_id=1)
    assert result["duplicates"] == []
    assert result["threshold_used"] == 0.90
    assert result["stills_scanned"] == 0


@pytest.mark.asyncio
async def test_find_duplicate_stills_no_duplicates(test_db):
    """Returns empty list when stills are unique."""
    from app.database import get_db
    from app.db_utils import execute
    import uuid

    job_id = str(uuid.uuid4())

    async with get_db() as db:
        # Create job first (foreign key constraint)
        await execute(db, """
            INSERT INTO jobs (id, user_id, status) VALUES (?, ?, ?)
        """, (job_id, 1, "complete"))

        await execute(db, """
            INSERT INTO stills (id, job_id, user_id, still_type, content, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), job_id, 1, "insight", "This is about marketing strategies", "active"))

        await execute(db, """
            INSERT INTO stills (id, job_id, user_id, still_type, content, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), job_id, 1, "insight", "Completely different topic about cooking", "active"))

        await db.commit()

    result = await find_duplicate_stills(user_id=1)
    assert result["duplicates"] == []
    assert result["stills_scanned"] == 2


@pytest.mark.asyncio
async def test_merge_duplicate_stills(test_db):
    """Merge retires the loser still."""
    from app.database import get_db
    from app.db_utils import execute, fetchone
    import uuid

    job_id = str(uuid.uuid4())
    winner_id = str(uuid.uuid4())
    loser_id = str(uuid.uuid4())

    async with get_db() as db:
        # Create job first (foreign key constraint)
        await execute(db, """
            INSERT INTO jobs (id, user_id, status) VALUES (?, ?, ?)
        """, (job_id, 1, "complete"))

        await execute(db, """
            INSERT INTO stills (id, job_id, user_id, still_type, content, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (winner_id, job_id, 1, "insight", "Winner content", "active"))

        await execute(db, """
            INSERT INTO stills (id, job_id, user_id, still_type, content, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (loser_id, job_id, 1, "insight", "Loser content", "active"))

        await db.commit()

    result = await merge_duplicate_stills(winner_id, loser_id, user_id=1)
    assert result["success"] == True
    assert result["retired_still_id"] == loser_id

    # Verify loser is retired
    async with get_db() as db:
        loser = await fetchone(db, "SELECT status FROM stills WHERE id = ?", (loser_id,))
        assert loser["status"] == "retired"

        winner = await fetchone(db, "SELECT status FROM stills WHERE id = ?", (winner_id,))
        assert winner["status"] == "active"
