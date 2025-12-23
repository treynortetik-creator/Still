"""Job management API endpoints."""
import json
from fastapi import APIRouter, HTTPException
from typing import Optional

from app.database import get_db
from app.models.job import JobStatus, JobStatusResponse

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


@router.get("/job/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get the current status of a processing job.

    Returns progress percentage, current step, and estimated time remaining.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id, status, current_step, progress, error_message
            FROM jobs WHERE id = ?
            """,
            (job_id,)
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Job not found")

        return JobStatusResponse(
            job_id=row["id"],
            status=JobStatus(row["status"]),
            current_step=row["current_step"],
            progress=row["progress"],
            estimated_time_remaining=estimate_time_remaining(row["status"], row["progress"]),
            error_message=row["error_message"],
        )


@router.get("/job/{job_id}/results")
async def get_job_results(job_id: str):
    """
    Get the results of a completed job.

    Returns all generated outputs, extracted atoms, and cost information.
    """
    async with get_db() as db:
        # Get job details
        cursor = await db.execute(
            """
            SELECT id, status, original_filename, target_persona,
                   asset_types, asset_quantities, cost_incurred,
                   created_at, completed_at, error_message
            FROM jobs WHERE id = ?
            """,
            (job_id,)
        )
        job = await cursor.fetchone()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get outputs
        cursor = await db.execute(
            """
            SELECT id, content_type, variation_number,
                   step1_draft, step2_edited, step3_final,
                   atoms_used, citations, warnings
            FROM outputs WHERE job_id = ?
            ORDER BY content_type, variation_number
            """,
            (job_id,)
        )
        output_rows = await cursor.fetchall()

        outputs = []
        for row in output_rows:
            outputs.append({
                "id": row["id"],
                "content_type": row["content_type"],
                "variation_number": row["variation_number"],
                "step1_draft": row["step1_draft"],
                "step2_edited": row["step2_edited"],
                "step3_final": row["step3_final"],
                "atoms_used": json.loads(row["atoms_used"]) if row["atoms_used"] else [],
                "citations": json.loads(row["citations"]) if row["citations"] else [],
                "warnings": json.loads(row["warnings"]) if row["warnings"] else [],
            })

        # Get atoms
        cursor = await db.execute(
            """
            SELECT id, atom_type, content, source_location,
                   tags, persona_relevance, quote_attribution
            FROM atoms WHERE job_id = ?
            ORDER BY atom_type
            """,
            (job_id,)
        )
        atom_rows = await cursor.fetchall()

        atoms = []
        for row in atom_rows:
            atoms.append({
                "id": row["id"],
                "type": row["atom_type"],
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
            "atoms": atoms,
            "cost_incurred": job["cost_incurred"],
            "created_at": job["created_at"],
            "completed_at": job["completed_at"],
            "error_message": job["error_message"],
        }


@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    """
    List all jobs with optional status filter.
    """
    async with get_db() as db:
        query = """
            SELECT id, status, original_filename, target_persona,
                   current_step, progress, cost_incurred,
                   created_at, completed_at
            FROM jobs
        """
        params = []

        if status:
            query += " WHERE status = ?"
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

        # Get total count
        count_query = "SELECT COUNT(*) FROM jobs"
        if status:
            count_query += " WHERE status = ?"
            cursor = await db.execute(count_query, (status,))
        else:
            cursor = await db.execute(count_query)

        total = (await cursor.fetchone())[0]

        return {
            "jobs": jobs,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
