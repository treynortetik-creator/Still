"""Workshop API endpoints for content editing."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall
from app.api.auth import get_current_user_id
from app.services.ai_editor import get_ai_edit_suggestions
from app.models.workshop import (
    WorkshopOutputListItem,
    WorkshopOutputList,
    WorkshopOutputDetail,
    WorkshopContentUpdate,
    WorkshopStatusUpdate,
    WorkshopUpdateResponse,
    StillPreview,
    AIEditRequest,
)

settings = get_settings()
router = APIRouter()


@router.get("/workshop", response_model=WorkshopOutputList)
async def list_workshop_outputs(
    status: Optional[str] = Query(None, description="Filter by status: draft, polished, published"),
    user_id: int = Depends(get_current_user_id),
):
    """List all outputs for the current user in the workshop."""
    async with get_db() as db:
        # Build query with optional status filter
        query = """
            SELECT o.id, o.job_id, o.content_type, o.status, o.step3_final,
                   o.edited_content, o.last_edited, o.created_at,
                   o.subject, o.email_day
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE j.user_id = ?
        """
        params = [user_id]

        if status:
            query += " AND o.status = ?"
            params.append(status)

        query += " ORDER BY COALESCE(o.last_edited, o.created_at) DESC"

        rows = await fetchall(db, query, tuple(params))

        outputs = []
        for row in rows:
            # Get preview from edited content or original
            content = row["edited_content"] or row["step3_final"] or ""
            # Get first line or first 100 chars as preview
            preview = content.split('\n')[0][:100] if content else ""
            if len(content) > 100 and len(preview) == 100:
                preview += "..."

            outputs.append(WorkshopOutputListItem(
                id=row["id"],
                job_id=row["job_id"],
                content_type=row["content_type"],
                status=row["status"] or "draft",
                preview=preview,
                last_edited=row["last_edited"],
                created_at=row["created_at"],
                subject=row["subject"],
                email_day=row["email_day"],
            ))

        return WorkshopOutputList(outputs=outputs, total=len(outputs))


@router.get("/workshop/{output_id}", response_model=WorkshopOutputDetail)
async def get_workshop_output(
    output_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Get a single output for editing in the workshop."""
    async with get_db() as db:
        # Get the output with user verification
        row = await fetchone(
            db,
            """
            SELECT o.id, o.job_id, o.content_type, o.status, o.step3_final,
                   o.edited_content, o.last_edited, o.created_at,
                   o.subject, o.email_day, o.email_purpose, o.sequence_name
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE o.id = ? AND j.user_id = ?
            """,
            (output_id, user_id)
        )

        if not row:
            raise HTTPException(status_code=404, detail="Output not found")

        # Get the content (user edits take priority)
        content = row["edited_content"] or row["step3_final"] or ""
        original_content = row["step3_final"] or ""

        # Get stills from the parent job
        still_rows = await fetchall(
            db,
            """
            SELECT id, still_type, content, source_location
            FROM stills
            WHERE job_id = ?
            ORDER BY id
            """,
            (row["job_id"],)
        )

        stills = [
            StillPreview(
                id=s["id"],
                still_type=s["still_type"],
                content=s["content"][:200] + "..." if len(s["content"]) > 200 else s["content"],
                source_location=s["source_location"],
            )
            for s in still_rows
        ]

        return WorkshopOutputDetail(
            id=row["id"],
            job_id=row["job_id"],
            content_type=row["content_type"],
            status=row["status"] or "draft",
            content=content,
            original_content=original_content,
            last_edited=row["last_edited"],
            created_at=row["created_at"],
            character_count=len(content),
            subject=row["subject"],
            email_day=row["email_day"],
            email_purpose=row["email_purpose"],
            sequence_name=row["sequence_name"],
            stills=stills,
        )


@router.put("/workshop/{output_id}", response_model=WorkshopUpdateResponse)
async def update_workshop_content(
    output_id: int,
    data: WorkshopContentUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """Save edited content for an output."""
    async with get_db() as db:
        # Verify ownership
        row = await fetchone(
            db,
            """
            SELECT o.id
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE o.id = ? AND j.user_id = ?
            """,
            (output_id, user_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Output not found")

        # Update the content
        now = datetime.utcnow()
        await execute(
            db,
            """
            UPDATE outputs
            SET edited_content = ?, last_edited = ?
            WHERE id = ?
            """,
            (data.content, now, output_id)
        )
        if not settings.use_postgres:
            await db.commit()

        # Get updated record
        updated = await fetchone(
            db,
            "SELECT status, last_edited FROM outputs WHERE id = ?",
            (output_id,)
        )

        return WorkshopUpdateResponse(
            id=output_id,
            status=updated["status"] or "draft",
            last_edited=updated["last_edited"],
            message="Content saved successfully"
        )


@router.patch("/workshop/{output_id}/status", response_model=WorkshopUpdateResponse)
async def update_workshop_status(
    output_id: int,
    data: WorkshopStatusUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """Update the status of an output."""
    async with get_db() as db:
        # Verify ownership
        row = await fetchone(
            db,
            """
            SELECT o.id
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE o.id = ? AND j.user_id = ?
            """,
            (output_id, user_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Output not found")

        # Update the status
        now = datetime.utcnow()
        await execute(
            db,
            """
            UPDATE outputs
            SET status = ?, last_edited = ?
            WHERE id = ?
            """,
            (data.status, now, output_id)
        )
        if not settings.use_postgres:
            await db.commit()

        return WorkshopUpdateResponse(
            id=output_id,
            status=data.status,
            last_edited=now,
            message=f"Status updated to {data.status}"
        )


@router.delete("/workshop/{output_id}")
async def delete_workshop_output(
    output_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Delete an output from the workshop."""
    async with get_db() as db:
        # Verify ownership
        row = await fetchone(
            db,
            """
            SELECT o.id
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE o.id = ? AND j.user_id = ?
            """,
            (output_id, user_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Output not found")

        # Delete the output
        await execute(db, "DELETE FROM outputs WHERE id = ?", (output_id,))
        if not settings.use_postgres:
            await db.commit()

        return {"message": "Output deleted successfully"}


@router.post("/workshop/{output_id}/ai-edit")
async def request_ai_edit(
    output_id: int,
    data: AIEditRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Request AI editing suggestions for workshop content.

    Returns a list of suggested edits that can be accepted/rejected individually.
    """
    async with get_db() as db:
        # Verify ownership
        row = await fetchone(
            db,
            """
            SELECT o.id, o.content_type
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE o.id = ? AND j.user_id = ?
            """,
            (output_id, user_id)
        )

        if not row:
            raise HTTPException(status_code=404, detail="Output not found")

        content_type = data.content_type or row["content_type"]

    try:
        result, cost = await get_ai_edit_suggestions(
            content=data.content,
            user_prompt=data.prompt,
            user_id=user_id,
            persona_id=data.persona_id,
            content_type=content_type,
        )

        # Format suggestions
        suggestions = []
        for idx, s in enumerate(result.get("suggestions", [])):
            suggestions.append({
                "id": s.get("id", idx + 1),
                "original_text": s.get("original_text", ""),
                "suggested_text": s.get("suggested_text", ""),
                "explanation": s.get("explanation", ""),
                "type": s.get("type", "clarity"),
            })

        return {
            "suggestions": suggestions,
            "summary": result.get("summary", ""),
            "cost": round(cost, 6),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI editing failed: {str(e)}"
        )
