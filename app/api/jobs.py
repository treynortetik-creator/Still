"""Job management API endpoints."""
import json
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.job import JobStatus, JobStatusResponse
from app.api.auth import get_current_user_id

router = APIRouter()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


def estimate_time_remaining(status: str, progress: int) -> Optional[str]:
    """Estimate time remaining based on current progress."""
    if status == JobStatus.COMPLETE.value:
        return None
    if status == JobStatus.FAILED.value:
        return None

    # Rough estimates based on typical processing times
    if progress < 20:
        return "5-10 minutes"
    elif progress < 40:
        return "4-8 minutes"
    elif progress < 60:
        return "3-5 minutes"
    elif progress < 80:
        return "1-3 minutes"
    else:
        return "Less than 1 minute"


@router.get("/job/{job_id}/status")
@limiter.limit("1000/hour")
async def get_job_status(
    request: Request,
    job_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """
    Get the current status of a processing job.

    Returns progress percentage, current step, estimated time remaining,
    and partial transcript preview during processing.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id, user_id, status, current_step, progress, error_message,
                   transcript, cleaned_transcript
            FROM jobs WHERE id = ? AND user_id = ?
            """,
            (job_id, user_id)
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get partial transcript preview (first 1000 chars)
        partial_transcript = None
        if row["cleaned_transcript"]:
            partial_transcript = row["cleaned_transcript"][:1000]
        elif row["transcript"]:
            partial_transcript = row["transcript"][:1000]

        return {
            "job_id": row["id"],
            "status": row["status"],
            "current_step": row["current_step"],
            "progress": row["progress"],
            "estimated_time_remaining": estimate_time_remaining(row["status"], row["progress"]),
            "error_message": row["error_message"],
            "partial_transcript": partial_transcript,
        }


@router.get("/job/{job_id}/results")
@limiter.limit("1000/hour")
async def get_job_results(
    request: Request,
    job_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """
    Get the results of a completed job.

    Returns all generated outputs, extracted stills, and cost information.
    """
    async with get_db() as db:
        # Get job details (scoped to user)
        cursor = await db.execute(
            """
            SELECT id, user_id, status, original_filename, target_persona,
                   asset_types, asset_quantities, cost_incurred,
                   created_at, completed_at, error_message
            FROM jobs WHERE id = ? AND user_id = ?
            """,
            (job_id, user_id)
        )
        job = await cursor.fetchone()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get outputs
        cursor = await db.execute(
            """
            SELECT id, content_type, variation_number,
                   step1_draft, step2_edited, step3_final,
                   atoms_used, citations, warnings, quality_scores,
                   hook_variations, subject, preview_text,
                   email_day, email_purpose, sequence_name
            FROM outputs WHERE job_id = ?
            ORDER BY content_type, variation_number
            """,
            (job_id,)
        )
        output_rows = await cursor.fetchall()

        # Collect output IDs for batch fetching image prompts
        output_ids = [row["id"] for row in output_rows]

        # Fetch all image prompts for these outputs in a single query (fixes N+1)
        image_prompts_by_output = {}
        if output_ids:
            placeholders = ",".join("?" * len(output_ids))
            prompt_cursor = await db.execute(
                f"SELECT id, output_id, prompt_text, platform, dimensions, style_modifiers FROM image_prompts WHERE output_id IN ({placeholders})",
                output_ids
            )
            prompt_rows = await prompt_cursor.fetchall()
            for p in prompt_rows:
                output_id = p["output_id"]
                if output_id not in image_prompts_by_output:
                    image_prompts_by_output[output_id] = []
                image_prompts_by_output[output_id].append({
                    "id": p["id"],
                    "prompt_text": p["prompt_text"],
                    "platform": p["platform"],
                    "dimensions": p["dimensions"],
                    "style_modifiers": p["style_modifiers"],
                })

        outputs = []
        for row in output_rows:
            output_data = {
                "id": row["id"],
                "content_type": row["content_type"],
                "variation_number": row["variation_number"],
                "step1_draft": row["step1_draft"],
                "step2_edited": row["step2_edited"],
                "step3_final": row["step3_final"],
                "atoms_used": json.loads(row["atoms_used"]) if row["atoms_used"] else [],
                "citations": json.loads(row["citations"]) if row["citations"] else [],
                "warnings": json.loads(row["warnings"]) if row["warnings"] else [],
                "quality_scores": json.loads(row["quality_scores"]) if row["quality_scores"] else {},
                "hook_variations": json.loads(row["hook_variations"]) if row["hook_variations"] else [],
            }
            # Add email sequence fields if present
            if row["subject"]:
                output_data["subject"] = row["subject"]
            if row["preview_text"]:
                output_data["preview_text"] = row["preview_text"]
            if row["email_day"] is not None:
                output_data["email_day"] = row["email_day"]
            if row["email_purpose"]:
                output_data["email_purpose"] = row["email_purpose"]
            if row["sequence_name"]:
                output_data["sequence_name"] = row["sequence_name"]

            # Get image prompts from the batch-fetched dictionary
            output_data["image_prompts"] = image_prompts_by_output.get(row["id"], [])

            outputs.append(output_data)

        # Get stills
        cursor = await db.execute(
            """
            SELECT id, still_type, content, source_location,
                   tags, persona_relevance, quote_attribution
            FROM stills WHERE job_id = ?
            ORDER BY still_type
            """,
            (job_id,)
        )
        still_rows = await cursor.fetchall()

        stills = []
        for row in still_rows:
            stills.append({
                "id": row["id"],
                "type": row["still_type"],
                "content": row["content"],
                "source_location": row["source_location"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "persona_relevance": json.loads(row["persona_relevance"]) if row["persona_relevance"] else {},
                "quote_attribution": row["quote_attribution"],
            })

        return {
            "job_id": job["id"],
            "status": job["status"],
            "original_filename": job["original_filename"],
            "target_persona": job["target_persona"],
            "asset_types": json.loads(job["asset_types"]) if job["asset_types"] else [],
            "asset_quantities": json.loads(job["asset_quantities"]) if job["asset_quantities"] else {},
            "outputs": outputs,
            "stills": stills,
            "atoms": stills,  # Keep for backwards compatibility
            "cost_incurred": job["cost_incurred"],
            "created_at": job["created_at"],
            "completed_at": job["completed_at"],
            "error_message": job["error_message"],
        }


@router.get("/jobs")
@limiter.limit("1000/hour")
async def list_jobs(
    request: Request,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    user_id: int = Depends(get_current_user_id),
):
    """
    List all jobs for the current user with optional status filter.
    """
    async with get_db() as db:
        query = """
            SELECT id, status, original_filename, target_persona,
                   current_step, progress, cost_incurred,
                   created_at, completed_at
            FROM jobs
            WHERE user_id = ?
        """
        params = [user_id]

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

        jobs = []
        for row in rows:
            jobs.append({
                "id": row["id"],
                "status": row["status"],
                "original_filename": row["original_filename"],
                "target_persona": row["target_persona"],
                "current_step": row["current_step"],
                "progress": row["progress"],
                "cost_incurred": row["cost_incurred"],
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
            })

        # Get total count for this user
        count_query = "SELECT COUNT(*) FROM jobs WHERE user_id = ?"
        count_params = [user_id]

        if status:
            count_query += " AND status = ?"
            count_params.append(status)

        cursor = await db.execute(count_query, count_params)
        total = (await cursor.fetchone())[0]

        return {
            "jobs": jobs,
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.get("/usage")
@limiter.limit("1000/hour")
async def get_usage_stats(request: Request, user_id: int = Depends(get_current_user_id)):
    """
    Get usage statistics and costs for the current user.
    """
    async with get_db() as db:
        # Get user's total cost
        cursor = await db.execute(
            "SELECT total_cost_incurred FROM users WHERE id = ?",
            (user_id,)
        )
        user_row = await cursor.fetchone()
        total_cost = user_row["total_cost_incurred"] if user_row else 0.0

        # Get job counts by status
        cursor = await db.execute(
            """
            SELECT status, COUNT(*) as count
            FROM jobs
            WHERE user_id = ?
            GROUP BY status
            """,
            (user_id,)
        )
        status_counts = {row["status"]: row["count"] for row in await cursor.fetchall()}

        # Get total jobs
        cursor = await db.execute(
            "SELECT COUNT(*) FROM jobs WHERE user_id = ?",
            (user_id,)
        )
        total_jobs = (await cursor.fetchone())[0]

        # Get cost breakdown by month (last 6 months)
        cursor = await db.execute(
            """
            SELECT
                strftime('%Y-%m', created_at) as month,
                SUM(cost_incurred) as cost,
                COUNT(*) as job_count
            FROM jobs
            WHERE user_id = ?
                AND created_at >= date('now', '-6 months')
            GROUP BY strftime('%Y-%m', created_at)
            ORDER BY month DESC
            """,
            (user_id,)
        )
        monthly_costs = [
            {"month": row["month"], "cost": row["cost"], "jobs": row["job_count"]}
            for row in await cursor.fetchall()
        ]

        # Get content type breakdown
        cursor = await db.execute(
            """
            SELECT content_type, COUNT(*) as count
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE j.user_id = ?
            GROUP BY content_type
            """,
            (user_id,)
        )
        content_counts = {row["content_type"]: row["count"] for row in await cursor.fetchall()}

        # Get library size
        cursor = await db.execute(
            "SELECT COUNT(*) FROM content_library WHERE user_id = ?",
            (user_id,)
        )
        library_size = (await cursor.fetchone())[0]

        return {
            "total_cost": round(total_cost, 4),
            "total_jobs": total_jobs,
            "jobs_by_status": status_counts,
            "monthly_costs": monthly_costs,
            "content_created": content_counts,
            "library_size": library_size,
        }
