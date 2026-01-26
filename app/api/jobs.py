"""Job management API endpoints."""
import json
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional

from app.config import get_settings
from app.database import get_db
from app.db_utils import fetchone, fetchall, fetchval, sql
from app.models.job import JobStatus, JobStatusResponse
from app.api.auth import get_current_user_id
from app.rate_limiter import limiter

settings = get_settings()

router = APIRouter()


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
        row = await fetchone(
            db,
            """
            SELECT id, user_id, status, current_step, progress, error_message,
                   transcript, cleaned_transcript
            FROM jobs WHERE id = ? AND user_id = ?
            """,
            (job_id, user_id)
        )

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
        job = await fetchone(
            db,
            """
            SELECT id, user_id, status, original_filename, target_persona,
                   asset_types, asset_quantities, cost_incurred,
                   created_at, completed_at, error_message
            FROM jobs WHERE id = ? AND user_id = ?
            """,
            (job_id, user_id)
        )

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get outputs
        output_rows = await fetchall(
            db,
            """
            SELECT id, content_type, variation_number,
                   step1_draft, step2_edited, step3_final,
                   stills_used, citations, warnings, quality_scores,
                   hook_variations, subject, preview_text,
                   email_day, email_purpose, sequence_name
            FROM outputs WHERE job_id = ?
            ORDER BY content_type, variation_number
            """,
            (job_id,)
        )

        # Collect output IDs for batch fetching image prompts
        output_ids = [row["id"] for row in output_rows]

        # Fetch all image prompts for these outputs in a single query (fixes N+1)
        image_prompts_by_output = {}
        if output_ids:
            # Build parameterized IN clause
            if settings.use_postgres:
                placeholders = ",".join(f"${i+1}" for i in range(len(output_ids)))
            else:
                placeholders = ",".join("?" * len(output_ids))
            query = f"SELECT id, output_id, prompt_text, platform, dimensions, style_modifiers FROM image_prompts WHERE output_id IN ({placeholders})"
            prompt_rows = await fetchall(db, query, tuple(output_ids)) if not settings.use_postgres else await db.fetch(query, *output_ids)
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
                "stills_used": json.loads(row["stills_used"]) if row["stills_used"] else [],
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
        still_rows = await fetchall(
            db,
            """
            SELECT id, still_type, content, source_location,
                   tags, persona_relevance, quote_attribution
            FROM stills WHERE job_id = ?
            ORDER BY still_type
            """,
            (job_id,)
        )

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

        rows = await fetchall(db, query, tuple(params))

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

        total = await fetchval(db, count_query, tuple(count_params))

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
        user_row = await fetchone(db, "SELECT total_cost_incurred FROM users WHERE id = ?", (user_id,))
        total_cost = user_row["total_cost_incurred"] if user_row else 0.0

        # Get job counts by status
        status_rows = await fetchall(
            db,
            """
            SELECT status, COUNT(*) as count
            FROM jobs
            WHERE user_id = ?
            GROUP BY status
            """,
            (user_id,)
        )
        status_counts = {row["status"]: row["count"] for row in status_rows}

        # Get total jobs
        total_jobs = await fetchval(db, "SELECT COUNT(*) FROM jobs WHERE user_id = ?", (user_id,))

        # Get cost breakdown by month (last 6 months)
        if settings.use_postgres:
            monthly_query = """
                SELECT
                    TO_CHAR(created_at, 'YYYY-MM') as month,
                    SUM(cost_incurred) as cost,
                    COUNT(*) as job_count
                FROM jobs
                WHERE user_id = $1
                    AND created_at >= CURRENT_DATE - INTERVAL '6 months'
                GROUP BY TO_CHAR(created_at, 'YYYY-MM')
                ORDER BY month DESC
            """
            monthly_rows = await db.fetch(monthly_query, user_id)
            monthly_costs = [
                {"month": row["month"], "cost": row["cost"], "jobs": row["job_count"]}
                for row in monthly_rows
            ]
        else:
            monthly_rows = await fetchall(
                db,
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
                for row in monthly_rows
            ]

        # Get content type breakdown
        content_rows = await fetchall(
            db,
            """
            SELECT content_type, COUNT(*) as count
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE j.user_id = ?
            GROUP BY content_type
            """,
            (user_id,)
        )
        content_counts = {row["content_type"]: row["count"] for row in content_rows}

        # Get library size
        library_size = await fetchval(db, "SELECT COUNT(*) FROM content_library WHERE user_id = ?", (user_id,))

        return {
            "total_cost": round(total_cost, 4),
            "total_jobs": total_jobs,
            "jobs_by_status": status_counts,
            "monthly_costs": monthly_costs,
            "content_created": content_counts,
            "library_size": library_size,
        }


@router.post("/jobs/{job_id}/approve-source")
async def approve_job_source(
    job_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """
    Approve Source of Truth and resume pipeline.

    This endpoint is called when the user reviews and approves the
    Source of Truth, allowing the pipeline to continue to distillation.
    """
    import asyncio
    from app.services.source_of_truth import approve_source_of_truth
    from app.services.pipeline import resume_pipeline_from_distillation

    # Get job and verify ownership
    async with get_db() as db:
        job = await fetchone(
            db,
            "SELECT id, user_id, status, source_id FROM jobs WHERE id = ?",
            (job_id,)
        )

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if job["status"] != "awaiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not awaiting approval (current status: {job['status']})"
        )

    if not job["source_id"]:
        raise HTTPException(status_code=400, detail="No Source of Truth found for this job")

    # Approve the source
    await approve_source_of_truth(job["source_id"])

    # Resume pipeline in background
    asyncio.create_task(resume_pipeline_from_distillation(job_id))

    return {
        "status": "approved",
        "message": "Source of Truth approved. Pipeline resuming.",
        "job_id": job_id
    }


@router.get("/jobs/{job_id}/source")
async def get_job_source(
    job_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """Get the Source of Truth for a job."""
    from app.services.source_of_truth import get_source_of_truth_by_job

    # Verify job ownership
    async with get_db() as db:
        job = await fetchone(
            db,
            "SELECT user_id FROM jobs WHERE id = ?",
            (job_id,)
        )

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    source = await get_source_of_truth_by_job(job_id)

    if not source:
        raise HTTPException(status_code=404, detail="No Source of Truth found")

    return source


@router.put("/jobs/{job_id}/source")
async def update_job_source(
    job_id: str,
    updates: dict,
    user_id: int = Depends(get_current_user_id),
):
    """Update the Source of Truth for a job (before approval)."""
    from app.services.source_of_truth import update_source_of_truth

    # Verify job ownership
    async with get_db() as db:
        job = await fetchone(
            db,
            "SELECT user_id, source_id FROM jobs WHERE id = ?",
            (job_id,)
        )

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not job["source_id"]:
        raise HTTPException(status_code=404, detail="No Source of Truth found")

    await update_source_of_truth(job["source_id"], updates)

    return {"status": "updated", "message": "Source of Truth updated"}
