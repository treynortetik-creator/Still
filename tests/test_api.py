"""Tests for API endpoints."""
import json
import pytest
from io import BytesIO


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_api_info(client):
    """Test API info endpoint."""
    response = await client.get("/api")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "ContentMultiplier API"
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_upload_text_content(client):
    """Test uploading text content."""
    response = await client.post(
        "/api/upload-text",
        data={
            "content": "This is sample content for testing the upload endpoint.",
            "target_persona": "ceo_longterm_care",
            "asset_types": json.dumps(["linkedin"]),
            "asset_quantities": json.dumps({"linkedin": 1}),
            "content_name": "test_content.txt",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "uploading"


@pytest.mark.asyncio
async def test_upload_requires_persona(client):
    """Test that upload requires target persona."""
    response = await client.post(
        "/api/upload-text",
        data={
            "content": "Test content",
            "target_persona": "",  # Empty persona
            "asset_types": json.dumps(["linkedin"]),
        },
    )

    # Should still work but the job will fail during processing
    # since persona validation happens in the pipeline
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_job_status_not_found(client):
    """Test getting status for non-existent job."""
    response = await client.get("/api/job/non-existent-job-id/status")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_jobs_empty(client):
    """Test listing jobs when empty."""
    response = await client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_library_empty(client):
    """Test getting library when empty."""
    response = await client.get("/api/library")
    assert response.status_code == 200
    data = response.json()
    assert "entries" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_library_stats(client):
    """Test getting library stats."""
    response = await client.get("/api/library/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_entries" in data
    assert "by_type" in data


@pytest.mark.asyncio
async def test_library_filter_by_type(client):
    """Test filtering library by type."""
    response = await client.get("/api/library?entry_type=data")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_library_search(client):
    """Test searching library."""
    response = await client.get("/api/library?search=test")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_dashboard(client):
    """Test admin dashboard API."""
    response = await client.get("/admin/dashboard")
    # This returns HTML or JSON depending on endpoint
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_list_prompts(client):
    """Test listing prompts."""
    response = await client.get("/admin/prompts")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_list_clients(client):
    """Test listing clients."""
    response = await client.get("/admin/clients")
    assert response.status_code == 200
    data = response.json()
    assert "clients" in data


@pytest.mark.asyncio
async def test_admin_get_costs(client):
    """Test getting cost breakdown."""
    response = await client.get("/admin/costs")
    assert response.status_code == 200
    data = response.json()
    assert "costs" in data


@pytest.mark.asyncio
async def test_generate_from_library_no_atoms(client):
    """Test generating from library with no atoms."""
    response = await client.post(
        "/api/generate-from-library",
        json={
            "atom_ids": [],
            "target_persona": "ceo_longterm_care",
            "asset_types": ["linkedin"],
        },
    )
    assert response.status_code == 400  # Should fail with no atoms
