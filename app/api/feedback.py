"""Feedback API endpoints for thumbs up/down ratings on outputs."""
import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall
from app.api.auth import get_current_user_id

settings = get_settings()

router = APIRouter()


class FeedbackCreate(BaseModel):
    """Create/update feedback for an output."""
    output_id: int
    feedback: Literal["thumbs_up", "thumbs_down"]
    comment: Optional[str] = Field(None, max_length=2000)


class FeedbackResponse(BaseModel):
    """Response for feedback operations."""
    id: int
    output_id: int
    user_id: int
    feedback: str
    comment: Optional[str]
    created_at: str


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    data: FeedbackCreate,
    user_id: int = Depends(get_current_user_id),
):
    """
    Submit feedback (thumbs up/down) for an output.

    Upserts - if feedback already exists for this user/output, it updates.
    """
    async with get_db() as db:
        # Verify output exists and belongs to user's job
        output_row = await fetchone(
            db,
            """
            SELECT o.id FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE o.id = ? AND j.user_id = ?
            """,
            (data.output_id, user_id)
        )
        if not output_row:
            raise HTTPException(status_code=404, detail="Output not found")

        # Check if feedback already exists
        existing = await fetchone(
            db,
            "SELECT id FROM output_feedback WHERE output_id = ? AND user_id = ?",
            (data.output_id, user_id)
        )

        if existing:
            # Update existing feedback
            await execute(
                db,
                """
                UPDATE output_feedback
                SET feedback = ?, comment = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (data.feedback, data.comment, existing["id"])
            )
            feedback_id = existing["id"]
        else:
            # Insert new feedback
            if settings.use_postgres:
                row = await db.fetchrow(
                    """
                    INSERT INTO output_feedback (output_id, user_id, feedback, comment)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                    """,
                    data.output_id, user_id, data.feedback, data.comment
                )
                feedback_id = row["id"]
            else:
                cursor = await db.execute(
                    """
                    INSERT INTO output_feedback (output_id, user_id, feedback, comment)
                    VALUES (?, ?, ?, ?)
                    """,
                    (data.output_id, user_id, data.feedback, data.comment)
                )
                feedback_id = cursor.lastrowid

        if not settings.use_postgres:
            await db.commit()

        # Fetch and return the feedback
        row = await fetchone(
            db,
            "SELECT * FROM output_feedback WHERE id = ?",
            (feedback_id,)
        )

        return FeedbackResponse(
            id=row["id"],
            output_id=row["output_id"],
            user_id=row["user_id"],
            feedback=row["feedback"],
            comment=row["comment"],
            created_at=row["created_at"]
        )


@router.get("/feedback/{output_id}")
async def get_feedback(
    output_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Get feedback for a specific output."""
    async with get_db() as db:
        row = await fetchone(
            db,
            """
            SELECT * FROM output_feedback
            WHERE output_id = ? AND user_id = ?
            """,
            (output_id, user_id)
        )

        if not row:
            return {"feedback": None}

        return {
            "id": row["id"],
            "output_id": row["output_id"],
            "feedback": row["feedback"],
            "comment": row["comment"],
            "created_at": row["created_at"]
        }


@router.delete("/feedback/{output_id}")
async def delete_feedback(
    output_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Remove feedback for an output."""
    async with get_db() as db:
        result = await execute(
            db,
            "DELETE FROM output_feedback WHERE output_id = ? AND user_id = ?",
            (output_id, user_id)
        )
        if not settings.use_postgres:
            await db.commit()

        # Check if any rows were affected
        if settings.use_postgres:
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="Feedback not found")
        else:
            if result == 0:
                raise HTTPException(status_code=404, detail="Feedback not found")

        return {"success": True, "message": "Feedback removed"}


@router.get("/feedback/summary/{job_id}")
async def get_feedback_summary(
    job_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """Get feedback summary for all outputs in a job."""
    async with get_db() as db:
        # Verify job belongs to user
        job_row = await fetchone(
            db,
            "SELECT id FROM jobs WHERE id = ? AND user_id = ?",
            (job_id, user_id)
        )
        if not job_row:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get all feedback for this job's outputs
        rows = await fetchall(
            db,
            """
            SELECT
                f.output_id,
                f.feedback,
                f.comment,
                o.content_type,
                o.variation_number
            FROM output_feedback f
            JOIN outputs o ON f.output_id = o.id
            WHERE o.job_id = ? AND f.user_id = ?
            """,
            (job_id, user_id)
        )

        feedback_list = []
        thumbs_up = 0
        thumbs_down = 0

        for row in rows:
            feedback_list.append({
                "output_id": row["output_id"],
                "feedback": row["feedback"],
                "comment": row["comment"],
                "content_type": row["content_type"],
                "variation_number": row["variation_number"]
            })
            if row["feedback"] == "thumbs_up":
                thumbs_up += 1
            else:
                thumbs_down += 1

        return {
            "job_id": job_id,
            "total_feedback": len(feedback_list),
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "feedback": feedback_list
        }
