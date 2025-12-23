"""Content library API endpoints."""
import json
import uuid
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from typing import Optional

from app.database import get_db
from app.models.job import JobResponse, JobStatus
from app.api.auth import get_current_user_id

router = APIRouter()


@router.get("/library")
async def get_library(
    entry_type: Optional[str] = Query(None, description="Filter by entry type"),
    persona: Optional[str] = Query(None, description="Filter by persona relevance"),
    min_relevance: int = Query(1, description="Minimum relevance score (1-5)"),
    search: Optional[str] = Query(None, description="Search in content"),
    limit: int = Query(50, description="Number of results"),
    offset: int = Query(0, description="Offset for pagination"),
    user_id: int = Depends(get_current_user_id),
):
    """
    Get content library entries with filtering.
    """
    async with get_db() as db:
        # Build query
        query = "SELECT * FROM content_library WHERE user_id = ?"
        params = [user_id]

        if entry_type:
            query += " AND entry_type = ?"
            params.append(entry_type)

        if search:
            query += " AND content LIKE ?"
            params.append(f"%{search}%")

        query += " ORDER BY date_added DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

        entries = []
        for row in rows:
            persona_relevance = json.loads(row["persona_relevance"]) if row["persona_relevance"] else {}

            # Filter by persona relevance if specified
            if persona and persona in persona_relevance:
                if persona_relevance[persona] < min_relevance:
                    continue

            entries.append({
                "id": row["id"],
                "entry_type": row["entry_type"],
                "content": row["content"],
                "source": row["source"],
                "source_timestamp": row["source_timestamp"],
                "speaker": row["speaker"],
                "date_added": row["date_added"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "persona_relevance": persona_relevance,
                "times_used": row["times_used"],
                "last_used": row["last_used"],
                "user_notes": row["user_notes"],
            })

        # Get total count
        count_query = "SELECT COUNT(*) FROM content_library WHERE user_id = ?"
        count_params = [user_id]

        if entry_type:
            count_query += " AND entry_type = ?"
            count_params.append(entry_type)

        if search:
            count_query += " AND content LIKE ?"
            count_params.append(f"%{search}%")

        cursor = await db.execute(count_query, count_params)
        total = (await cursor.fetchone())[0]

        return {
            "entries": entries,
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.get("/library/stats")
async def get_library_stats(user_id: int = Depends(get_current_user_id)):
    """
    Get statistics about the content library.
    """
    async with get_db() as db:
        # Count by type
        cursor = await db.execute(
            """
            SELECT entry_type, COUNT(*) as count
            FROM content_library
            WHERE user_id = ?
            GROUP BY entry_type
            """,
            (user_id,)
        )
        type_counts = {row["entry_type"]: row["count"] for row in await cursor.fetchall()}

        # Total count
        cursor = await db.execute(
            "SELECT COUNT(*) FROM content_library WHERE user_id = ?",
            (user_id,)
        )
        total = (await cursor.fetchone())[0]

        # Most used
        cursor = await db.execute(
            """
            SELECT id, content, times_used
            FROM content_library
            WHERE user_id = ?
            ORDER BY times_used DESC
            LIMIT 5
            """,
            (user_id,)
        )
        most_used = [
            {"id": row["id"], "content": row["content"][:100], "times_used": row["times_used"]}
            for row in await cursor.fetchall()
        ]

        return {
            "total_entries": total,
            "by_type": type_counts,
            "most_used": most_used,
        }


@router.post("/generate-from-library", response_model=JobResponse)
async def generate_from_library(
    background_tasks: BackgroundTasks,
    atom_ids: list[int],
    target_persona: str,
    asset_types: list[str] = ["linkedin"],
    asset_quantities: dict[str, int] = {"linkedin": 2},
    user_id: int = Depends(get_current_user_id),
):
    """
    Generate new content using existing library entries.

    Select atoms from the library and generate content without uploading new source material.
    """
    if not atom_ids:
        raise HTTPException(status_code=400, detail="Must provide at least one atom ID")

    async with get_db() as db:
        # Verify atoms exist and get their content
        placeholders = ",".join("?" * len(atom_ids))
        cursor = await db.execute(
            f"""
            SELECT id, entry_type, content, persona_relevance
            FROM content_library
            WHERE id IN ({placeholders}) AND user_id = ?
            """,
            (*atom_ids, user_id)
        )
        atoms = await cursor.fetchall()

        if len(atoms) != len(atom_ids):
            raise HTTPException(status_code=404, detail="Some atoms not found")

        # Create a new job for library generation
        job_id = str(uuid.uuid4())

        # Prepare atom content for the job
        atom_content = []
        for atom in atoms:
            atom_content.append({
                "id": atom["id"],
                "type": atom["entry_type"],
                "content": atom["content"],
                "persona_relevance": json.loads(atom["persona_relevance"]) if atom["persona_relevance"] else {},
            })

        await db.execute(
            """
            INSERT INTO jobs (
                id, user_id, status, original_filename, file_type,
                target_persona, asset_types, asset_quantities,
                processing_mode, current_step, progress, transcript
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                user_id,
                JobStatus.DRAFTING.value,
                "library_generation",
                "library",
                target_persona,
                json.dumps(asset_types),
                json.dumps(asset_quantities),
                "autopilot",
                "Generating from library atoms",
                40,
                json.dumps(atom_content),  # Store atom content as transcript
            )
        )
        await db.commit()

        # Update usage stats for the atoms
        for atom_id in atom_ids:
            await db.execute(
                """
                UPDATE content_library
                SET times_used = times_used + 1, last_used = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (atom_id,)
            )
        await db.commit()

    # Start background processing (skip transcription and atomization)
    from app.services.pipeline import process_job_from_library
    background_tasks.add_task(process_job_from_library, job_id, atom_content)

    return JobResponse(
        job_id=job_id,
        status=JobStatus.DRAFTING,
        message="Generating content from library atoms."
    )


@router.delete("/library/{entry_id}")
async def delete_library_entry(entry_id: int, user_id: int = Depends(get_current_user_id)):
    """
    Delete a library entry.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM content_library WHERE id = ? AND user_id = ?",
            (entry_id, user_id)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Entry not found")

        await db.execute("DELETE FROM content_library WHERE id = ?", (entry_id,))
        await db.commit()

    return {"message": "Entry deleted successfully"}


@router.put("/library/{entry_id}/notes")
async def update_library_notes(entry_id: int, notes: str, user_id: int = Depends(get_current_user_id)):
    """
    Update user notes for a library entry.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM content_library WHERE id = ? AND user_id = ?",
            (entry_id, user_id)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Entry not found")

        await db.execute(
            "UPDATE content_library SET user_notes = ? WHERE id = ?",
            (notes, entry_id)
        )
        await db.commit()

    return {"message": "Notes updated successfully"}
