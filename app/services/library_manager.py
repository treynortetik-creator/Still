"""Content library management service (The Reserve)."""
import json
import logging
from typing import Optional

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall, fetchval

settings = get_settings()
logger = logging.getLogger(__name__)


def validate_still(still: dict) -> dict:
    """
    Validate and sanitize a still before database insertion.

    Returns sanitized still dict with proper types.
    """
    return {
        "id": str(still.get("id", "")) if still.get("id") else None,
        "job_id": str(still.get("job_id", "")) if still.get("job_id") else None,
        "user_id": int(still.get("user_id", 0)) if still.get("user_id") else None,
        "still_type": str(still.get("still_type", "insight"))[:50],
        "content": str(still.get("content", ""))[:50000],  # Limit content size
        "source_location": str(still.get("source_location", ""))[:500] if still.get("source_location") else None,
        "source_file": str(still.get("source_file", ""))[:500] if still.get("source_file") else None,
        "tags": still.get("tags") if isinstance(still.get("tags"), list) else [],
        "persona_relevance": still.get("persona_relevance") if isinstance(still.get("persona_relevance"), dict) else {},
        "quote_attribution": str(still.get("quote_attribution", ""))[:200] if still.get("quote_attribution") else None,
        "topics": still.get("topics") if isinstance(still.get("topics"), list) else [],
        "campaign_name": str(still.get("campaign_name", ""))[:200] if still.get("campaign_name") else None,
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

            await execute(
                db,
                """
                INSERT INTO content_library (
                    user_id, entry_type, content, source, source_timestamp,
                    tags, persona_relevance, topics, campaign_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                )
            )
            count += 1

        if not settings.use_postgres:
            await db.commit()

    return count


async def save_stills_to_db(stills: list[dict], campaign_name: Optional[str] = None) -> int:
    """
    Save stills to the stills table (job-specific tracking).

    Returns the number of stills saved.
    """
    async with get_db() as db:
        count = 0

        for still in stills:
            # Validate and sanitize the still data
            validated = validate_still(still)

            if not validated["id"] or not validated["job_id"] or not validated["user_id"]:
                logger.warning(f"Skipping still with missing required fields: {still.get('id')}")
                continue

            await execute(
                db,
                """
                INSERT INTO stills (
                    id, job_id, user_id, still_type, content,
                    source_location, source_file, tags, persona_relevance,
                    quote_attribution, topics, campaign_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                )
            )
            count += 1

        if not settings.use_postgres:
            await db.commit()

    return count


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
