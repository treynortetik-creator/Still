"""Integration tests for still lifecycle management."""
import pytest
from datetime import date, timedelta


class TestStillLifecycleFlow:
    """Integration tests for the full still lifecycle flow."""

    @pytest.mark.asyncio
    async def test_still_lifecycle_flow(self, test_db):
        """Test full lifecycle: still with expiration -> check expiration -> status update."""
        from app.services.lifecycle import check_expiring_stills, get_lifecycle_summary, update_still_status
        from app.database import get_db

        # 1. First create a job (required for foreign key constraint)
        async with get_db() as db:
            await db.execute("""
                INSERT INTO jobs (id, user_id, status, original_filename, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, ("test-lifecycle-job", 1, "completed", "test.txt"))
            await db.commit()

        # 2. Create a test still with expiration date in 7 days
        async with get_db() as db:
            expiration = (date.today() + timedelta(days=7)).isoformat()
            await db.execute("""
                INSERT INTO stills (id, job_id, user_id, still_type, content, status, expiration_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, ("test-still-lifecycle-1", "test-lifecycle-job", 1, "data", "Test lifecycle content", "active", expiration))
            await db.commit()

        # 3. Check expiring stills with 30-day threshold (should flag our 7-day still)
        count = await check_expiring_stills(days_threshold=30)
        assert count >= 1, f"Should flag at least one expiring still, got {count}"

        # 4. Verify status was updated to needs_review
        async with get_db() as db:
            cursor = await db.execute("SELECT status FROM stills WHERE id = ?", ("test-still-lifecycle-1",))
            row = await cursor.fetchone()
            assert row is not None, "Still should exist"
            assert row[0] == "needs_review", f"Status should be 'needs_review', got '{row[0]}'"

        # 5. Get lifecycle summary for user
        summary = await get_lifecycle_summary(user_id=1)
        assert "needs_review" in summary, "Summary should include needs_review count"
        assert summary["needs_review"] >= 1, f"Should have at least 1 needs_review still, got {summary['needs_review']}"

        # 6. Manually update status to evergreen
        success = await update_still_status("test-still-lifecycle-1", "evergreen")
        assert success is True, "Update should succeed"

        # 7. Verify final status
        async with get_db() as db:
            cursor = await db.execute("SELECT status FROM stills WHERE id = ?", ("test-still-lifecycle-1",))
            row = await cursor.fetchone()
            assert row is not None, "Still should still exist"
            assert row[0] == "evergreen", f"Status should be 'evergreen', got '{row[0]}'"

    @pytest.mark.asyncio
    async def test_expiration_only_affects_active_stills(self, test_db):
        """Test that expiration check only affects active stills."""
        from app.services.lifecycle import check_expiring_stills
        from app.database import get_db

        # Create a job first
        async with get_db() as db:
            await db.execute("""
                INSERT INTO jobs (id, user_id, status, original_filename, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, ("test-expiration-job", 1, "completed", "test.txt"))
            await db.commit()

        # Create a still that's already evergreen with near expiration
        async with get_db() as db:
            expiration = (date.today() + timedelta(days=5)).isoformat()
            await db.execute("""
                INSERT INTO stills (id, job_id, user_id, still_type, content, status, expiration_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, ("test-still-evergreen", "test-expiration-job", 1, "insight", "Evergreen content", "evergreen", expiration))
            await db.commit()

        # Run expiration check
        await check_expiring_stills(days_threshold=30)

        # Verify evergreen still was NOT changed
        async with get_db() as db:
            cursor = await db.execute("SELECT status FROM stills WHERE id = ?", ("test-still-evergreen",))
            row = await cursor.fetchone()
            assert row[0] == "evergreen", f"Evergreen still should remain evergreen, got '{row[0]}'"

    @pytest.mark.asyncio
    async def test_lifecycle_summary_counts(self, test_db):
        """Test lifecycle summary returns correct counts."""
        from app.services.lifecycle import get_lifecycle_summary
        from app.database import get_db

        # Create a job first
        async with get_db() as db:
            await db.execute("""
                INSERT INTO jobs (id, user_id, status, original_filename, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, ("test-summary-job", 1, "completed", "test.txt"))
            await db.commit()

        # Create stills with different statuses
        async with get_db() as db:
            # Active still
            await db.execute("""
                INSERT INTO stills (id, job_id, user_id, still_type, content, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, ("test-active-1", "test-summary-job", 1, "data", "Active content", "active"))

            # Evergreen still
            await db.execute("""
                INSERT INTO stills (id, job_id, user_id, still_type, content, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, ("test-evergreen-1", "test-summary-job", 1, "story", "Evergreen content", "evergreen"))

            # Retired still
            await db.execute("""
                INSERT INTO stills (id, job_id, user_id, still_type, content, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, ("test-retired-1", "test-summary-job", 1, "quote", "Retired content", "retired"))

            await db.commit()

        # Get summary
        summary = await get_lifecycle_summary(user_id=1)

        # Verify all status keys exist
        assert "active" in summary
        assert "evergreen" in summary
        assert "needs_review" in summary
        assert "retired" in summary
        assert "expiring_soon" in summary

        # Verify counts are at least what we just created
        assert summary["active"] >= 1
        assert summary["evergreen"] >= 1
        assert summary["retired"] >= 1

    @pytest.mark.asyncio
    async def test_update_status_invalid_values(self, test_db):
        """Test that update_still_status rejects invalid values."""
        from app.services.lifecycle import update_still_status
        import pytest

        with pytest.raises(ValueError, match="Invalid status"):
            await update_still_status("some-id", "invalid_status")

        with pytest.raises(ValueError, match="still_id is required"):
            await update_still_status("", "active")

    @pytest.mark.asyncio
    async def test_update_status_nonexistent_still(self, test_db):
        """Test that updating a nonexistent still returns False."""
        from app.services.lifecycle import update_still_status

        success = await update_still_status("nonexistent-still-id", "active")
        assert success is False


class TestAllStillTypesValidation:
    """Tests for validating all 10 still types."""

    def test_all_still_types_valid_in_library_manager(self):
        """Test all 10 still types are accepted by validation."""
        from app.services.library_manager import validate_still, VALID_STILL_TYPES

        all_types = ['data', 'insight', 'story', 'problem', 'solution', 'quote',
                     'framework', 'definition', 'question', 'proof_point']

        # Verify VALID_STILL_TYPES matches our expected types
        assert len(VALID_STILL_TYPES) == 10, f"Expected 10 still types, got {len(VALID_STILL_TYPES)}"
        for still_type in all_types:
            assert still_type in VALID_STILL_TYPES, f"Type {still_type} should be in VALID_STILL_TYPES"

        # Test each type is validated correctly
        for still_type in all_types:
            still = {
                "still_type": still_type,
                "content": f"Test content for {still_type}",
            }
            validated = validate_still(still)
            assert validated["still_type"] == still_type, f"Type {still_type} should be valid after validation"

    def test_invalid_still_type_defaults_to_insight(self):
        """Test that invalid still types default to insight."""
        from app.services.library_manager import validate_still

        still = {
            "still_type": "completely_invalid_type",
            "content": "Some content",
        }
        validated = validate_still(still)
        assert validated["still_type"] == "insight", "Invalid type should default to 'insight'"

    def test_still_type_enum_matches_library_manager(self):
        """Test that StillType enum and VALID_STILL_TYPES are in sync."""
        from app.models.stills import StillType
        from app.services.library_manager import VALID_STILL_TYPES

        enum_types = [t.value for t in StillType]

        # Both should have exactly 10 types
        assert len(enum_types) == 10
        assert len(VALID_STILL_TYPES) == 10

        # All types should match
        for t in enum_types:
            assert t in VALID_STILL_TYPES, f"Enum type '{t}' not in VALID_STILL_TYPES"
        for t in VALID_STILL_TYPES:
            assert t in enum_types, f"VALID_STILL_TYPES type '{t}' not in enum"


class TestLifecycleFieldsValidation:
    """Tests for lifecycle field validation."""

    def test_validate_funnel_stages(self):
        """Test funnel stage validation."""
        from app.services.library_manager import validate_still, VALID_FUNNEL_STAGES

        valid_stages = ["awareness", "consideration", "decision"]
        assert VALID_FUNNEL_STAGES == valid_stages

        for stage in valid_stages:
            still = {
                "still_type": "data",
                "content": "Test",
                "funnel_stage": stage,
            }
            validated = validate_still(still)
            assert validated["funnel_stage"] == stage

    def test_validate_status_values(self):
        """Test status value validation."""
        from app.services.library_manager import validate_still, VALID_STATUSES

        valid_statuses = ["active", "evergreen", "needs_review", "retired"]
        assert VALID_STATUSES == valid_statuses

        for status in valid_statuses:
            still = {
                "still_type": "data",
                "content": "Test",
                "status": status,
            }
            validated = validate_still(still)
            assert validated["status"] == status

    def test_validate_performance_values(self):
        """Test performance value validation."""
        from app.services.library_manager import validate_still, VALID_PERFORMANCE_VALUES

        valid_performance = ["high", "medium", "low", "untested"]
        assert VALID_PERFORMANCE_VALUES == valid_performance

        for perf in valid_performance:
            still = {
                "still_type": "data",
                "content": "Test",
                "performance": perf,
            }
            validated = validate_still(still)
            assert validated["performance"] == perf

    def test_validate_expiration_date_format(self):
        """Test expiration date format validation."""
        from app.services.library_manager import validate_still

        # Valid date (YYYY-MM-DD format)
        still = {
            "still_type": "data",
            "content": "Test",
            "expiration_date": "2025-12-31",
        }
        validated = validate_still(still)
        assert validated["expiration_date"] == "2025-12-31"

        # Wrong length - rejected
        still = {
            "still_type": "data",
            "content": "Test",
            "expiration_date": "2025-1-31",  # Single digit month
        }
        validated = validate_still(still)
        assert validated["expiration_date"] is None

        # Non-string - rejected
        still = {
            "still_type": "data",
            "content": "Test",
            "expiration_date": 20251231,
        }
        validated = validate_still(still)
        assert validated["expiration_date"] is None

        # Completely invalid - rejected
        still = {
            "still_type": "data",
            "content": "Test",
            "expiration_date": "not-a-date",
        }
        validated = validate_still(still)
        assert validated["expiration_date"] is None

    def test_validate_best_formats(self):
        """Test best_formats list validation."""
        from app.services.library_manager import validate_still

        # Valid list
        still = {
            "still_type": "data",
            "content": "Test",
            "best_formats": ["linkedin", "email", "blog"],
        }
        validated = validate_still(still)
        assert validated["best_formats"] == ["linkedin", "email", "blog"]

        # String instead of list
        still = {
            "still_type": "data",
            "content": "Test",
            "best_formats": "linkedin",
        }
        validated = validate_still(still)
        assert validated["best_formats"] == []
