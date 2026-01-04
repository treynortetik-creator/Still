"""Tests for still matching service."""
import pytest
from app.services.still_matcher import fuzzy_match_score, match_stills


def test_fuzzy_match_score_identical():
    """Identical strings return 1.0."""
    score = fuzzy_match_score("Hello world", "Hello world")
    assert score == 1.0


def test_fuzzy_match_score_similar():
    """Similar strings return high score."""
    score = fuzzy_match_score(
        "Revenue increased by 40%",
        "Revenue increased by 52%"
    )
    assert score > 0.7


def test_fuzzy_match_score_different():
    """Different strings return low score."""
    score = fuzzy_match_score(
        "Revenue increased by 40%",
        "Customer satisfaction improved"
    )
    assert score < 0.5


@pytest.mark.asyncio
async def test_match_stills_finds_exact_match(test_db):
    """Exact matches are identified with high confidence."""
    old_stills = [
        {"id": "old1", "content": "Revenue grew 40% year over year", "still_type": "data"}
    ]
    new_stills = [
        {"id": "new1", "content": "Revenue grew 40% year over year", "still_type": "data"}
    ]

    matches, orphans = await match_stills(old_stills, new_stills, user_id=1)

    assert len(matches) == 1
    assert matches[0]["confidence"] == "high"
    assert matches[0]["old"]["id"] == "old1"
    assert matches[0]["new"]["id"] == "new1"
    assert len(orphans) == 0
