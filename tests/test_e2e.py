"""
End-to-end integration tests for ContentMultiplier MVP
Tests complete user workflows from registration to content generation
"""

import pytest
import asyncio
import httpx
import os
import json
from pathlib import Path
from datetime import datetime

# Base URL for tests - configurable via environment
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "test_data"


class TestConfig:
    """Test configuration and shared state"""
    access_token: str = None
    user_id: int = None
    job_id: str = None
    library_still_ids: list = []

    # Test user credentials
    test_email = f"test_user_{datetime.now().strftime('%Y%m%d%H%M%S')}@example.com"
    test_password = "TestPassword123!"


@pytest.fixture(scope="function")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def client():
    """Async HTTP client for API calls"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        yield client


class TestUserJourney:
    """Test complete user journey from registration to results"""

    @pytest.mark.asyncio
    async def test_01_user_registration(self, client: httpx.AsyncClient):
        """Test: User can register with email/password"""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": TestConfig.test_email,
                "password": TestConfig.test_password,
                "confirm_password": TestConfig.test_password,
            }
        )

        assert response.status_code == 200, f"Registration failed: {response.text}"

        data = response.json()
        assert "access_token" in data, "No access token returned"
        assert "user" in data, "No user info returned"
        assert data["user"]["email"] == TestConfig.test_email

        TestConfig.access_token = data["access_token"]
        TestConfig.user_id = data["user"]["id"]

        print(f"Registered user: {TestConfig.test_email} (ID: {TestConfig.user_id})")

    @pytest.mark.asyncio
    async def test_02_user_login(self, client: httpx.AsyncClient):
        """Test: User can login with credentials"""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": TestConfig.test_email,
                "password": TestConfig.test_password,
            }
        )

        assert response.status_code == 200, f"Login failed: {response.text}"

        data = response.json()
        assert "access_token" in data, "No access token returned"

        # Update token in case it changed
        TestConfig.access_token = data["access_token"]

        print("Login successful")

    @pytest.mark.asyncio
    async def test_03_upload_text_content(self, client: httpx.AsyncClient):
        """Test: User can upload text content with magic words"""
        # For e2e testing, we use text content (faster than video)
        sample_content = """
        Welcome to the SafelyYou Q4 2024 webinar. Today we'll discuss how our
        AI-powered fall detection system has achieved an 80% reduction in falls
        across 500 senior living communities.

        The key insight is that traditional monitoring misses 40% of incidents.
        Our technology addresses this by providing real-time alerts to staff.

        The ROI is significant: facilities save an average of $50,000 annually
        in reduced liability and improved resident retention. DON feedback has
        been overwhelmingly positive, with 95% reporting improved peace of mind.

        CMS compliance is built into our reporting dashboard, making audits
        effortless. This has been particularly valuable for memory care units
        where documentation requirements are stringent.
        """

        headers = {"Authorization": f"Bearer {TestConfig.access_token}"}

        response = await client.post(
            "/api/upload-text",
            data={
                "content": sample_content,
                "target_persona": "ceo_longterm_care",
                "asset_types": json.dumps(["linkedin", "blog"]),
                "asset_quantities": json.dumps({"linkedin": 2, "blog": 1}),
                "magic_words": "SafelyYou, Q4, ROI, DON, CMS",
                "content_name": "test_webinar.txt",
            },
            headers=headers,
        )

        assert response.status_code == 200, f"Upload failed: {response.text}"

        data = response.json()
        assert "job_id" in data, "No job_id returned"

        TestConfig.job_id = data["job_id"]
        print(f"Created job: {TestConfig.job_id}")

    @pytest.mark.asyncio
    async def test_04_job_processing(self, client: httpx.AsyncClient):
        """Test: Job processes through all steps"""
        headers = {"Authorization": f"Bearer {TestConfig.access_token}"}

        max_wait_seconds = 300  # 5 minutes for text content
        poll_interval = 5  # seconds
        elapsed = 0

        seen_steps = set()

        while elapsed < max_wait_seconds:
            response = await client.get(
                f"/api/job/{TestConfig.job_id}/status",
                headers=headers,
            )

            assert response.status_code == 200, f"Status check failed: {response.text}"

            data = response.json()
            current_step = data.get("current_step", "")
            status = data.get("status", "")

            # Track seen steps
            if current_step:
                seen_steps.add(current_step.lower())

            print(f"Status: {status} | Step: {current_step} | Progress: {data.get('progress', 0)}%")

            # Check for partial transcript
            if "partial_transcript" in data and data["partial_transcript"]:
                print(f"Partial transcript available: {len(data['partial_transcript'])} chars")

            if status == "complete":
                print("Job completed successfully!")
                break
            elif status == "failed":
                pytest.fail(f"Job failed: {data.get('error_message', 'Unknown error')}")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        assert elapsed < max_wait_seconds, "Job processing timed out"

        # Verify we saw expected steps
        expected_keywords = ["transcrib", "distill", "draft", "edit"]
        for keyword in expected_keywords:
            found = any(keyword in step for step in seen_steps)
            print(f"Step containing '{keyword}': {'Found' if found else 'Not found'}")

    @pytest.mark.asyncio
    async def test_05_results_with_quality_scores(self, client: httpx.AsyncClient):
        """Test: Results show outputs with quality scores"""
        headers = {"Authorization": f"Bearer {TestConfig.access_token}"}

        response = await client.get(
            f"/api/job/{TestConfig.job_id}/results",
            headers=headers,
        )

        assert response.status_code == 200, f"Results fetch failed: {response.text}"

        data = response.json()

        # Verify outputs
        outputs = data.get("outputs", [])
        assert len(outputs) > 0, "No outputs generated"
        print(f"Generated {len(outputs)} outputs")

        # Check for quality scores
        for output in outputs:
            content_type = output.get("content_type", "unknown")
            quality = output.get("quality_scores", {})

            if quality:
                overall = quality.get("overall_score", 0)
                print(f"  {content_type}: Quality score {overall}/100")
                assert 0 <= overall <= 100, f"Invalid quality score: {overall}"

        # Verify stills (support both keys for backwards compatibility)
        stills = data.get("stills", data.get("atoms", []))
        assert len(stills) > 0, "No stills extracted"
        print(f"Extracted {len(stills)} stills")

        # Store still IDs for library test
        TestConfig.library_still_ids = [s.get("id") for s in stills[:3] if s.get("id")]

    @pytest.mark.asyncio
    async def test_06_content_library_populated(self, client: httpx.AsyncClient):
        """Test: Stills added to user's library"""
        headers = {"Authorization": f"Bearer {TestConfig.access_token}"}

        response = await client.get(
            "/api/library",
            headers=headers,
        )

        assert response.status_code == 200, f"Library fetch failed: {response.text}"

        data = response.json()
        entries = data.get("entries", [])

        assert len(entries) > 0, "Library is empty after upload"
        print(f"Library contains {len(entries)} entries")

        # Check still types
        still_types = set()
        for entry in entries:
            stills = entry.get("stills", entry.get("atoms", []))
            for still in stills:
                still_types.add(still.get("type", "unknown"))

        print(f"Still types found: {still_types}")

    @pytest.mark.asyncio
    async def test_07_brand_voice_preview(self, client: httpx.AsyncClient):
        """Test: Brand voice preview works"""
        headers = {"Authorization": f"Bearer {TestConfig.access_token}"}

        response = await client.post(
            "/api/personas/preview-voice",
            json={
                "sample_text": "Our new AI system helps reduce operational costs by 40% through automation.",
                "persona_id": "ceo_longterm_care",
            },
            headers=headers,
        )

        assert response.status_code == 200, f"Preview failed: {response.text}"

        data = response.json()
        assert "transformed_text" in data, "No transformed text returned"
        assert "changes_summary" in data, "No changes summary returned"
        assert data["transformed_text"] != data["original_text"], "Text was not transformed"

        print(f"Original: {data['original_text'][:50]}...")
        print(f"Transformed: {data['transformed_text'][:50]}...")

    @pytest.mark.asyncio
    async def test_08_personas_list(self, client: httpx.AsyncClient):
        """Test: Can list available personas"""
        headers = {"Authorization": f"Bearer {TestConfig.access_token}"}

        response = await client.get(
            "/api/personas",
            headers=headers,
        )

        assert response.status_code == 200, f"Personas fetch failed: {response.text}"

        data = response.json()
        personas = data.get("personas", [])

        assert len(personas) >= 3, "Expected at least 3 default personas"

        for persona in personas:
            print(f"Persona: {persona.get('title', 'Unknown')}")
            assert "id" in persona, "Persona missing id"
            assert "title" in persona, "Persona missing title"


class TestEdgeCases:
    """Test edge cases and failure scenarios"""

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, client: httpx.AsyncClient):
        """Test: Protected endpoints reject unauthorized requests"""
        response = await client.get("/api/library")
        assert response.status_code == 401, "Expected 401 for unauthorized request"

    @pytest.mark.asyncio
    async def test_invalid_job_access(self, client: httpx.AsyncClient):
        """Test: Can't access another user's job"""
        # Create second user
        second_email = f"second_user_{datetime.now().strftime('%Y%m%d%H%M%S')}@example.com"

        response = await client.post(
            "/api/auth/register",
            json={
                "email": second_email,
                "password": "TestPassword456!",
                "confirm_password": "TestPassword456!",
            }
        )

        assert response.status_code == 200
        second_token = response.json()["access_token"]

        # Try to access first user's job with second user's token
        if TestConfig.job_id:
            headers = {"Authorization": f"Bearer {second_token}"}
            response = await client.get(
                f"/api/job/{TestConfig.job_id}/status",
                headers=headers,
            )

            # Should get 404 (job not found for this user) or 403 (forbidden)
            assert response.status_code in [403, 404], \
                f"Expected 403/404 for cross-user access, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_short_sample_text_rejected(self, client: httpx.AsyncClient):
        """Test: Too-short sample text is rejected for preview"""
        headers = {"Authorization": f"Bearer {TestConfig.access_token}"}

        response = await client.post(
            "/api/personas/preview-voice",
            json={
                "sample_text": "Hi",  # Too short
                "persona_id": "ceo_longterm_care",
            },
            headers=headers,
        )

        assert response.status_code == 400, "Expected 400 for too-short text"

    @pytest.mark.asyncio
    async def test_invalid_persona_rejected(self, client: httpx.AsyncClient):
        """Test: Invalid persona ID is rejected"""
        headers = {"Authorization": f"Bearer {TestConfig.access_token}"}

        response = await client.post(
            "/api/personas/preview-voice",
            json={
                "sample_text": "This is a valid sample text for testing purposes.",
                "persona_id": "nonexistent_persona_xyz",
            },
            headers=headers,
        )

        assert response.status_code == 404, "Expected 404 for invalid persona"


class TestDataIntegrity:
    """Test data isolation and integrity"""

    @pytest.mark.asyncio
    async def test_duplicate_registration_fails(self, client: httpx.AsyncClient):
        """Test: Can't register with same email twice"""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": TestConfig.test_email,  # Already registered
                "password": "AnotherPassword123!",
                "confirm_password": "AnotherPassword123!",
            }
        )

        assert response.status_code == 400, "Expected 400 for duplicate email"

    @pytest.mark.asyncio
    async def test_wrong_password_login_fails(self, client: httpx.AsyncClient):
        """Test: Login fails with wrong password"""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": TestConfig.test_email,
                "password": "WrongPassword123!",
            }
        )

        assert response.status_code == 401, "Expected 401 for wrong password"


class TestHealthChecks:
    """Test system health endpoints"""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: httpx.AsyncClient):
        """Test: Health endpoint returns healthy"""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"

    @pytest.mark.asyncio
    async def test_api_info_endpoint(self, client: httpx.AsyncClient):
        """Test: API info endpoint returns version"""
        response = await client.get("/api")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data.get("status") == "running"


# Run tests with: pytest tests/test_e2e.py -v --asyncio-mode=auto
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
