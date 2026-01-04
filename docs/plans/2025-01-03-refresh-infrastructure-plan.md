# Refresh Phase Infrastructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the Refresh phase infrastructure including dashboard, automatic status updates, performance tracking, bulk actions, and source refresh workflow with smart merging.

**Architecture:** New `/refresh.html` page with three-column layout showing sources needing review, stills needing attention, and top performers. Background task service for automatic maintenance. Hybrid matching service (fuzzy + LLM) for source refresh workflow. API layer at `/api/refresh/` for all operations.

**Tech Stack:** Python/FastAPI backend, vanilla JS + Tailwind frontend, SQLite/PostgreSQL database, OpenRouter LLM for uncertain matching.

---

## Task 1: Add Refresh Settings to Database

**Files:**
- Modify: `app/database.py` (add settings inserts)
- Modify: `app/api/admin_views.py` (settings endpoint)

**Step 1: Add default refresh settings to database init**

In `app/database.py`, find the settings table initialization and add:

```python
# In init_db() after settings table creation, add default refresh settings
refresh_settings = [
    ('still_matching_model', 'google/gemini-flash-1.5'),
    ('fuzzy_match_high_threshold', '0.85'),
    ('fuzzy_match_low_threshold', '0.50'),
    ('auto_retire_expired', 'true'),
    ('expiration_warning_days', '30'),
]
for key, value in refresh_settings:
    await execute(db,
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        (key, value)
    )
```

**Step 2: Test settings exist**

Run: `python3 -c "from app.database import init_db; import asyncio; asyncio.run(init_db())"`

Verify settings were added by checking the database.

**Step 3: Commit**

```bash
git add app/database.py
git commit -m "feat: add refresh settings to database initialization"
```

---

## Task 2: Create Still Matching Prompt Template

**Files:**
- Create: `data/prompts/still_matching.txt`

**Step 1: Create the prompt file**

```text
You are comparing content stills to find matches between an old source and a new version.

OLD STILL:
{old_still_content}
Type: {old_still_type}

NEW STILL CANDIDATES:
{new_still_candidates}

SOURCE CONTEXT:
{source_context}

Determine if any of the new still candidates are an updated version of the old still.
Consider:
- Same core statistic with updated numbers (e.g., "40% ROI" → "52% ROI")
- Same quote with minor wording changes
- Same insight reframed or expanded
- Same story with additional details

A match means the NEW still is an UPDATE of the OLD still, not just similar content.

OUTPUT FORMAT (valid JSON):
{
  "match_found": true,
  "matched_candidate_index": 0,
  "confidence": "high",
  "reasoning": "Both stills reference the same ROI statistic, with updated percentage"
}

If no match found:
{
  "match_found": false,
  "matched_candidate_index": null,
  "confidence": "high",
  "reasoning": "No candidates appear to be updates of the old still"
}
```

**Step 2: Verify prompt loads**

Run: `python3 -c "from app.services.prompt_manager import get_rendered_prompt; import asyncio; p, c = asyncio.run(get_rendered_prompt('still_matching', {'old_still_content': 'test', 'old_still_type': 'data', 'new_still_candidates': 'test', 'source_context': 'test'})); print('OK' if p else 'FAIL')"`

**Step 3: Commit**

```bash
git add data/prompts/still_matching.txt
git commit -m "feat: add still matching prompt template"
```

---

## Task 3: Create Refresh Tasks Service

**Files:**
- Create: `app/services/refresh_tasks.py`
- Create: `tests/test_refresh_tasks.py`

**Step 1: Write the failing test**

Create `tests/test_refresh_tasks.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_refresh_tasks.py -v`
Expected: FAIL with "cannot import name 'run_refresh_maintenance'"

**Step 3: Write the implementation**

Create `app/services/refresh_tasks.py`:

```python
"""Refresh maintenance tasks service."""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchall, fetchone

logger = logging.getLogger(__name__)
settings = get_settings()


async def get_setting(key: str, default: str = None) -> str:
    """Get a setting value from the database."""
    async with get_db() as db:
        row = await fetchone(db, "SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default


async def get_stills_needing_attention(user_id: int) -> Dict[str, List[dict]]:
    """
    Get all stills that need attention, grouped by reason.

    Categories:
    - expired: expiration_date < today
    - needs_review: status = 'needs_review'
    - never_used: usage_count = 0 AND created_at > 30 days ago
    - low_performance: performance = 'low'
    """
    result = {
        "expired": [],
        "needs_review": [],
        "never_used": [],
        "low_performance": [],
    }

    today = datetime.now().date().isoformat()
    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()

    async with get_db() as db:
        # Expired stills
        rows = await fetchall(db, """
            SELECT s.*, j.campaign_name as source_name
            FROM stills s
            LEFT JOIN jobs j ON s.job_id = j.id
            WHERE s.user_id = ?
            AND s.expiration_date < ?
            AND s.status != 'retired'
            ORDER BY s.expiration_date ASC
        """, (user_id, today))
        result["expired"] = [dict(r) for r in rows]

        # Needs review
        rows = await fetchall(db, """
            SELECT s.*, j.campaign_name as source_name
            FROM stills s
            LEFT JOIN jobs j ON s.job_id = j.id
            WHERE s.user_id = ? AND s.status = 'needs_review'
            ORDER BY s.expiration_date ASC NULLS LAST
        """, (user_id,))
        result["needs_review"] = [dict(r) for r in rows]

        # Never used (older than 30 days)
        rows = await fetchall(db, """
            SELECT s.*, j.campaign_name as source_name
            FROM stills s
            LEFT JOIN jobs j ON s.job_id = j.id
            WHERE s.user_id = ?
            AND (s.usage_count = 0 OR s.usage_count IS NULL)
            AND s.created_at < ?
            AND s.status = 'active'
            ORDER BY s.created_at ASC
        """, (user_id, thirty_days_ago))
        result["never_used"] = [dict(r) for r in rows]

        # Low performance
        rows = await fetchall(db, """
            SELECT s.*, j.campaign_name as source_name
            FROM stills s
            LEFT JOIN jobs j ON s.job_id = j.id
            WHERE s.user_id = ? AND s.performance = 'low'
            ORDER BY s.usage_count DESC
        """, (user_id,))
        result["low_performance"] = [dict(r) for r in rows]

    return result


async def get_sources_needing_review(user_id: int, days_threshold: int = 14) -> List[dict]:
    """
    Get sources where review_date has passed or is within threshold days.
    """
    threshold_date = (datetime.now() + timedelta(days=days_threshold)).date().isoformat()

    async with get_db() as db:
        rows = await fetchall(db, """
            SELECT src.*, j.campaign_name, j.source_summary,
                   (SELECT COUNT(*) FROM stills WHERE job_id = src.job_id) as still_count
            FROM sources src
            JOIN jobs j ON src.job_id = j.id
            WHERE src.user_id = ? AND src.review_date <= ?
            ORDER BY src.review_date ASC
        """, (user_id, threshold_date))

        return [dict(r) for r in rows]


async def get_top_performers(user_id: int, limit: int = 10) -> List[dict]:
    """Get stills with highest usage and/or high performance rating."""
    async with get_db() as db:
        rows = await fetchall(db, """
            SELECT s.*, j.campaign_name as source_name
            FROM stills s
            LEFT JOIN jobs j ON s.job_id = j.id
            WHERE s.user_id = ?
            AND s.status IN ('active', 'evergreen')
            AND (s.performance = 'high' OR s.usage_count > 0)
            ORDER BY
                CASE WHEN s.performance = 'high' THEN 0 ELSE 1 END,
                s.usage_count DESC
            LIMIT ?
        """, (user_id, limit))

        return [dict(r) for r in rows]


async def run_refresh_maintenance(user_id: int = None) -> Dict[str, int]:
    """
    Run all automatic status updates.

    1. Mark stills expiring within N days as needs_review
    2. Auto-retire stills past expiration_date (if enabled)
    3. Count sources needing review

    Returns summary of changes made.
    """
    results = {
        "stills_marked_needs_review": 0,
        "stills_retired": 0,
        "sources_flagged": 0,
    }

    # Get settings
    warning_days = int(await get_setting('expiration_warning_days', '30'))
    auto_retire = (await get_setting('auto_retire_expired', 'true')).lower() == 'true'

    warning_date = (datetime.now() + timedelta(days=warning_days)).date().isoformat()
    today = datetime.now().date().isoformat()

    async with get_db() as db:
        # Build user filter
        user_filter = "AND user_id = ?" if user_id else ""
        user_params = (user_id,) if user_id else ()

        # 1. Mark stills expiring soon as needs_review
        if settings.use_postgres:
            result = await db.execute(f"""
                UPDATE stills
                SET status = 'needs_review'
                WHERE status = 'active'
                AND expiration_type != 'evergreen'
                AND expiration_date IS NOT NULL
                AND expiration_date <= $1
                AND expiration_date > $2
                {user_filter.replace('?', '$3') if user_id else ''}
            """, warning_date, today, *user_params)
            results["stills_marked_needs_review"] = int(result.split()[-1]) if result else 0
        else:
            cursor = await db.execute(f"""
                UPDATE stills
                SET status = 'needs_review'
                WHERE status = 'active'
                AND expiration_type != 'evergreen'
                AND expiration_date IS NOT NULL
                AND expiration_date <= ?
                AND expiration_date > ?
                {user_filter}
            """, (warning_date, today) + user_params)
            results["stills_marked_needs_review"] = cursor.rowcount
            await db.commit()

        # 2. Auto-retire expired stills (if enabled)
        if auto_retire:
            if settings.use_postgres:
                result = await db.execute(f"""
                    UPDATE stills
                    SET status = 'retired'
                    WHERE status IN ('active', 'needs_review')
                    AND expiration_type != 'evergreen'
                    AND expiration_date IS NOT NULL
                    AND expiration_date < $1
                    {user_filter.replace('?', '$2') if user_id else ''}
                """, today, *user_params)
                results["stills_retired"] = int(result.split()[-1]) if result else 0
            else:
                cursor = await db.execute(f"""
                    UPDATE stills
                    SET status = 'retired'
                    WHERE status IN ('active', 'needs_review')
                    AND expiration_type != 'evergreen'
                    AND expiration_date IS NOT NULL
                    AND expiration_date < ?
                    {user_filter}
                """, (today,) + user_params)
                results["stills_retired"] = cursor.rowcount
                await db.commit()

        # 3. Count sources needing review
        row = await fetchone(db, f"""
            SELECT COUNT(*) as count FROM sources
            WHERE review_date <= ?
            {user_filter}
        """, (today,) + user_params)
        results["sources_flagged"] = row["count"] if row else 0

    logger.info(f"Refresh maintenance complete: {results}")
    return results


async def get_refresh_counts(user_id: int) -> Dict[str, int]:
    """Get counts for notification badge."""
    today = datetime.now().date().isoformat()
    threshold_date = (datetime.now() + timedelta(days=14)).date().isoformat()

    async with get_db() as db:
        # Sources needing review
        source_row = await fetchone(db, """
            SELECT COUNT(*) as count FROM sources
            WHERE user_id = ? AND review_date <= ?
        """, (user_id, threshold_date))

        # Stills needing attention (needs_review status OR expired)
        still_row = await fetchone(db, """
            SELECT COUNT(*) as count FROM stills
            WHERE user_id = ?
            AND (status = 'needs_review' OR (expiration_date < ? AND status != 'retired'))
        """, (user_id, today))

        return {
            "sources": source_row["count"] if source_row else 0,
            "stills": still_row["count"] if still_row else 0,
        }
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_refresh_tasks.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/refresh_tasks.py tests/test_refresh_tasks.py
git commit -m "feat: add refresh tasks service with maintenance functions"
```

---

## Task 4: Create Still Matcher Service

**Files:**
- Create: `app/services/still_matcher.py`
- Create: `tests/test_still_matcher.py`

**Step 1: Write the failing test**

Create `tests/test_still_matcher.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_still_matcher.py -v`
Expected: FAIL with "cannot import name 'fuzzy_match_score'"

**Step 3: Write the implementation**

Create `app/services/still_matcher.py`:

```python
"""Still matching service for source refresh workflow."""
import logging
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional

from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.services.prompt_manager import get_rendered_prompt
from app.services.refresh_tasks import get_setting
from app.utils.json_parser import parse_llm_json

logger = logging.getLogger(__name__)


def fuzzy_match_score(text1: str, text2: str) -> float:
    """
    Calculate similarity score between two text strings.
    Uses SequenceMatcher for token-based comparison.

    Returns float between 0.0 (no match) and 1.0 (identical).
    """
    if not text1 or not text2:
        return 0.0

    # Normalize texts
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()

    # Use SequenceMatcher for similarity
    return SequenceMatcher(None, t1, t2).ratio()


def find_best_fuzzy_match(
    new_still: dict,
    old_stills: List[dict]
) -> Tuple[Optional[dict], float]:
    """
    Find the best matching old still for a new still using fuzzy matching.

    Returns (best_match, score) tuple.
    """
    if not old_stills:
        return None, 0.0

    best_match = None
    best_score = 0.0

    for old_still in old_stills:
        score = fuzzy_match_score(new_still["content"], old_still["content"])

        # Boost score if same type
        if new_still.get("still_type") == old_still.get("still_type"):
            score = min(1.0, score + 0.05)

        if score > best_score:
            best_score = score
            best_match = old_still

    return best_match, best_score


async def llm_match(
    old_still: dict,
    new_still_candidates: List[dict],
    source_context: str,
    user_id: int,
) -> dict:
    """
    Use LLM to determine if any candidates match the old still.

    Returns match result dict.
    """
    # Get model from settings
    model = await get_setting('still_matching_model', 'google/gemini-flash-1.5')

    # Format candidates for prompt
    candidates_text = "\n".join([
        f"[{i}] ({c.get('still_type', 'unknown').upper()}) {c['content']}"
        for i, c in enumerate(new_still_candidates)
    ])

    variables = {
        "old_still_content": old_still["content"],
        "old_still_type": old_still.get("still_type", "unknown"),
        "new_still_candidates": candidates_text,
        "source_context": source_context or "No additional context",
    }

    prompt, _ = await get_rendered_prompt("still_matching", variables)

    try:
        response_text, _, _, _ = await call_llm_text(
            prompt=prompt,
            step="still_matching",
            response_format="json",
            user_id=user_id,
        )

        result = parse_llm_json(response_text, context="still matching")

        if result.get("match_found") and result.get("matched_candidate_index") is not None:
            idx = result["matched_candidate_index"]
            if 0 <= idx < len(new_still_candidates):
                return {
                    "old": old_still,
                    "new": new_still_candidates[idx],
                    "confidence": result.get("confidence", "medium"),
                    "reasoning": result.get("reasoning", ""),
                    "match_type": "llm",
                }

        return {
            "old": old_still,
            "new": None,
            "confidence": result.get("confidence", "medium"),
            "reasoning": result.get("reasoning", "No match found"),
            "match_type": "llm",
        }

    except Exception as e:
        logger.error(f"LLM matching failed: {e}")
        return {
            "old": old_still,
            "new": None,
            "confidence": "low",
            "reasoning": f"LLM matching error: {str(e)}",
            "match_type": "error",
        }


async def match_stills(
    old_stills: List[dict],
    new_stills: List[dict],
    user_id: int,
    source_context: str = "",
) -> Tuple[List[dict], List[dict]]:
    """
    Match old stills to new stills using hybrid fuzzy + LLM approach.

    Args:
        old_stills: List of existing stills from source
        new_stills: List of new stills from refreshed source
        user_id: User ID for LLM calls
        source_context: Optional context about the source

    Returns:
        (matches, orphans) tuple where:
        - matches: List of {old, new, confidence, match_type} dicts
        - orphans: List of old stills with no match (should be retired)
    """
    # Get thresholds from settings
    high_threshold = float(await get_setting('fuzzy_match_high_threshold', '0.85'))
    low_threshold = float(await get_setting('fuzzy_match_low_threshold', '0.50'))

    matches = []
    matched_old_ids = set()
    matched_new_ids = set()
    uncertain_pairs = []

    # First pass: fuzzy matching
    for new_still in new_stills:
        best_match, score = find_best_fuzzy_match(new_still, old_stills)

        if score >= high_threshold and best_match:
            # High confidence match
            matches.append({
                "old": best_match,
                "new": new_still,
                "confidence": "high",
                "score": score,
                "match_type": "fuzzy",
            })
            matched_old_ids.add(best_match["id"])
            matched_new_ids.add(new_still["id"])
        elif score >= low_threshold and best_match:
            # Uncertain - queue for LLM
            uncertain_pairs.append({
                "old": best_match,
                "new": new_still,
                "score": score,
            })
        else:
            # No match - this is a new still
            matches.append({
                "old": None,
                "new": new_still,
                "confidence": "new",
                "match_type": "none",
            })
            matched_new_ids.add(new_still["id"])

    # Second pass: LLM for uncertain matches
    for pair in uncertain_pairs:
        if pair["old"]["id"] in matched_old_ids:
            # Already matched, treat as new
            matches.append({
                "old": None,
                "new": pair["new"],
                "confidence": "new",
                "match_type": "none",
            })
            continue

        # Get unmatched new stills as candidates for LLM
        candidates = [pair["new"]]  # Primary candidate

        llm_result = await llm_match(
            pair["old"],
            candidates,
            source_context,
            user_id,
        )

        if llm_result["new"]:
            matched_old_ids.add(pair["old"]["id"])
            matched_new_ids.add(llm_result["new"]["id"])

        matches.append(llm_result)

    # Find orphans (old stills with no match)
    orphans = [s for s in old_stills if s["id"] not in matched_old_ids]

    return matches, orphans
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_still_matcher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/still_matcher.py tests/test_still_matcher.py
git commit -m "feat: add still matcher service with hybrid fuzzy+LLM matching"
```

---

## Task 5: Create Refresh API Router

**Files:**
- Create: `app/api/refresh.py`
- Modify: `app/main.py` (add router)

**Step 1: Create the refresh API router**

Create `app/api/refresh.py`:

```python
"""Refresh API endpoints."""
import csv
import io
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.database import get_db
from app.db_utils import execute, fetchall, fetchone
from app.services.refresh_tasks import (
    get_stills_needing_attention,
    get_sources_needing_review,
    get_top_performers,
    get_refresh_counts,
    run_refresh_maintenance,
)

router = APIRouter(prefix="/api/refresh", tags=["refresh"])


# Request/Response models
class BulkRetireRequest(BaseModel):
    still_ids: List[str]


class BulkExtendReviewRequest(BaseModel):
    source_ids: List[int]
    days: int = 180


class MarkPerformerRequest(BaseModel):
    still_ids: List[str]


class RefreshCounts(BaseModel):
    sources: int
    stills: int


# Endpoints
@router.get("/counts")
async def get_counts(user: dict = Depends(get_current_user)) -> RefreshCounts:
    """Get notification badge counts."""
    counts = await get_refresh_counts(user["id"])
    return RefreshCounts(**counts)


@router.get("/dashboard")
async def get_dashboard(user: dict = Depends(get_current_user)):
    """Get all dashboard data in one call."""
    sources = await get_sources_needing_review(user["id"])
    stills = await get_stills_needing_attention(user["id"])
    top_performers = await get_top_performers(user["id"])
    counts = await get_refresh_counts(user["id"])

    return {
        "sources_needing_review": sources,
        "stills_needing_attention": stills,
        "top_performers": top_performers,
        "counts": counts,
    }


@router.get("/sources-needing-review")
async def get_sources(user: dict = Depends(get_current_user)):
    """Get sources needing review."""
    return await get_sources_needing_review(user["id"])


@router.get("/stills-needing-attention")
async def get_stills(user: dict = Depends(get_current_user)):
    """Get stills needing attention, grouped by reason."""
    return await get_stills_needing_attention(user["id"])


@router.get("/top-performers")
async def get_performers(
    limit: int = Query(default=10, le=50),
    user: dict = Depends(get_current_user)
):
    """Get top performing stills."""
    return await get_top_performers(user["id"], limit)


@router.post("/run-maintenance")
async def trigger_maintenance(user: dict = Depends(get_current_user)):
    """Manually trigger refresh maintenance."""
    results = await run_refresh_maintenance(user["id"])
    return {"success": True, "results": results}


@router.post("/bulk-retire")
async def bulk_retire(
    request: BulkRetireRequest,
    user: dict = Depends(get_current_user)
):
    """Retire multiple stills at once."""
    if not request.still_ids:
        raise HTTPException(status_code=400, detail="No still IDs provided")

    async with get_db() as db:
        placeholders = ",".join(["?" for _ in request.still_ids])
        await execute(db, f"""
            UPDATE stills
            SET status = 'retired'
            WHERE id IN ({placeholders})
            AND user_id = ?
        """, tuple(request.still_ids) + (user["id"],))

        if not hasattr(db, 'fetchone'):  # SQLite
            await db.commit()

    return {"success": True, "retired_count": len(request.still_ids)}


@router.post("/bulk-extend-review")
async def bulk_extend_review(
    request: BulkExtendReviewRequest,
    user: dict = Depends(get_current_user)
):
    """Extend review dates for multiple sources."""
    if not request.source_ids:
        raise HTTPException(status_code=400, detail="No source IDs provided")

    new_date = (datetime.now() + timedelta(days=request.days)).date().isoformat()

    async with get_db() as db:
        placeholders = ",".join(["?" for _ in request.source_ids])
        await execute(db, f"""
            UPDATE sources
            SET review_date = ?
            WHERE id IN ({placeholders})
            AND user_id = ?
        """, (new_date,) + tuple(request.source_ids) + (user["id"],))

        if not hasattr(db, 'fetchone'):  # SQLite
            await db.commit()

    return {"success": True, "extended_count": len(request.source_ids), "new_date": new_date}


@router.get("/export-stale")
async def export_stale_csv(user: dict = Depends(get_current_user)):
    """Export stale content as CSV."""
    stills = await get_stills_needing_attention(user["id"])

    # Flatten all categories with reason
    rows = []
    for reason, still_list in stills.items():
        for still in still_list:
            rows.append({
                "id": still["id"],
                "content": still["content"][:200],  # Truncate for CSV
                "type": still.get("still_type", ""),
                "status": still.get("status", ""),
                "reason": reason,
                "expiration_date": still.get("expiration_date", ""),
                "usage_count": still.get("usage_count", 0),
                "performance": still.get("performance", ""),
                "source": still.get("source_name", ""),
            })

    # Generate CSV
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=stale_content.csv"}
    )


# Performance tracking endpoints
@router.get("/stills/{still_id}/outputs")
async def get_still_outputs(
    still_id: str,
    user: dict = Depends(get_current_user)
):
    """Get outputs that used a specific still."""
    async with get_db() as db:
        # Verify still belongs to user
        still = await fetchone(db,
            "SELECT id FROM stills WHERE id = ? AND user_id = ?",
            (still_id, user["id"])
        )
        if not still:
            raise HTTPException(status_code=404, detail="Still not found")

        # Find outputs containing this still in atoms_used
        rows = await fetchall(db, """
            SELECT o.id, o.content_type, o.created_at, o.status,
                   o.step3_final, o.subject, j.campaign_name
            FROM outputs o
            LEFT JOIN jobs j ON o.job_id = j.id
            WHERE o.atoms_used LIKE ?
            ORDER BY o.created_at DESC
            LIMIT 20
        """, (f'%{still_id}%',))

        return [dict(r) for r in rows]


@router.post("/outputs/{output_id}/mark-performer")
async def mark_output_performer(
    output_id: int,
    request: MarkPerformerRequest,
    user: dict = Depends(get_current_user)
):
    """Mark an output as high performer and update contributing stills."""
    async with get_db() as db:
        # Verify output exists
        output = await fetchone(db,
            "SELECT id, job_id FROM outputs WHERE id = ?",
            (output_id,)
        )
        if not output:
            raise HTTPException(status_code=404, detail="Output not found")

        # Update output status
        await execute(db,
            "UPDATE outputs SET status = 'high_performer' WHERE id = ?",
            (output_id,)
        )

        # Update selected stills to high performance
        if request.still_ids:
            placeholders = ",".join(["?" for _ in request.still_ids])
            await execute(db, f"""
                UPDATE stills
                SET performance = 'high'
                WHERE id IN ({placeholders})
                AND user_id = ?
            """, tuple(request.still_ids) + (user["id"],))

        if not hasattr(db, 'fetchone'):  # SQLite
            await db.commit()

    return {"success": True, "stills_updated": len(request.still_ids)}
```

**Step 2: Add router to main.py**

In `app/main.py`, add import and include router:

```python
# Add to imports
from app.api.refresh import router as refresh_router

# Add to router includes (after other routers)
app.include_router(refresh_router)
```

**Step 3: Test API loads**

Run: `python3 -c "from app.api.refresh import router; print('Router OK')"`

**Step 4: Commit**

```bash
git add app/api/refresh.py app/main.py
git commit -m "feat: add refresh API router with all endpoints"
```

---

## Task 6: Create Refresh Dashboard Frontend

**Files:**
- Create: `frontend/refresh.html`
- Create: `frontend/static/refresh.js`

**Step 1: Create the HTML page**

Create `frontend/refresh.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Refresh - Still</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body class="min-h-screen bg-surface-primary">
    <div id="nav-container"></div>

    <main class="max-w-7xl mx-auto px-4 py-8">
        <!-- Header -->
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-2xl font-bold text-text-primary">Refresh Dashboard</h1>
                <p class="text-text-secondary mt-1">Monitor and maintain your content library</p>
            </div>
            <button id="run-maintenance-btn" class="btn-primary">
                Run Maintenance Check
            </button>
        </div>

        <!-- Dashboard Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Sources Needing Review -->
            <div class="card">
                <div class="card-header flex justify-between items-center">
                    <h2 class="text-lg font-semibold text-text-primary">Sources Needing Review</h2>
                    <span id="sources-count" class="badge-warning">0</span>
                </div>
                <div id="sources-list" class="card-body space-y-3">
                    <p class="text-text-secondary text-sm">Loading...</p>
                </div>
            </div>

            <!-- Stills Needing Attention -->
            <div class="card">
                <div class="card-header flex justify-between items-center">
                    <h2 class="text-lg font-semibold text-text-primary">Stills Needing Attention</h2>
                    <span id="stills-count" class="badge-error">0</span>
                </div>
                <div id="stills-list" class="card-body space-y-3">
                    <p class="text-text-secondary text-sm">Loading...</p>
                </div>
            </div>

            <!-- Top Performers -->
            <div class="card">
                <div class="card-header flex justify-between items-center">
                    <h2 class="text-lg font-semibold text-text-primary">Top Performers</h2>
                    <span id="performers-count" class="badge-success">0</span>
                </div>
                <div id="performers-list" class="card-body space-y-3">
                    <p class="text-text-secondary text-sm">Loading...</p>
                </div>
            </div>
        </div>

        <!-- Bulk Actions Bar -->
        <div id="bulk-actions" class="fixed bottom-0 left-0 right-0 bg-surface-secondary border-t border-border p-4 hidden">
            <div class="max-w-7xl mx-auto flex justify-between items-center">
                <span id="selection-count" class="text-text-primary font-medium">0 items selected</span>
                <div class="flex gap-3">
                    <button id="bulk-retire-btn" class="btn-secondary">Retire All Expired</button>
                    <button id="bulk-extend-btn" class="btn-secondary">Extend Review +6mo</button>
                    <button id="export-csv-btn" class="btn-secondary">Export CSV</button>
                </div>
            </div>
        </div>
    </main>

    <!-- Still Detail Modal -->
    <div id="still-modal" class="modal hidden">
        <div class="modal-backdrop" onclick="closeStillModal()"></div>
        <div class="modal-content">
            <div id="still-modal-body"></div>
        </div>
    </div>

    <!-- Mark Performer Modal -->
    <div id="performer-modal" class="modal hidden">
        <div class="modal-backdrop" onclick="closePerformerModal()"></div>
        <div class="modal-content">
            <div id="performer-modal-body"></div>
        </div>
    </div>

    <script src="/static/auth.js"></script>
    <script src="/static/utils.js"></script>
    <script src="/static/components.js"></script>
    <script src="/static/theme.js"></script>
    <script src="/static/refresh.js"></script>
</body>
</html>
```

**Step 2: Create the JavaScript file**

Create `frontend/static/refresh.js`:

```javascript
/**
 * Refresh Dashboard JavaScript
 */

let dashboardData = null;
let selectedStills = new Set();
let selectedSources = new Set();

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadDashboard();
    setupEventListeners();
});

async function loadDashboard() {
    try {
        const response = await fetch('/api/refresh/dashboard', {
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });

        if (!response.ok) throw new Error('Failed to load dashboard');

        dashboardData = await response.json();
        renderDashboard();
    } catch (error) {
        console.error('Dashboard load error:', error);
        UI.showToast('Failed to load dashboard', 'error');
    }
}

function renderDashboard() {
    renderSources();
    renderStills();
    renderPerformers();
    updateCounts();
}

function renderSources() {
    const container = document.getElementById('sources-list');
    const sources = dashboardData.sources_needing_review || [];

    if (sources.length === 0) {
        container.innerHTML = '<p class="text-text-secondary text-sm">No sources need review</p>';
        return;
    }

    container.innerHTML = sources.map(source => `
        <div class="source-item p-3 bg-surface-tertiary rounded-lg">
            <div class="flex justify-between items-start">
                <div>
                    <h3 class="font-medium text-text-primary">${source.campaign_name || 'Unnamed Source'}</h3>
                    <p class="text-sm text-text-secondary">${source.still_count || 0} stills</p>
                    <p class="text-xs text-text-tertiary">Review due: ${formatDate(source.review_date)}</p>
                </div>
                <div class="flex gap-2">
                    <button onclick="extendReview(${source.id})" class="btn-sm btn-secondary">
                        +6mo
                    </button>
                    <button onclick="refreshSource(${source.id})" class="btn-sm btn-primary">
                        Refresh
                    </button>
                </div>
            </div>
        </div>
    `).join('');

    document.getElementById('sources-count').textContent = sources.length;
}

function renderStills() {
    const container = document.getElementById('stills-list');
    const stills = dashboardData.stills_needing_attention || {};

    const categories = [
        { key: 'expired', label: 'Expired', icon: '⏰' },
        { key: 'needs_review', label: 'Needs Review', icon: '👀' },
        { key: 'never_used', label: 'Never Used (30+ days)', icon: '📭' },
        { key: 'low_performance', label: 'Low Performance', icon: '📉' },
    ];

    let totalCount = 0;
    const html = categories.map(cat => {
        const items = stills[cat.key] || [];
        totalCount += items.length;

        if (items.length === 0) return '';

        return `
            <div class="still-category mb-4">
                <h3 class="text-sm font-medium text-text-secondary mb-2">
                    ${cat.icon} ${cat.label} (${items.length})
                </h3>
                <div class="space-y-2">
                    ${items.slice(0, 5).map(still => `
                        <div class="still-item p-2 bg-surface-tertiary rounded cursor-pointer hover:bg-surface-hover"
                             onclick="showStillDetail('${still.id}')">
                            <p class="text-sm text-text-primary truncate">${still.content}</p>
                            <p class="text-xs text-text-tertiary">${still.still_type} · ${still.source_name || 'Unknown source'}</p>
                        </div>
                    `).join('')}
                    ${items.length > 5 ? `<p class="text-xs text-text-secondary">+${items.length - 5} more</p>` : ''}
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = html || '<p class="text-text-secondary text-sm">No stills need attention</p>';
    document.getElementById('stills-count').textContent = totalCount;
}

function renderPerformers() {
    const container = document.getElementById('performers-list');
    const performers = dashboardData.top_performers || [];

    if (performers.length === 0) {
        container.innerHTML = '<p class="text-text-secondary text-sm">No top performers yet</p>';
        return;
    }

    container.innerHTML = performers.map(still => `
        <div class="performer-item p-3 bg-surface-tertiary rounded-lg cursor-pointer hover:bg-surface-hover"
             onclick="showStillDetail('${still.id}')">
            <div class="flex justify-between items-start">
                <div class="flex-1 min-w-0">
                    <p class="text-sm text-text-primary truncate">${still.content}</p>
                    <p class="text-xs text-text-tertiary">${still.still_type} · Used ${still.usage_count || 0}x</p>
                </div>
                ${still.performance === 'high' ? '<span class="badge-success text-xs">High</span>' : ''}
            </div>
        </div>
    `).join('');

    document.getElementById('performers-count').textContent = performers.length;
}

function updateCounts() {
    // Counts are already set by render functions
}

function setupEventListeners() {
    document.getElementById('run-maintenance-btn').addEventListener('click', runMaintenance);
    document.getElementById('bulk-retire-btn').addEventListener('click', bulkRetire);
    document.getElementById('bulk-extend-btn').addEventListener('click', bulkExtend);
    document.getElementById('export-csv-btn').addEventListener('click', exportCSV);
}

async function runMaintenance() {
    try {
        const response = await fetch('/api/refresh/run-maintenance', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });

        const data = await response.json();

        if (data.success) {
            const { results } = data;
            UI.showToast(
                `Maintenance complete: ${results.stills_marked_needs_review} flagged, ${results.stills_retired} retired`,
                'success'
            );
            await loadDashboard();
        }
    } catch (error) {
        UI.showToast('Maintenance failed', 'error');
    }
}

async function extendReview(sourceId) {
    try {
        const response = await fetch('/api/refresh/bulk-extend-review', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ source_ids: [sourceId], days: 180 })
        });

        if (response.ok) {
            UI.showToast('Review date extended by 6 months', 'success');
            await loadDashboard();
        }
    } catch (error) {
        UI.showToast('Failed to extend review date', 'error');
    }
}

async function refreshSource(sourceId) {
    // TODO: Implement source refresh workflow
    UI.showToast('Source refresh coming soon', 'info');
}

async function showStillDetail(stillId) {
    // TODO: Implement still detail modal
    console.log('Show still:', stillId);
}

async function bulkRetire() {
    const expiredStills = (dashboardData.stills_needing_attention?.expired || []).map(s => s.id);

    if (expiredStills.length === 0) {
        UI.showToast('No expired stills to retire', 'info');
        return;
    }

    try {
        const response = await fetch('/api/refresh/bulk-retire', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ still_ids: expiredStills })
        });

        if (response.ok) {
            UI.showToast(`Retired ${expiredStills.length} stills`, 'success');
            await loadDashboard();
        }
    } catch (error) {
        UI.showToast('Failed to retire stills', 'error');
    }
}

async function bulkExtend() {
    const sourceIds = (dashboardData.sources_needing_review || []).map(s => s.id);

    if (sourceIds.length === 0) {
        UI.showToast('No sources to extend', 'info');
        return;
    }

    try {
        const response = await fetch('/api/refresh/bulk-extend-review', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ source_ids: sourceIds, days: 180 })
        });

        if (response.ok) {
            UI.showToast(`Extended ${sourceIds.length} source review dates`, 'success');
            await loadDashboard();
        }
    } catch (error) {
        UI.showToast('Failed to extend review dates', 'error');
    }
}

async function exportCSV() {
    try {
        const response = await fetch('/api/refresh/export-stale', {
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'stale_content.csv';
        a.click();
        window.URL.revokeObjectURL(url);

        UI.showToast('CSV exported', 'success');
    } catch (error) {
        UI.showToast('Export failed', 'error');
    }
}

function closeStillModal() {
    document.getElementById('still-modal').classList.add('hidden');
}

function closePerformerModal() {
    document.getElementById('performer-modal').classList.add('hidden');
}

function formatDate(dateStr) {
    if (!dateStr) return 'Unknown';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
}

function getToken() {
    return localStorage.getItem('token') || '';
}
```

**Step 3: Commit**

```bash
git add frontend/refresh.html frontend/static/refresh.js
git commit -m "feat: add refresh dashboard frontend with three-column layout"
```

---

## Task 7: Add Navigation Badge

**Files:**
- Modify: `frontend/static/components.js`

**Step 1: Update navigation to include Refresh with badge**

In `frontend/static/components.js`, find the `renderPremiumNav` function and update the nav links array to include Refresh between Reserve and Workshop. Add badge logic:

```javascript
// In the nav links section, add Refresh:
{ name: 'Refresh', href: '/refresh.html', id: 'nav-refresh' },

// After rendering nav, add badge fetch:
async function updateRefreshBadge() {
    try {
        const token = localStorage.getItem('token');
        if (!token) return;

        const response = await fetch('/api/refresh/counts', {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            const counts = await response.json();
            const total = counts.sources + counts.stills;

            const refreshLink = document.getElementById('nav-refresh');
            if (refreshLink && total > 0) {
                refreshLink.innerHTML = `Refresh <span class="nav-badge">${total}</span>`;
            }
        }
    } catch (e) {
        console.log('Badge fetch skipped');
    }
}

// Call after nav renders
updateRefreshBadge();
```

**Step 2: Add badge CSS to styles.css**

In `frontend/static/styles.css`:

```css
.nav-badge {
    background: var(--color-error, #EF4444);
    color: white;
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 10px;
    margin-left: 4px;
}
```

**Step 3: Commit**

```bash
git add frontend/static/components.js frontend/static/styles.css
git commit -m "feat: add refresh nav item with notification badge"
```

---

## Task 8: Add Still Detail Modal with Performance Tracking

**Files:**
- Modify: `frontend/static/refresh.js`

**Step 1: Implement showStillDetail function**

Update `showStillDetail` in `refresh.js`:

```javascript
async function showStillDetail(stillId) {
    try {
        // Get still data from dashboard data
        let still = null;
        for (const category of Object.values(dashboardData.stills_needing_attention || {})) {
            still = category.find(s => s.id === stillId);
            if (still) break;
        }
        if (!still) {
            still = (dashboardData.top_performers || []).find(s => s.id === stillId);
        }

        if (!still) {
            UI.showToast('Still not found', 'error');
            return;
        }

        // Fetch outputs for this still
        const outputsRes = await fetch(`/api/refresh/stills/${stillId}/outputs`, {
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });
        const outputs = await outputsRes.json();

        const modal = document.getElementById('still-modal');
        const body = document.getElementById('still-modal-body');

        body.innerHTML = `
            <div class="p-6">
                <div class="flex justify-between items-start mb-4">
                    <h2 class="text-xl font-bold text-text-primary">Still Detail</h2>
                    <button onclick="closeStillModal()" class="text-text-secondary hover:text-text-primary">✕</button>
                </div>

                <div class="bg-surface-tertiary p-4 rounded-lg mb-4">
                    <p class="text-text-primary">${still.content}</p>
                </div>

                <div class="grid grid-cols-2 gap-4 mb-4">
                    <div>
                        <label class="text-sm text-text-secondary">Type</label>
                        <p class="font-medium text-text-primary">${still.still_type}</p>
                    </div>
                    <div>
                        <label class="text-sm text-text-secondary">Status</label>
                        <select id="still-status" class="input-field" onchange="updateStillStatus('${stillId}', this.value)">
                            <option value="active" ${still.status === 'active' ? 'selected' : ''}>Active</option>
                            <option value="evergreen" ${still.status === 'evergreen' ? 'selected' : ''}>Evergreen</option>
                            <option value="needs_review" ${still.status === 'needs_review' ? 'selected' : ''}>Needs Review</option>
                            <option value="retired" ${still.status === 'retired' ? 'selected' : ''}>Retired</option>
                        </select>
                    </div>
                    <div>
                        <label class="text-sm text-text-secondary">Funnel Stage</label>
                        <p class="font-medium text-text-primary">${still.funnel_stage || 'Not set'}</p>
                    </div>
                    <div>
                        <label class="text-sm text-text-secondary">Performance</label>
                        <select id="still-performance" class="input-field" onchange="updateStillPerformance('${stillId}', this.value)">
                            <option value="untested" ${still.performance === 'untested' ? 'selected' : ''}>Untested</option>
                            <option value="low" ${still.performance === 'low' ? 'selected' : ''}>Low</option>
                            <option value="medium" ${still.performance === 'medium' ? 'selected' : ''}>Medium</option>
                            <option value="high" ${still.performance === 'high' ? 'selected' : ''}>High</option>
                        </select>
                    </div>
                </div>

                <div class="mb-4">
                    <h3 class="text-sm font-medium text-text-secondary mb-2">Usage Stats</h3>
                    <p class="text-text-primary">Used ${still.usage_count || 0} times · Last used: ${still.last_used_at ? formatDate(still.last_used_at) : 'Never'}</p>
                </div>

                <div class="mb-4">
                    <h3 class="text-sm font-medium text-text-secondary mb-2">Outputs Using This Still (${outputs.length})</h3>
                    <div class="space-y-2 max-h-40 overflow-y-auto">
                        ${outputs.length > 0 ? outputs.map(o => `
                            <div class="p-2 bg-surface-tertiary rounded text-sm">
                                <span class="font-medium">${o.content_type}</span> · ${formatDate(o.created_at)}
                                ${o.campaign_name ? `<span class="text-text-tertiary"> · ${o.campaign_name}</span>` : ''}
                            </div>
                        `).join('') : '<p class="text-text-tertiary text-sm">No outputs yet</p>'}
                    </div>
                </div>

                <div>
                    <h3 class="text-sm font-medium text-text-secondary mb-2">Source Context</h3>
                    <p class="text-text-tertiary text-sm">${still.source_name || 'Unknown source'}</p>
                </div>
            </div>
        `;

        modal.classList.remove('hidden');
    } catch (error) {
        console.error('Error showing still detail:', error);
        UI.showToast('Failed to load still detail', 'error');
    }
}

async function updateStillStatus(stillId, newStatus) {
    try {
        const response = await fetch(`/api/library/stills/${stillId}/status`, {
            method: 'PATCH',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ status: newStatus })
        });

        if (response.ok) {
            UI.showToast('Status updated', 'success');
        }
    } catch (error) {
        UI.showToast('Failed to update status', 'error');
    }
}

async function updateStillPerformance(stillId, newPerformance) {
    try {
        const response = await fetch(`/api/library/stills/${stillId}/performance`, {
            method: 'PATCH',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ performance: newPerformance })
        });

        if (response.ok) {
            UI.showToast('Performance updated', 'success');
        }
    } catch (error) {
        UI.showToast('Failed to update performance', 'error');
    }
}
```

**Step 2: Add modal CSS if not exists**

Ensure `frontend/static/styles.css` has modal styles:

```css
.modal {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: flex;
    align-items: center;
    justify-content: center;
}

.modal.hidden {
    display: none;
}

.modal-backdrop {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
}

.modal-content {
    position: relative;
    background: var(--color-surface-secondary);
    border-radius: 12px;
    max-width: 600px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
}
```

**Step 3: Commit**

```bash
git add frontend/static/refresh.js frontend/static/styles.css
git commit -m "feat: add still detail modal with performance tracking"
```

---

## Task 9: Add Library API Endpoints for Status/Performance Updates

**Files:**
- Modify: `app/api/library.py` (or create if needed)

**Step 1: Add PATCH endpoints for still updates**

In `app/api/library.py`, add:

```python
from pydantic import BaseModel

class StatusUpdate(BaseModel):
    status: str

class PerformanceUpdate(BaseModel):
    performance: str

@router.patch("/stills/{still_id}/status")
async def update_still_status(
    still_id: str,
    update: StatusUpdate,
    user: dict = Depends(get_current_user)
):
    """Update a still's status."""
    valid_statuses = ['active', 'evergreen', 'needs_review', 'retired']
    if update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    async with get_db() as db:
        await execute(db,
            "UPDATE stills SET status = ? WHERE id = ? AND user_id = ?",
            (update.status, still_id, user["id"])
        )
        if not hasattr(db, 'fetchone'):
            await db.commit()

    return {"success": True}


@router.patch("/stills/{still_id}/performance")
async def update_still_performance(
    still_id: str,
    update: PerformanceUpdate,
    user: dict = Depends(get_current_user)
):
    """Update a still's performance rating."""
    valid_ratings = ['untested', 'low', 'medium', 'high']
    if update.performance not in valid_ratings:
        raise HTTPException(status_code=400, detail=f"Invalid rating. Must be one of: {valid_ratings}")

    async with get_db() as db:
        await execute(db,
            "UPDATE stills SET performance = ? WHERE id = ? AND user_id = ?",
            (update.performance, still_id, user["id"])
        )
        if not hasattr(db, 'fetchone'):
            await db.commit()

    return {"success": True}
```

**Step 2: Commit**

```bash
git add app/api/library.py
git commit -m "feat: add PATCH endpoints for still status and performance updates"
```

---

## Task 10: Add Admin Settings for Refresh Configuration

**Files:**
- Modify: `app/templates/admin/settings.html`
- Modify: `app/api/admin_views.py`

**Step 1: Add refresh settings section to admin template**

In the admin settings template, add a new section for Refresh Settings with the model dropdown, thresholds, and auto-retire toggle.

**Step 2: Add endpoint to get/set refresh settings**

In admin_views.py, add endpoints:

```python
@router.get("/api/refresh-settings")
async def get_refresh_settings():
    """Get current refresh settings."""
    settings = {}
    async with get_db() as db:
        for key in ['still_matching_model', 'fuzzy_match_high_threshold',
                    'fuzzy_match_low_threshold', 'auto_retire_expired',
                    'expiration_warning_days']:
            row = await fetchone(db, "SELECT value FROM settings WHERE key = ?", (key,))
            settings[key] = row["value"] if row else None
    return settings

@router.post("/api/refresh-settings")
async def update_refresh_settings(settings: dict):
    """Update refresh settings."""
    allowed_keys = ['still_matching_model', 'fuzzy_match_high_threshold',
                   'fuzzy_match_low_threshold', 'auto_retire_expired',
                   'expiration_warning_days']

    async with get_db() as db:
        for key, value in settings.items():
            if key in allowed_keys:
                await execute(db,
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, str(value))
                )
        await db.commit()

    return {"success": True}
```

**Step 3: Commit**

```bash
git add app/templates/admin/settings.html app/api/admin_views.py
git commit -m "feat: add admin settings UI for refresh configuration"
```

---

## Task 11: Run Full Test Suite

**Step 1: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

**Step 2: Fix any failures**

Address any test failures before proceeding.

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete refresh infrastructure implementation"
```

---

## Summary

This plan implements:
1. Refresh tasks service with automatic maintenance
2. Still matcher with hybrid fuzzy + LLM matching
3. Refresh API with all endpoints
4. Refresh dashboard frontend
5. Navigation badge with counts
6. Still detail modal with performance tracking
7. Library API updates for status/performance
8. Admin settings for refresh configuration

Total estimated tasks: 11
Each task follows TDD approach with failing tests first.
