"""Tests for refresh maintenance tasks."""
import pytest
from datetime import datetime, timedelta
from app.services.refresh_tasks import (
    run_refresh_maintenance,
    get_stills_needing_attention,
    get_sources_needing_review,
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
