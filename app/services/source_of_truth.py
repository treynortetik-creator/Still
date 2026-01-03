"""Source of Truth generation service."""
import json
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall
from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.services.prompt_manager import get_rendered_prompt
from app.utils.json_parser import parse_llm_json

logger = logging.getLogger(__name__)
settings = get_settings()


async def generate_source_of_truth(
    cleaned_transcript: str,
    job_id: str,
    user_id: int,
) -> Tuple[dict, float]:
    """
    Generate Source of Truth document from cleaned transcript.

    Args:
        cleaned_transcript: The cleaned source content
        job_id: Job ID for cost tracking
        user_id: User ID for cost tracking

    Returns:
        (source_data, cost) tuple
    """
    # Calculate default review date (6 months out)
    today = datetime.now().date()

    # Build variables for the prompt template
    variables = {
        "cleaned_transcript": cleaned_transcript,
        "today_date": today.isoformat(),
    }

    # Load prompt template (editable via admin panel)
    prompt, config = await get_rendered_prompt("source_of_truth", variables)

    # Call LLM
    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=prompt,
        step="source_of_truth",
        response_format="json",
        job_id=job_id,
        user_id=user_id,
    )

    # Parse response
    result = parse_llm_json(response_text, context="source of truth")

    # Ensure required fields have defaults
    if not result.get("core_narratives"):
        result["core_narratives"] = []
    if not result.get("statistics"):
        result["statistics"] = []
    if not result.get("quotable_moments"):
        result["quotable_moments"] = []
    if not result.get("objections_qa"):
        result["objections_qa"] = []
    if not result.get("key_visuals"):
        result["key_visuals"] = []
    if not result.get("funnel_stage"):
        result["funnel_stage"] = "awareness"
    if not result.get("review_date"):
        result["review_date"] = (today + timedelta(days=180)).isoformat()

    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return result, cost


async def save_source_of_truth(
    job_id: str,
    user_id: int,
    source_data: dict,
) -> int:
    """
    Save Source of Truth to database.

    Args:
        job_id: The job ID this source belongs to
        user_id: The user ID
        source_data: The parsed source of truth data

    Returns:
        source_id: The ID of the created source record
    """
    async with get_db() as db:
        # Insert source record
        if settings.use_postgres:
            row = await db.fetchrow(
                """
                INSERT INTO sources (
                    job_id, user_id, core_narratives, statistics, quotable_moments,
                    primary_pain_point, the_promise, objections_qa, key_visuals,
                    funnel_stage, review_date
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id
                """,
                job_id,
                user_id,
                json.dumps(source_data.get("core_narratives", [])),
                json.dumps(source_data.get("statistics", [])),
                json.dumps(source_data.get("quotable_moments", [])),
                source_data.get("primary_pain_point", ""),
                source_data.get("the_promise", ""),
                json.dumps(source_data.get("objections_qa", [])),
                json.dumps(source_data.get("key_visuals", [])),
                source_data.get("funnel_stage", "awareness"),
                source_data.get("review_date"),
            )
            source_id = row["id"]
        else:
            cursor = await db.execute(
                """
                INSERT INTO sources (
                    job_id, user_id, core_narratives, statistics, quotable_moments,
                    primary_pain_point, the_promise, objections_qa, key_visuals,
                    funnel_stage, review_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    user_id,
                    json.dumps(source_data.get("core_narratives", [])),
                    json.dumps(source_data.get("statistics", [])),
                    json.dumps(source_data.get("quotable_moments", [])),
                    source_data.get("primary_pain_point", ""),
                    source_data.get("the_promise", ""),
                    json.dumps(source_data.get("objections_qa", [])),
                    json.dumps(source_data.get("key_visuals", [])),
                    source_data.get("funnel_stage", "awareness"),
                    source_data.get("review_date"),
                )
            )
            source_id = cursor.lastrowid
            await db.commit()

        # Update job with source_id
        await execute(
            db,
            "UPDATE jobs SET source_id = ? WHERE id = ?",
            (source_id, job_id)
        )
        if not settings.use_postgres:
            await db.commit()

    logger.info(f"Saved Source of Truth {source_id} for job {job_id}")
    return source_id


async def approve_source_of_truth(source_id: int) -> None:
    """
    Mark Source of Truth as approved, allowing distillation to proceed.

    Args:
        source_id: The source ID to approve
    """
    async with get_db() as db:
        await execute(
            db,
            """
            UPDATE sources
            SET is_approved = ?, approved_at = ?
            WHERE id = ?
            """,
            (True, datetime.now(), source_id)
        )
        if not settings.use_postgres:
            await db.commit()

    logger.info(f"Source of Truth {source_id} approved")


async def get_source_of_truth(source_id: int) -> Optional[Dict]:
    """
    Get Source of Truth by ID.

    Args:
        source_id: The source ID

    Returns:
        Source of Truth data dict or None
    """
    async with get_db() as db:
        row = await fetchone(
            db,
            "SELECT * FROM sources WHERE id = ?",
            (source_id,)
        )

        if not row:
            return None

        return {
            "id": row["id"],
            "job_id": row["job_id"],
            "user_id": row["user_id"],
            "core_narratives": json.loads(row["core_narratives"]) if row["core_narratives"] else [],
            "statistics": json.loads(row["statistics"]) if row["statistics"] else [],
            "quotable_moments": json.loads(row["quotable_moments"]) if row["quotable_moments"] else [],
            "primary_pain_point": row["primary_pain_point"],
            "the_promise": row["the_promise"],
            "objections_qa": json.loads(row["objections_qa"]) if row["objections_qa"] else [],
            "key_visuals": json.loads(row["key_visuals"]) if row["key_visuals"] else [],
            "funnel_stage": row["funnel_stage"],
            "review_date": row["review_date"],
            "is_approved": row["is_approved"],
            "approved_at": row["approved_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


async def get_source_of_truth_by_job(job_id: str) -> Optional[Dict]:
    """
    Get Source of Truth by job ID.

    Args:
        job_id: The job ID

    Returns:
        Source of Truth data dict or None
    """
    async with get_db() as db:
        row = await fetchone(
            db,
            "SELECT * FROM sources WHERE job_id = ?",
            (job_id,)
        )

        if not row:
            return None

        return {
            "id": row["id"],
            "job_id": row["job_id"],
            "user_id": row["user_id"],
            "core_narratives": json.loads(row["core_narratives"]) if row["core_narratives"] else [],
            "statistics": json.loads(row["statistics"]) if row["statistics"] else [],
            "quotable_moments": json.loads(row["quotable_moments"]) if row["quotable_moments"] else [],
            "primary_pain_point": row["primary_pain_point"],
            "the_promise": row["the_promise"],
            "objections_qa": json.loads(row["objections_qa"]) if row["objections_qa"] else [],
            "key_visuals": json.loads(row["key_visuals"]) if row["key_visuals"] else [],
            "funnel_stage": row["funnel_stage"],
            "review_date": row["review_date"],
            "is_approved": row["is_approved"],
            "approved_at": row["approved_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


async def update_source_of_truth(
    source_id: int,
    updates: dict,
) -> None:
    """
    Update Source of Truth fields.

    Args:
        source_id: The source ID to update
        updates: Dict of fields to update
    """
    allowed_fields = [
        "core_narratives", "statistics", "quotable_moments",
        "primary_pain_point", "the_promise", "objections_qa",
        "key_visuals", "funnel_stage", "review_date"
    ]

    # Build update query
    set_clauses = []
    values = []

    for field in allowed_fields:
        if field in updates:
            set_clauses.append(f"{field} = ?")
            value = updates[field]
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            values.append(value)

    if not set_clauses:
        return

    set_clauses.append("updated_at = ?")
    values.append(datetime.now())
    values.append(source_id)

    query = f"UPDATE sources SET {', '.join(set_clauses)} WHERE id = ?"

    async with get_db() as db:
        await execute(db, query, tuple(values))
        if not settings.use_postgres:
            await db.commit()

    logger.info(f"Updated Source of Truth {source_id}")


async def get_statistics_for_factcheck(source_id: int) -> list:
    """
    Get statistics from Source of Truth formatted for fact-checking.

    Args:
        source_id: The source ID

    Returns:
        List of statistics with citation info
    """
    source = await get_source_of_truth(source_id)
    if not source:
        return []

    return source.get("statistics", [])
