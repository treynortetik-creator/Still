"""Pytest configuration and fixtures."""
import os
import pytest
import asyncio
from pathlib import Path
from httpx import AsyncClient, ASGITransport

# Set test environment BEFORE importing app modules
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

# Use a separate test database to avoid affecting production
TEST_DB_PATH = Path(__file__).parent.parent / "database" / "test_contentmultiplier.db"

# Override DATABASE_PATH before importing app modules
import app.database as db_module
db_module.DATABASE_PATH = TEST_DB_PATH

from app.main import app
from app.database import init_db


@pytest.fixture(scope="function")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_db():
    """Initialize test database (separate from production)."""
    # Ensure test database directory exists
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing test database
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    # Initialize fresh database
    await init_db()

    yield TEST_DB_PATH

    # Cleanup
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
async def client(test_db):
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_client(test_db):
    """Create authenticated async test client with a registered user.

    Uses the default user created by init_db to avoid rate limiting issues.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Use the default user and create a token for it directly
        # The default user (id=1) is created by init_db
        from app.services.auth import create_access_token
        token = create_access_token({"sub": "1", "email": "default@contentmultiplier.com"})

        # Add auth header to all requests
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


@pytest.fixture
def sample_transcript():
    """Sample transcript for testing."""
    return """
    Speaker 1: Welcome everyone to today's webinar on improving staff retention in senior care facilities.

    We've seen some incredible results over the past year. Our data shows a 40% reduction in turnover
    when facilities implement our three-step framework.

    The first step is recognition. Staff need to feel valued. One facility, Sunrise Senior Living,
    implemented a peer recognition program and saw turnover drop from 85% to 52% in just six months.

    The second step is training. When staff feel competent, they stay longer. We recommend at least
    20 hours of specialized training in the first month.

    And the third step is flexibility. Offering flexible scheduling has become critical, especially
    post-pandemic. 73% of CNAs cite schedule flexibility as a top factor in job satisfaction.

    The bottom line? Investing in your staff isn't just the right thing to do - it's the profitable
    thing to do. Every 1% reduction in turnover saves approximately $50,000 per year for a 100-bed facility.

    Thank you for joining us today.
    """


@pytest.fixture
def sample_stills():
    """Sample stills for testing."""
    return [
        {
            "id": "still-001",
            "still_type": "data",
            "content": "40% reduction in turnover",
            "source_location": "intro",
            "persona_relevance": {"ceo_longterm_care": 5},
        },
        {
            "id": "still-002",
            "still_type": "story",
            "content": "Sunrise Senior Living implemented a peer recognition program and saw turnover drop from 85% to 52%",
            "source_location": "step 1",
            "persona_relevance": {"ceo_longterm_care": 4},
        },
        {
            "id": "still-003",
            "still_type": "insight",
            "content": "Three-step framework: recognition, training, flexibility",
            "source_location": "main body",
            "persona_relevance": {"don_memory_care": 5},
        },
    ]
