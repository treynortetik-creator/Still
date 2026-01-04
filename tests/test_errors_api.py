"""Tests for the error logging API endpoint."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_db
from app.db_utils import fetchall


@pytest.mark.asyncio
async def test_log_error_endpoint_without_auth(test_db):
    """POST /api/errors/log should work without authentication."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/errors/log", json={
            "error_type": "test_api_error",
            "error_message": "Test from endpoint"
        })

    assert response.status_code == 200
    assert response.json() == {"success": True}

    # Verify it was logged to database
    async with get_db() as db:
        rows = await fetchall(db, "SELECT * FROM error_logs WHERE error_type = ?", ("test_api_error",))
        assert len(rows) == 1
        assert rows[0]["source"] == "frontend"


@pytest.mark.asyncio
async def test_log_error_endpoint_with_context(test_db):
    """POST /api/errors/log should accept additional context."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/errors/log", json={
            "error_type": "frontend_error",
            "error_message": "Button click failed",
            "endpoint": "/refresh",
            "stack_trace": "Error at line 42",
            "additional_context": {"browser": "Chrome", "version": "120"}
        })

    assert response.status_code == 200

    async with get_db() as db:
        rows = await fetchall(db, "SELECT * FROM error_logs WHERE error_type = ?", ("frontend_error",))
        assert len(rows) == 1
        assert rows[0]["endpoint"] == "/refresh"
        assert rows[0]["stack_trace"] == "Error at line 42"
        assert "Chrome" in str(rows[0]["additional_context"])


@pytest.mark.asyncio
async def test_log_error_endpoint_validates_required_fields(test_db):
    """POST /api/errors/log should require error_type and error_message."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/errors/log", json={
            "error_type": "missing_message"
            # error_message missing
        })

    assert response.status_code == 422  # Validation error
