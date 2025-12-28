"""Tests for database operations."""
import json
import pytest
from app.database import get_db, init_db


@pytest.mark.asyncio
async def test_database_initialization(test_db):
    """Test database is properly initialized."""
    async with get_db() as db:
        # Check tables exist
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in await cursor.fetchall()]

        assert "users" in tables
        assert "jobs" in tables
        assert "stills" in tables  # renamed from atoms
        assert "outputs" in tables
        assert "content_library" in tables
        assert "prompt_templates" in tables


@pytest.mark.asyncio
async def test_default_user_created(test_db):
    """Test default user is created."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE email = ?",
            ("default@contentmultiplier.com",)
        )
        user = await cursor.fetchone()

        assert user is not None
        assert user["subscription_tier"] == "pro"


@pytest.mark.asyncio
async def test_create_job(test_db):
    """Test creating a job."""
    import uuid

    job_id = str(uuid.uuid4())

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO jobs (id, user_id, status, original_filename, target_persona)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, 1, "uploading", "test.txt", "ceo_longterm_care")
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = await cursor.fetchone()

        assert job is not None
        assert job["id"] == job_id
        assert job["status"] == "uploading"
        assert job["target_persona"] == "ceo_longterm_care"


@pytest.mark.asyncio
async def test_create_still(test_db):
    """Test creating a still (formerly atom)."""
    import uuid

    job_id = str(uuid.uuid4())
    still_id = str(uuid.uuid4())

    async with get_db() as db:
        # Create job first
        await db.execute(
            "INSERT INTO jobs (id, user_id, status) VALUES (?, ?, ?)",
            (job_id, 1, "complete")
        )

        # Create still
        await db.execute(
            """
            INSERT INTO stills (id, job_id, user_id, still_type, content, tags, persona_relevance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                still_id,
                job_id,
                1,
                "data",
                "40% improvement",
                json.dumps(["roi", "metrics"]),
                json.dumps({"ceo_longterm_care": 5})
            )
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM stills WHERE id = ?", (still_id,))
        still = await cursor.fetchone()

        assert still is not None
        assert still["still_type"] == "data"
        assert still["content"] == "40% improvement"


@pytest.mark.asyncio
async def test_create_library_entry(test_db):
    """Test creating a library entry."""
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO content_library (user_id, entry_type, content, tags)
            VALUES (?, ?, ?, ?)
            """,
            (1, "insight", "Best practice for retention", json.dumps(["retention"]))
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM content_library WHERE user_id = ?"
            , (1,)
        )
        entry = await cursor.fetchone()

        assert entry is not None
        assert entry["entry_type"] == "insight"
        assert entry["times_used"] == 0


@pytest.mark.asyncio
async def test_update_job_status(test_db):
    """Test updating job status."""
    import uuid

    job_id = str(uuid.uuid4())

    async with get_db() as db:
        # Create job
        await db.execute(
            "INSERT INTO jobs (id, user_id, status, progress) VALUES (?, ?, ?, ?)",
            (job_id, 1, "uploading", 0)
        )
        await db.commit()

        # Update status
        await db.execute(
            "UPDATE jobs SET status = ?, progress = ? WHERE id = ?",
            ("atomizing", 30, job_id)
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = await cursor.fetchone()

        assert job["status"] == "atomizing"
        assert job["progress"] == 30


@pytest.mark.asyncio
async def test_foreign_key_constraint(test_db):
    """Test foreign key constraints work."""
    import uuid
    import sqlite3

    async with get_db() as db:
        # Try to create still with non-existent job_id
        with pytest.raises(Exception):  # Should fail due to FK constraint
            await db.execute(
                """
                INSERT INTO stills (id, job_id, user_id, still_type, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), "nonexistent-job", 1, "data", "test")
            )
            await db.commit()
