"""Content library management service (The Reserve)."""
import json
import logging
from typing import Optional, List, Tuple
from difflib import SequenceMatcher

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall, fetchval
from app.services.settings_manager import get_global_setting

settings = get_settings()
logger = logging.getLogger(__name__)


# Duplicate detection thresholds
DUPLICATE_HIGH_THRESHOLD = 0.90  # Almost identical - skip
DUPLICATE_MEDIUM_THRESHOLD = 0.75  # Very similar - merge metadata


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity score between two text strings.
    Returns float between 0.0 (no match) and 1.0 (identical).
    """
    if not text1 or not text2:
        return 0.0
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()
    return SequenceMatcher(None, t1, t2).ratio()


async def find_duplicate_still(
    content: str,
    still_type: str,
    user_id: int,
    exclude_job_id: Optional[str] = None
) -> Tuple[Optional[dict], float]:
    """
    Find if a duplicate still already exists in the database.

    Args:
        content: The content of the new still
        still_type: The type of the new still
        user_id: User ID to search within
        exclude_job_id: Optional job_id to exclude (current job)

    Returns:
        Tuple of (matching_still, similarity_score) or (None, 0.0)
    """
    async with get_db() as db:
        # Get existing stills of the same type for this user
        if exclude_job_id:
            rows = await fetchall(
                db,
                """
                SELECT id, content, still_type, usage_count, performance, status
                FROM stills
                WHERE user_id = ? AND still_type = ? AND job_id != ? AND status != 'retired'
                """,
                (user_id, still_type, exclude_job_id)
            )
        else:
            rows = await fetchall(
                db,
                """
                SELECT id, content, still_type, usage_count, performance, status
                FROM stills
                WHERE user_id = ? AND still_type = ? AND status != 'retired'
                """,
                (user_id, still_type)
            )

        best_match = None
        best_score = 0.0

        for row in rows:
            score = calculate_similarity(content, row["content"])
            if score > best_score:
                best_score = score
                best_match = dict(row)

        return best_match, best_score


async def get_existing_stills_for_dedup(user_id: int) -> List[dict]:
    """
    Get all active stills for a user for duplicate detection.
    """
    async with get_db() as db:
        rows = await fetchall(
            db,
            """
            SELECT id, content, still_type, usage_count, performance, status, job_id
            FROM stills
            WHERE user_id = ? AND status != 'retired'
            ORDER BY created_at DESC
            """,
            (user_id,)
        )
        return [dict(row) for row in rows]


def _extract_still_ids(stills_used: List) -> List[str]:
    """
    Extract still IDs from stills_used list.

    The stills_used field can contain:
    - String IDs directly: ["abc123", "def456"]
    - Content snippets (from older outputs): ["Some insight text..."]

    We only want actual still IDs (UUIDs or similar).
    """
    if not stills_used:
        return []

    still_ids = []
    for item in stills_used:
        if isinstance(item, str):
            # Check if it looks like a still ID (contains hyphen for UUIDs,
            # or is alphanumeric with underscore for generated IDs)
            # IDs are typically short (< 50 chars) vs content snippets which are longer
            if len(item) < 50 and ('-' in item or '_' in item or item.isalnum()):
                still_ids.append(item)

    return still_ids

# All valid still types (10 total)
VALID_STILL_TYPES = [
    "data", "insight", "story", "problem", "solution", "quote",
    "framework", "definition", "question", "proof_point"
]

# Valid funnel stages
VALID_FUNNEL_STAGES = ["awareness", "consideration", "decision"]

# Valid status values
VALID_STATUSES = ["active", "evergreen", "needs_review", "retired"]

# Valid expiration types
VALID_EXPIRATION_TYPES = ["date_bound", "event_bound", "evergreen"]

# Valid performance values
VALID_PERFORMANCE_VALUES = ["high", "medium", "low", "untested"]


def validate_still(still: dict) -> dict:
    """
    Validate and sanitize a still before database insertion.

    Validates all 10 still types and lifecycle fields:
    - best_formats: list of content format strings
    - funnel_stage: awareness/consideration/decision
    - expiration_date: YYYY-MM-DD string or None
    - status: active/evergreen/needs_review/retired
    - expiration_type: date_bound/event_bound/evergreen
    - performance: high/medium/low/untested

    Returns sanitized still dict with proper types.
    """
    # Validate still_type against known types
    still_type = str(still.get("still_type", "insight"))[:50]
    if still_type not in VALID_STILL_TYPES:
        still_type = "insight"  # Default to insight if invalid

    # Validate funnel_stage
    funnel_stage = still.get("funnel_stage")
    if funnel_stage and funnel_stage not in VALID_FUNNEL_STAGES:
        funnel_stage = None

    # Validate best_formats as list
    best_formats = still.get("best_formats")
    if not isinstance(best_formats, list):
        best_formats = []

    # Validate expiration_date format (should be YYYY-MM-DD string or None)
    expiration_date = still.get("expiration_date")
    if expiration_date:
        if isinstance(expiration_date, str) and len(expiration_date) == 10:
            # Basic format check
            try:
                parts = expiration_date.split("-")
                if len(parts) == 3 and all(p.isdigit() for p in parts):
                    pass  # Valid format
                else:
                    expiration_date = None
            except (ValueError, AttributeError):
                expiration_date = None
        else:
            expiration_date = None

    # Validate status
    status = still.get("status", "active")
    if status not in VALID_STATUSES:
        status = "active"

    # Validate expiration_type
    expiration_type = still.get("expiration_type")
    if expiration_type and expiration_type not in VALID_EXPIRATION_TYPES:
        expiration_type = None

    # Validate performance
    performance = still.get("performance", "untested")
    if performance not in VALID_PERFORMANCE_VALUES:
        performance = "untested"

    return {
        "id": str(still.get("id", "")) if still.get("id") else None,
        "job_id": str(still.get("job_id", "")) if still.get("job_id") else None,
        "user_id": int(still.get("user_id", 0)) if still.get("user_id") else None,
        "still_type": still_type,
        "content": str(still.get("content", ""))[:50000],  # Limit content size
        "source_location": str(still.get("source_location", ""))[:500] if still.get("source_location") else None,
        "source_file": str(still.get("source_file", ""))[:500] if still.get("source_file") else None,
        "tags": still.get("tags") if isinstance(still.get("tags"), list) else [],
        "persona_relevance": still.get("persona_relevance") if isinstance(still.get("persona_relevance"), dict) else {},
        "quote_attribution": str(still.get("quote_attribution", ""))[:200] if still.get("quote_attribution") else None,
        "topics": still.get("topics") if isinstance(still.get("topics"), list) else [],
        "campaign_name": str(still.get("campaign_name", ""))[:200] if still.get("campaign_name") else None,
        # Lifecycle fields
        "best_formats": best_formats,
        "funnel_stage": funnel_stage,
        "expiration_date": expiration_date,
        "status": status,
        "expiration_type": expiration_type,
        "performance": performance,
    }


def validate_output(output: dict) -> dict:
    """
    Validate and sanitize an output before database insertion.

    Returns sanitized output dict with proper types.
    """
    return {
        "content_type": str(output.get("content_type", ""))[:50],
        "variation_number": int(output.get("variation_number", 1)) if output.get("variation_number") else 1,
        "content": str(output.get("content", "")) if output.get("content") else None,
        "step1_draft": str(output.get("step1_draft", "")) if output.get("step1_draft") else None,
        "step2_edited": str(output.get("step2_edited", "")) if output.get("step2_edited") else None,
        "step3_final": str(output.get("step3_final", "")) if output.get("step3_final") else None,
        "stills_used": output.get("stills_used", output.get("atoms_used", [])) if isinstance(output.get("stills_used", output.get("atoms_used")), list) else [],
        "citations": output.get("citations") if isinstance(output.get("citations"), list) else [],
        "warnings": output.get("warnings") if isinstance(output.get("warnings"), list) else [],
        "quality_scores": output.get("quality_scores") if isinstance(output.get("quality_scores"), dict) else None,
        "hook_variations": output.get("hook_variations") if isinstance(output.get("hook_variations"), list) else None,
        "subject": str(output.get("subject", ""))[:500] if output.get("subject") else None,
        "preview_text": str(output.get("preview_text", ""))[:500] if output.get("preview_text") else None,
        "email_day": int(output.get("email_day")) if output.get("email_day") and str(output.get("email_day")).isdigit() else None,
        "email_purpose": str(output.get("email_purpose", ""))[:200] if output.get("email_purpose") else None,
        "sequence_name": str(output.get("sequence_name", ""))[:200] if output.get("sequence_name") else None,
        "topics": output.get("topics") if isinstance(output.get("topics"), list) else [],
        "campaign_name": str(output.get("campaign_name", ""))[:200] if output.get("campaign_name") else None,
    }


async def add_stills_to_library(
    stills: list[dict],
    user_id: int,
    source_file: Optional[str] = None,
    campaign_name: Optional[str] = None,
    job_id: Optional[str] = None,
) -> int:
    """
    Add extracted stills to the Reserve (content library).

    Returns the number of entries added.
    """
    async with get_db() as db:
        count = 0

        for still in stills:
            # Validate and sanitize the still data
            validated = validate_still(still)

            # Use job_id from parameter, or from still if available
            still_job_id = job_id or validated.get("job_id")

            await execute(
                db,
                """
                INSERT INTO content_library (
                    user_id, entry_type, content, source, source_timestamp,
                    tags, persona_relevance, topics, campaign_name, job_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    validated["still_type"],
                    validated["content"],
                    source_file or validated["source_file"],
                    validated["source_location"],
                    json.dumps(validated["tags"]),
                    json.dumps(validated["persona_relevance"]),
                    json.dumps(campaign_name and validated["topics"] or validated["topics"]),
                    campaign_name or validated["campaign_name"],
                    still_job_id,
                )
            )
            count += 1

        if not settings.use_postgres:
            await db.commit()

    return count


async def save_stills_to_db(
    stills: list[dict],
    campaign_name: Optional[str] = None,
    source_id: Optional[int] = None,
    skip_duplicates: bool = True,
) -> dict:
    """
    Save stills to the stills table (job-specific tracking).

    Args:
        stills: List of stills to save
        campaign_name: Optional campaign name
        source_id: Optional source ID
        skip_duplicates: If True, skip stills that are >90% similar to existing ones

    Returns:
        Dict with 'saved', 'skipped_duplicates', and 'duplicate_details' counts
    """
    result = {
        "saved": 0,
        "skipped_duplicates": 0,
        "duplicate_details": []
    }

    # Get duplicate detection setting (default to enabled)
    dedup_enabled = skip_duplicates
    if skip_duplicates:
        setting = await get_global_setting('skip_duplicate_stills', 'true')
        dedup_enabled = setting.lower() == 'true'

    async with get_db() as db:
        for still in stills:
            # Validate and sanitize the still data
            validated = validate_still(still)

            if not validated["id"] or not validated["job_id"] or not validated["user_id"]:
                logger.warning(f"Skipping still with missing required fields: {still.get('id')}")
                continue

            # Check for duplicates if enabled
            if dedup_enabled:
                duplicate, score = await find_duplicate_still(
                    content=validated["content"],
                    still_type=validated["still_type"],
                    user_id=validated["user_id"],
                    exclude_job_id=validated["job_id"]
                )

                if duplicate and score >= DUPLICATE_HIGH_THRESHOLD:
                    # Skip - this is essentially a duplicate
                    logger.info(
                        f"Skipping duplicate still (score={score:.2f}): "
                        f"'{validated['content'][:50]}...' matches existing still {duplicate['id']}"
                    )
                    result["skipped_duplicates"] += 1
                    result["duplicate_details"].append({
                        "new_content_preview": validated["content"][:100],
                        "existing_still_id": duplicate["id"],
                        "similarity_score": round(score, 3),
                        "still_type": validated["still_type"]
                    })
                    continue

            # Handle best_formats: PostgreSQL uses TEXT[], SQLite uses JSON
            if settings.use_postgres:
                best_formats_value = validated["best_formats"]  # Pass as list for PostgreSQL array
            else:
                best_formats_value = json.dumps(validated["best_formats"])  # JSON for SQLite

            await execute(
                db,
                """
                INSERT INTO stills (
                    id, job_id, user_id, still_type, content,
                    source_location, source_file, tags, persona_relevance,
                    quote_attribution, topics, campaign_name, source_id,
                    best_formats, funnel_stage, expiration_date,
                    status, expiration_type, performance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validated["id"],
                    validated["job_id"],
                    validated["user_id"],
                    validated["still_type"],
                    validated["content"],
                    validated["source_location"],
                    validated["source_file"],
                    json.dumps(validated["tags"]),
                    json.dumps(validated["persona_relevance"]),
                    validated["quote_attribution"],
                    json.dumps(validated["topics"]),
                    campaign_name or validated["campaign_name"],
                    source_id,
                    best_formats_value,
                    validated["funnel_stage"],
                    validated["expiration_date"],
                    validated["status"],
                    validated["expiration_type"],
                    validated["performance"],
                )
            )
            result["saved"] += 1

        if not settings.use_postgres:
            await db.commit()

    if result["skipped_duplicates"] > 0:
        logger.info(f"Duplicate detection: saved {result['saved']}, skipped {result['skipped_duplicates']} duplicates")

    return result


async def save_outputs_to_db(outputs: list[dict], job_id: str, campaign_name: Optional[str] = None) -> int:
    """
    Save generated outputs to the database.

    Returns the number of outputs saved.
    """
    async with get_db() as db:
        count = 0

        for output in outputs:
            # Validate and sanitize the output data
            validated = validate_output(output)

            if settings.use_postgres:
                # PostgreSQL: use RETURNING to get the inserted ID
                row = await db.fetchrow(
                    """
                    INSERT INTO outputs (
                        job_id, content_type, variation_number,
                        step1_draft, step2_edited, step3_final,
                        atoms_used, citations, warnings, quality_scores,
                        hook_variations, subject, preview_text,
                        email_day, email_purpose, sequence_name,
                        topics, campaign_name
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                    RETURNING id
                    """,
                    job_id,
                    validated["content_type"],
                    validated["variation_number"],
                    validated["content"] or validated["step1_draft"],
                    validated["step2_edited"],
                    validated["step3_final"],
                    json.dumps(validated["stills_used"]),
                    json.dumps(validated["citations"]),
                    json.dumps(validated["warnings"]),
                    json.dumps(validated["quality_scores"]) if validated["quality_scores"] else None,
                    json.dumps(validated["hook_variations"]) if validated["hook_variations"] else None,
                    validated["subject"],
                    validated["preview_text"],
                    validated["email_day"],
                    validated["email_purpose"],
                    validated["sequence_name"],
                    json.dumps(validated["topics"]),
                    campaign_name or validated["campaign_name"],
                )
                output_id = row["id"]
            else:
                # SQLite: use lastrowid
                cursor = await db.execute(
                    """
                    INSERT INTO outputs (
                        job_id, content_type, variation_number,
                        step1_draft, step2_edited, step3_final,
                        atoms_used, citations, warnings, quality_scores,
                        hook_variations, subject, preview_text,
                        email_day, email_purpose, sequence_name,
                        topics, campaign_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        validated["content_type"],
                        validated["variation_number"],
                        validated["content"] or validated["step1_draft"],
                        validated["step2_edited"],
                        validated["step3_final"],
                        json.dumps(validated["stills_used"]),
                        json.dumps(validated["citations"]),
                        json.dumps(validated["warnings"]),
                        json.dumps(validated["quality_scores"]) if validated["quality_scores"] else None,
                        json.dumps(validated["hook_variations"]) if validated["hook_variations"] else None,
                        validated["subject"],
                        validated["preview_text"],
                        validated["email_day"],
                        validated["email_purpose"],
                        validated["sequence_name"],
                        json.dumps(validated["topics"]),
                        campaign_name or validated["campaign_name"],
                    )
                )
                output_id = cursor.lastrowid

            count += 1

            # Track still usage for this output
            still_ids = _extract_still_ids(validated["stills_used"])
            if still_ids:
                from app.services.drafting import record_still_usage
                await record_still_usage(still_ids, output_id)

            # Save image prompts if present
            image_prompts = output.get("image_prompts", [])
            for prompt in image_prompts:
                await execute(
                    db,
                    """
                    INSERT INTO image_prompts (output_id, prompt_text, platform, dimensions, style_modifiers)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        output_id,
                        prompt.get("prompt_text", ""),
                        prompt.get("platform", "midjourney"),
                        prompt.get("dimensions", "1200x630"),
                        prompt.get("style_modifiers"),
                    )
                )

        if not settings.use_postgres:
            await db.commit()

    return count


async def get_library_entries_by_ids(entry_ids: list[int], user_id: int) -> list[dict]:
    """
    Get library entries by their IDs.
    """
    if not entry_ids:
        return []

    async with get_db() as db:
        placeholders = ",".join("?" * len(entry_ids))
        rows = await fetchall(
            db,
            f"""
            SELECT * FROM content_library
            WHERE id IN ({placeholders}) AND user_id = ?
            """,
            (*entry_ids, user_id)
        )

        entries = []
        for row in rows:
            entries.append({
                "id": row["id"],
                "entry_type": row["entry_type"],
                "content": row["content"],
                "source": row["source"],
                "source_timestamp": row["source_timestamp"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "persona_relevance": json.loads(row["persona_relevance"]) if row["persona_relevance"] else {},
            })

        return entries
