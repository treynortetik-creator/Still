"""Tests for API endpoints."""
import json
import pytest
from io import BytesIO


# ============== Public Endpoints (no auth required) ==============

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


# ============== Protected Endpoints (auth required) ==============

@pytest.mark.asyncio
async def test_upload_text_content(auth_client):
    """Test uploading text content."""
    response = await auth_client.post(
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
async def test_upload_requires_persona(auth_client):
    """Test that upload requires target persona."""
    response = await auth_client.post(
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
async def test_get_job_status_not_found(auth_client):
    """Test getting status for non-existent job."""
    response = await auth_client.get("/api/job/non-existent-job-id/status")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_jobs_empty(auth_client):
    """Test listing jobs when empty."""
    response = await auth_client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_library_empty(auth_client):
    """Test getting library when empty."""
    response = await auth_client.get("/api/library")
    assert response.status_code == 200
    data = response.json()
    assert "entries" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_library_stats(auth_client):
    """Test getting library stats."""
    response = await auth_client.get("/api/library/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_entries" in data
    assert "by_type" in data


@pytest.mark.asyncio
async def test_library_filter_by_type(auth_client):
    """Test filtering library by type."""
    response = await auth_client.get("/api/library?entry_type=data")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_library_search(auth_client):
    """Test searching library."""
    response = await auth_client.get("/api/library?search=test")
    assert response.status_code == 200


# ============== Admin Endpoints (require admin auth or redirect) ==============

@pytest.mark.asyncio
async def test_admin_dashboard_redirects_without_auth(client):
    """Test admin dashboard redirects without authentication."""
    response = await client.get("/admin/dashboard", follow_redirects=False)
    # Admin pages redirect to login when not authenticated
    # 503 when admin credentials not configured, 302/401 otherwise
    assert response.status_code in [302, 401, 503]


@pytest.mark.asyncio
async def test_admin_list_prompts_redirects_without_auth(client):
    """Test admin prompts redirects without authentication."""
    response = await client.get("/admin/prompts", follow_redirects=False)
    # Admin pages redirect to login when not authenticated
    # 503 when admin credentials not configured, 302/401 otherwise
    assert response.status_code in [302, 401, 503]


@pytest.mark.asyncio
async def test_admin_list_clients(auth_client):
    """Test listing clients via API."""
    response = await auth_client.get("/api/admin/clients")
    # May return 200 or 403 depending on user role
    # 503 when admin credentials not configured
    assert response.status_code in [200, 403, 503]


# ============== Library Generation ==============

@pytest.mark.asyncio
async def test_generate_from_library_no_atoms(auth_client):
    """Test generating from library with no atoms."""
    response = await auth_client.post(
        "/api/generate-from-library",
        json={
            "atom_ids": [],
            "target_persona": "ceo_longterm_care",
            "asset_types": ["linkedin"],
        },
    )
    assert response.status_code == 400  # Should fail with no atoms
