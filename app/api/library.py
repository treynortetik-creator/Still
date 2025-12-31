"""The Reserve (content library) API endpoints."""
import json
import uuid
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall, fetchval, execute_insert_returning_id
from app.models.job import JobResponse, JobStatus
from app.api.auth import get_current_user_id

settings = get_settings()
router = APIRouter()


class CreateStillRequest(BaseModel):
    """Request model for manually creating a still."""
    entry_type: str  # data, insight, story, problem, solution, quote
    content: str
    source: Optional[str] = None
    source_timestamp: Optional[str] = None
    speaker: Optional[str] = None
    tags: Optional[list[str]] = None
    topics: Optional[list[str]] = None
    campaign_name: Optional[str] = None
    user_notes: Optional[str] = None


@router.get("/library")
async def get_library(
    entry_type: Optional[str] = Query(None, description="Filter by entry type"),
    persona: Optional[str] = Query(None, description="Filter by persona relevance"),
    min_relevance: int = Query(1, description="Minimum relevance score (1-5)"),
    search: Optional[str] = Query(None, description="Search in content", max_length=200),
    campaign: Optional[str] = Query(None, description="Filter by campaign name"),
    topic: Optional[str] = Query(None, description="Filter by topic"),
    limit: int = Query(50, description="Number of results", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination", ge=0),
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

        if campaign:
            query += " AND campaign_name = ?"
            params.append(campaign)

        if topic:
            query += " AND topics LIKE ?"
            params.append(f'%"{topic}"%')  # JSON array contains check

        query += " ORDER BY date_added DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await fetchall(db, query, tuple(params))

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
                "campaign_name": row["campaign_name"],
                "topics": json.loads(row["topics"]) if row["topics"] else [],
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

        if campaign:
            count_query += " AND campaign_name = ?"
            count_params.append(campaign)

        if topic:
            count_query += " AND topics LIKE ?"
            count_params.append(f'%"{topic}"%')  # JSON array contains check

        total = await fetchval(db, count_query, tuple(count_params))

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
        type_rows = await fetchall(
            db,
            """
            SELECT entry_type, COUNT(*) as count
            FROM content_library
            WHERE user_id = ?
            GROUP BY entry_type
            """,
            (user_id,)
        )
        type_counts = {row["entry_type"]: row["count"] for row in type_rows}

        # Total count
        total = await fetchval(
            db,
            "SELECT COUNT(*) FROM content_library WHERE user_id = ?",
            (user_id,)
        )

        # Most used
        most_used_rows = await fetchall(
            db,
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
            for row in most_used_rows
        ]

        return {
            "total_entries": total,
            "by_type": type_counts,
            "most_used": most_used,
        }


@router.get("/library/filters")
async def get_library_filters(user_id: int = Depends(get_current_user_id)):
    """
    Get available filter options for campaigns and topics.
    Returns unique campaigns and topics for dropdown population.
    """
    async with get_db() as db:
        # Get unique campaigns
        campaign_rows = await fetchall(
            db,
            """
            SELECT DISTINCT campaign_name
            FROM content_library
            WHERE user_id = ? AND campaign_name IS NOT NULL AND campaign_name != ''
            ORDER BY campaign_name
            """,
            (user_id,)
        )
        campaigns = [row["campaign_name"] for row in campaign_rows]

        # Get unique topics (from JSON arrays)
        topic_rows = await fetchall(
            db,
            """
            SELECT topics FROM content_library
            WHERE user_id = ? AND topics IS NOT NULL AND topics != '[]'
            """,
            (user_id,)
        )

        all_topics = set()
        for row in topic_rows:
            if row["topics"]:
                topics_list = json.loads(row["topics"])
                all_topics.update(topics_list)

        return {
            "campaigns": campaigns,
            "topics": sorted(list(all_topics))
        }


@router.post("/generate-from-library", response_model=JobResponse)
async def generate_from_library(
    background_tasks: BackgroundTasks,
    still_ids: list[int] = None,
    atom_ids: list[int] = None,  # Keep for backwards compatibility
    target_persona: str = None,
    asset_types: list[str] = ["linkedin"],
    asset_quantities: dict[str, int] = {"linkedin": 2},
    user_id: int = Depends(get_current_user_id),
):
    """
    Generate new content using existing Reserve stills.

    Select stills from the Reserve and generate content without uploading new source material.
    """
    # Support both still_ids and atom_ids for backwards compatibility
    ids_to_use = still_ids or atom_ids
    if not ids_to_use:
        raise HTTPException(status_code=400, detail="Must provide at least one still ID")

    async with get_db() as db:
        # Verify stills exist and get their content
        placeholders = ",".join("?" * len(ids_to_use))
        stills = await fetchall(
            db,
            f"""
            SELECT id, entry_type, content, persona_relevance
            FROM content_library
            WHERE id IN ({placeholders}) AND user_id = ?
            """,
            (*ids_to_use, user_id)
        )

        if len(stills) != len(ids_to_use):
            raise HTTPException(status_code=404, detail="Some stills not found")

        # Create a new job for Reserve generation
        job_id = str(uuid.uuid4())

        # Prepare still content for the job
        still_content = []
        for still in stills:
            still_content.append({
                "id": still["id"],
                "type": still["entry_type"],
                "content": still["content"],
                "persona_relevance": json.loads(still["persona_relevance"]) if still["persona_relevance"] else {},
            })

        await execute(
            db,
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
                "reserve_generation",
                "library",
                target_persona,
                json.dumps(asset_types),
                json.dumps(asset_quantities),
                "autopilot",
                "Generating from Reserve stills",
                40,
                json.dumps(still_content),  # Store still content as transcript
            )
        )
        if not settings.use_postgres:
            await db.commit()

        # Update usage stats for the stills
        for still_id in ids_to_use:
            if settings.use_postgres:
                await db.execute(
                    "UPDATE content_library SET times_used = times_used + 1, last_used = NOW() WHERE id = $1",
                    still_id
                )
            else:
                await execute(
                    db,
                    """
                    UPDATE content_library
                    SET times_used = times_used + 1, last_used = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (still_id,)
                )
        if not settings.use_postgres:
            await db.commit()

    # Start background processing (skip transcription and distillation)
    from app.services.pipeline import process_job_from_library
    background_tasks.add_task(process_job_from_library, job_id, still_content)

    return JobResponse(
        job_id=job_id,
        status=JobStatus.DRAFTING,
        message="Generating content from Reserve stills."
    )


@router.delete("/library/{entry_id}")
async def delete_library_entry(entry_id: int, user_id: int = Depends(get_current_user_id)):
    """
    Delete a library entry.
    """
    async with get_db() as db:
        row = await fetchone(
            db,
            "SELECT id FROM content_library WHERE id = ? AND user_id = ?",
            (entry_id, user_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Entry not found")

        await execute(db, "DELETE FROM content_library WHERE id = ?", (entry_id,))
        if not settings.use_postgres:
            await db.commit()

    return {"message": "Entry deleted successfully"}


class BatchDeleteRequest(BaseModel):
    """Request model for batch deleting stills."""
    ids: list[int]


@router.post("/library/batch-delete")
async def batch_delete_library_entries(
    request: BatchDeleteRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Delete multiple library entries at once.
    """
    if not request.ids:
        raise HTTPException(status_code=400, detail="No IDs provided")

    if len(request.ids) > 500:
        raise HTTPException(status_code=400, detail="Maximum 500 entries can be deleted at once")

    async with get_db() as db:
        # Verify ownership of all entries
        placeholders = ",".join("?" * len(request.ids))
        rows = await fetchall(
            db,
            f"SELECT id FROM content_library WHERE id IN ({placeholders}) AND user_id = ?",
            (*request.ids, user_id)
        )

        found_ids = {row["id"] for row in rows}
        requested_ids = set(request.ids)

        if found_ids != requested_ids:
            missing = requested_ids - found_ids
            raise HTTPException(
                status_code=404,
                detail=f"Some entries not found or not owned by user: {list(missing)[:5]}"
            )

        # Delete all entries
        await execute(
            db,
            f"DELETE FROM content_library WHERE id IN ({placeholders}) AND user_id = ?",
            (*request.ids, user_id)
        )
        if not settings.use_postgres:
            await db.commit()

    return {"message": f"Successfully deleted {len(request.ids)} entries", "deleted_count": len(request.ids)}


@router.put("/library/{entry_id}/notes")
async def update_library_notes(entry_id: int, notes: str, user_id: int = Depends(get_current_user_id)):
    """
    Update user notes for a library entry.
    """
    async with get_db() as db:
        row = await fetchone(
            db,
            "SELECT id FROM content_library WHERE id = ? AND user_id = ?",
            (entry_id, user_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Entry not found")

        await execute(
            db,
            "UPDATE content_library SET user_notes = ? WHERE id = ?",
            (notes, entry_id)
        )
        if not settings.use_postgres:
            await db.commit()

    return {"message": "Notes updated successfully"}


@router.post("/library/add")
async def create_library_entry(
    request: CreateStillRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Manually add a still to the Reserve.

    Allows users to create custom stills without going through content processing.
    """
    # Validate entry type
    valid_types = {"data", "insight", "story", "problem", "solution", "quote"}
    if request.entry_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entry type. Must be one of: {', '.join(valid_types)}"
        )

    # Validate content
    if not request.content or not request.content.strip():
        raise HTTPException(status_code=400, detail="Content is required")

    if len(request.content) > 10000:
        raise HTTPException(status_code=400, detail="Content exceeds maximum length of 10,000 characters")

    async with get_db() as db:
        # Insert the new still
        new_id = await execute_insert_returning_id(
            db,
            """
            INSERT INTO content_library (
                user_id, entry_type, content, source, source_timestamp,
                speaker, tags, persona_relevance, times_used, user_notes,
                campaign_name, topics
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                request.entry_type,
                request.content.strip(),
                request.source,
                request.source_timestamp,
                request.speaker,
                json.dumps(request.tags or []),
                json.dumps({"general": 3}),  # Default relevance
                0,
                request.user_notes,
                request.campaign_name,
                json.dumps(request.topics or []),
            )
        )

        if not settings.use_postgres:
            await db.commit()

    return {
        "message": "Still added successfully",
        "id": new_id,
        "entry_type": request.entry_type,
    }


@router.put("/library/{entry_id}")
async def update_library_entry(
    entry_id: int,
    request: CreateStillRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Update a still in the Reserve.
    """
    # Validate entry type
    valid_types = {"data", "insight", "story", "problem", "solution", "quote"}
    if request.entry_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entry type. Must be one of: {', '.join(valid_types)}"
        )

    # Validate content
    if not request.content or not request.content.strip():
        raise HTTPException(status_code=400, detail="Content is required")

    async with get_db() as db:
        # Verify ownership
        row = await fetchone(
            db,
            "SELECT id FROM content_library WHERE id = ? AND user_id = ?",
            (entry_id, user_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Entry not found")

        await execute(
            db,
            """
            UPDATE content_library SET
                entry_type = ?,
                content = ?,
                source = ?,
                source_timestamp = ?,
                speaker = ?,
                tags = ?,
                user_notes = ?,
                campaign_name = ?,
                topics = ?
            WHERE id = ?
            """,
            (
                request.entry_type,
                request.content.strip(),
                request.source,
                request.source_timestamp,
                request.speaker,
                json.dumps(request.tags or []),
                request.user_notes,
                request.campaign_name,
                json.dumps(request.topics or []),
                entry_id,
            )
        )
        if not settings.use_postgres:
            await db.commit()

    return {"message": "Still updated successfully", "id": entry_id}
