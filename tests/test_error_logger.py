"""Tests for error logger service."""
import pytest
from app.services.error_logger import log_error
from app.database import get_db
from app.db_utils import fetchall


@pytest.mark.asyncio
async def test_log_error_basic(test_db):
    """Logs an error to the database."""
    await log_error(
        error_type="test_error",
        error_message="Test error message",
        source="backend",
        endpoint="/api/test"
    )

    async with get_db() as db:
        rows = await fetchall(db, "SELECT * FROM error_logs WHERE error_type = ?", ("test_error",))
        assert len(rows) == 1
        assert rows[0]["error_message"] == "Test error message"
        assert rows[0]["source"] == "backend"


@pytest.mark.asyncio
async def test_log_error_with_context(test_db):
    """Logs an error with additional context."""
    await log_error(
        error_type="api_error",
        error_message="API failed",
        source="frontend",
        user_id=1,
        endpoint="/api/refresh/merge",
        additional_context={"browser": "Chrome", "url": "http://localhost/refresh"}
    )

    async with get_db() as db:
        rows = await fetchall(db, "SELECT * FROM error_logs WHERE error_type = ?", ("api_error",))
        assert len(rows) == 1
        assert rows[0]["user_id"] == 1
        assert "Chrome" in str(rows[0]["additional_context"])


@pytest.mark.asyncio
async def test_log_error_never_raises(test_db):
    """log_error should never raise, even with bad input."""
    # This should not raise even with None values
    await log_error(
        error_type=None,
        error_message=None
    )
    # If we get here, test passes
    assert True
