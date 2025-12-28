"""Edit API endpoints for tone adjustment and content regeneration."""
import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.api.auth import get_current_user_id
from app.services.content_editor import (
    adjust_tone,
    apply_edit_instructions,
    get_tone_presets,
    TONE_PRESETS
)

router = APIRouter()


class ToneAdjustRequest(BaseModel):
    """Request to adjust content tone."""
    output_id: int
    tone_preset: str
    custom_instructions: Optional[str] = None


class EditRequest(BaseModel):
    """Request to apply custom edits."""
    output_id: int
    instructions: str


class SaveEditRequest(BaseModel):
    """Request to save manual edits."""
    output_id: int
    edited_content: str
    edit_note: Optional[str] = None


@router.get("/edit/tone-presets")
async def list_tone_presets():
    """Get all available tone presets."""
    return {
        "presets": get_tone_presets()
    }


@router.post("/edit/adjust-tone")
async def adjust_content_tone(
    data: ToneAdjustRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Adjust the tone of an output using a preset or custom instructions.

    Returns the adjusted content without saving (preview).
    """
    # Validate tone preset
    if data.tone_preset not in TONE_PRESETS and not data.custom_instructions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tone preset. Available: {list(TONE_PRESETS.keys())}"
        )

    async with get_db() as db:
        # Get output and verify access
        cursor = await db.execute(
            """
            SELECT o.*, j.id as job_id FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE o.id = ? AND j.user_id = ?
            """,
            (data.output_id, user_id)
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Output not found")

        # Get the current content
        content = row["step3_final"] or row["step2_edited"] or row["step1_draft"]
        if not content:
            raise HTTPException(status_code=400, detail="Output has no content")

        job_id = row["job_id"]
        content_type = row["content_type"]

    # Adjust tone
    adjusted_content, cost = await adjust_tone(
        content=content,
        tone_preset=data.tone_preset,
        content_type=content_type,
        custom_instructions=data.custom_instructions,
        job_id=job_id,
        user_id=user_id,
    )

    # Update user's cost
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET total_cost_incurred = total_cost_incurred + ? WHERE id = ?",
            (cost, user_id)
        )
        await db.commit()

    return {
        "output_id": data.output_id,
        "original_content": content,
        "adjusted_content": adjusted_content,
        "tone": data.tone_preset,
        "cost": cost
    }


@router.post("/edit/apply-changes")
async def apply_changes(
    data: EditRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Apply custom edit instructions to an output.

    Returns the edited content without saving (preview).
    """
    async with get_db() as db:
        # Get output and verify access
        cursor = await db.execute(
            """
            SELECT o.*, j.id as job_id FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE o.id = ? AND j.user_id = ?
            """,
            (data.output_id, user_id)
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Output not found")

        content = row["step3_final"] or row["step2_edited"] or row["step1_draft"]
        if not content:
            raise HTTPException(status_code=400, detail="Output has no content")

        job_id = row["job_id"]
        content_type = row["content_type"]

    # Apply edits
    edited_content, change_summary, cost = await apply_edit_instructions(
        content=content,
        instructions=data.instructions,
        content_type=content_type,
        job_id=job_id,
        user_id=user_id,
    )

    # Update user's cost
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET total_cost_incurred = total_cost_incurred + ? WHERE id = ?",
            (cost, user_id)
        )
        await db.commit()

    return {
        "output_id": data.output_id,
        "original_content": content,
        "edited_content": edited_content,
        "change_summary": change_summary,
        "instructions": data.instructions,
        "cost": cost
    }


@router.post("/edit/{output_id}/save")
async def save_edit(
    output_id: int,
    data: SaveEditRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Save edited content to the output and record in edit history.
    """
    async with get_db() as db:
        # Get output and verify access
        cursor = await db.execute(
            """
            SELECT o.*, j.id as job_id FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE o.id = ? AND j.user_id = ?
            """,
            (data.output_id, user_id)
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Output not found")

        # Get current content for history
        current_content = row["step3_final"] or row["step2_edited"] or row["step1_draft"]

        # Save to edit history
        await db.execute(
            """
            INSERT INTO output_edits (output_id, user_id, previous_content, new_content, edit_note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (output_id, user_id, current_content, data.edited_content, data.edit_note)
        )

        # Update output with new content
        await db.execute(
            """
            UPDATE outputs
            SET step3_final = ?, user_edits = user_edits + 1
            WHERE id = ?
            """,
            (data.edited_content, output_id)
        )

        await db.commit()

        return {
            "success": True,
            "output_id": output_id,
            "message": "Edit saved successfully"
        }


@router.get("/edit/{output_id}/history")
async def get_edit_history(
    output_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Get edit history for an output."""
    async with get_db() as db:
        # Verify access
        cursor = await db.execute(
            """
            SELECT o.id FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE o.id = ? AND j.user_id = ?
            """,
            (output_id, user_id)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Output not found")

        # Get edit history
        cursor = await db.execute(
            """
            SELECT id, previous_content, new_content, edit_note, created_at
            FROM output_edits
            WHERE output_id = ?
            ORDER BY created_at DESC
            """,
            (output_id,)
        )
        rows = await cursor.fetchall()

        history = []
        for row in rows:
            history.append({
                "id": row["id"],
                "previous_content": row["previous_content"],
                "new_content": row["new_content"],
                "edit_note": row["edit_note"],
                "created_at": row["created_at"]
            })

        return {
            "output_id": output_id,
            "edit_count": len(history),
            "history": history
        }


@router.post("/edit/{output_id}/revert/{edit_id}")
async def revert_to_version(
    output_id: int,
    edit_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Revert output to a previous version from edit history."""
    async with get_db() as db:
        # Verify access and get edit record
        cursor = await db.execute(
            """
            SELECT e.*, o.step3_final as current_content
            FROM output_edits e
            JOIN outputs o ON e.output_id = o.id
            JOIN jobs j ON o.job_id = j.id
            WHERE e.id = ? AND e.output_id = ? AND j.user_id = ?
            """,
            (edit_id, output_id, user_id)
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Edit record not found")

        # The previous_content is what we want to revert TO
        revert_content = row["previous_content"]
        current_content = row["current_content"]

        # Save current as new edit history entry
        await db.execute(
            """
            INSERT INTO output_edits (output_id, user_id, previous_content, new_content, edit_note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (output_id, user_id, current_content, revert_content, f"Reverted to version from edit #{edit_id}")
        )

        # Update output
        await db.execute(
            "UPDATE outputs SET step3_final = ?, user_edits = user_edits + 1 WHERE id = ?",
            (revert_content, output_id)
        )

        await db.commit()

        return {
            "success": True,
            "output_id": output_id,
            "reverted_to_edit_id": edit_id,
            "content": revert_content
        }
