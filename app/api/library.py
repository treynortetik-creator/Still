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


class GenerateFromLibraryRequest(BaseModel):
    """Request model for generating content from Reserve stills."""
    still_ids: Optional[list[int]] = None
    atom_ids: Optional[list[int]] = None  # Backwards compatibility
    target_persona: Optional[str] = None
    asset_types: list[str] = ["linkedin"]
    asset_quantities: dict[str, int] = {"linkedin": 2}


@router.get("/library")
async def get_library(
    entry_type: Optional[str] = Query(None, description="Filter by entry type"),
    persona: Optional[str] = Query(None, description="Filter by persona relevance"),
    min_relevance: int = Query(1, description="Minimum relevance score (1-5)"),
    search: Optional[str] = Query(None, description="Search in content", max_length=200),
    campaign: Optional[str] = Query(None, description="Filter by campaign name"),
    topic: Optional[str] = Query(None, description="Filter by topic"),
    job_id: Optional[str] = Query(None, description="Filter by source job ID"),
    status: Optional[str] = Query(None, description="Filter by status (active, evergreen, needs_review, retired)"),
    funnel_stage: Optional[str] = Query(None, description="Filter by funnel stage (awareness, consideration, decision)"),
    sort_by: str = Query("newest", description="Sort order: newest, oldest, most_used, never_used, expiring_soon"),
    limit: int = Query(50, description="Number of results", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination", ge=0),
    user_id: int = Depends(get_current_user_id),
):
    """
    Get content library entries with filtering and sorting.

    Supports lifecycle filters (status, funnel_stage) and sorting options:
    - newest: Most recently added first (default)
    - oldest: Oldest first
    - most_used: Most frequently used first
    - never_used: Only entries never used, newest first
    - expiring_soon: Entries with expiration dates, soonest first
    """
    # Validate status filter
    if status:
        valid_statuses = {"active", "evergreen", "needs_review", "retired"}
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}"
            )

    # Validate funnel_stage filter
    if funnel_stage:
        valid_stages = {"awareness", "consideration", "decision"}
        if funnel_stage not in valid_stages:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid funnel_stage. Must be one of: {', '.join(sorted(valid_stages))}"
            )

    # Validate sort_by
    valid_sort_options = {"newest", "oldest", "most_used", "never_used", "expiring_soon"}
    if sort_by not in valid_sort_options:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by. Must be one of: {', '.join(sorted(valid_sort_options))}"
        )

    async with get_db() as db:
        # Build query with LEFT JOIN to get source file name from jobs table
        # Also join with sources table to get SOT info (source_id, is_approved)
        query = """
            SELECT cl.*, j.original_filename as source_file,
                   s.id as source_id, s.is_approved as source_approved
            FROM content_library cl
            LEFT JOIN jobs j ON cl.job_id = j.id
            LEFT JOIN sources s ON j.id = s.job_id
            WHERE cl.user_id = ?
        """
        params = [user_id]

        if entry_type:
            query += " AND cl.entry_type = ?"
            params.append(entry_type)

        if search:
            query += " AND cl.content LIKE ?"
            params.append(f"%{search}%")

        if campaign:
            query += " AND cl.campaign_name = ?"
            params.append(campaign)

        if topic:
            query += " AND cl.topics LIKE ?"
            params.append(f'%"{topic}"%')  # JSON array contains check

        if job_id:
            query += " AND cl.job_id = ?"
            params.append(job_id)

        # Lifecycle filters
        if status:
            query += " AND cl.status = ?"
            params.append(status)

        if funnel_stage:
            query += " AND cl.funnel_stage = ?"
            params.append(funnel_stage)

        # Handle sort_by with special filters for some options
        if sort_by == "never_used":
            query += " AND (cl.times_used = 0 OR cl.times_used IS NULL)"
            order_clause = "ORDER BY cl.date_added DESC"
        elif sort_by == "expiring_soon":
            query += " AND cl.expiration_date IS NOT NULL"
            order_clause = "ORDER BY cl.expiration_date ASC"
        elif sort_by == "oldest":
            order_clause = "ORDER BY cl.date_added ASC"
        elif sort_by == "most_used":
            order_clause = "ORDER BY COALESCE(cl.times_used, 0) DESC, cl.date_added DESC"
        else:  # newest (default)
            order_clause = "ORDER BY cl.date_added DESC"

        query += f" {order_clause} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await fetchall(db, query, tuple(params))

        entries = []
        for row in rows:
            persona_relevance = json.loads(row["persona_relevance"]) if row["persona_relevance"] else {}

            # Filter by persona relevance if specified
            if persona and persona in persona_relevance:
                if persona_relevance[persona] < min_relevance:
                    continue

            # Handle best_formats - it's a TEXT[] in PostgreSQL, may need conversion
            best_formats = row.get("best_formats")
            if best_formats is None:
                best_formats = []
            elif isinstance(best_formats, str):
                # SQLite returns JSON string
                try:
                    best_formats = json.loads(best_formats)
                except (json.JSONDecodeError, TypeError):
                    best_formats = []
            # PostgreSQL returns list directly, so no conversion needed

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
                "times_used": row["times_used"] or 0,
                "last_used": row["last_used"],
                "user_notes": row["user_notes"],
                "campaign_name": row["campaign_name"],
                "topics": json.loads(row["topics"]) if row["topics"] else [],
                "source_file": row.get("source_file"),
                "job_id": row.get("job_id"),
                # SOT (Source of Truth) fields
                "source_id": row.get("source_id"),
                "source_approved": row.get("source_approved"),
                # Lifecycle fields
                "status": row.get("status") or "active",
                "best_formats": best_formats,
                "funnel_stage": row.get("funnel_stage"),
                "expiration_type": row.get("expiration_type"),
                "expiration_date": str(row["expiration_date"]) if row.get("expiration_date") else None,
                "performance": row.get("performance") or "untested",
            })

        # Get total count (must match the same filters)
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

        if job_id:
            count_query += " AND job_id = ?"
            count_params.append(job_id)

        # Include lifecycle filters in count
        if status:
            count_query += " AND status = ?"
            count_params.append(status)

        if funnel_stage:
            count_query += " AND funnel_stage = ?"
            count_params.append(funnel_stage)

        # Include sort_by filters that affect result set
        if sort_by == "never_used":
            count_query += " AND (times_used = 0 OR times_used IS NULL)"
        elif sort_by == "expiring_soon":
            count_query += " AND expiration_date IS NOT NULL"

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


@router.get("/library/sources")
async def get_library_sources(user_id: int = Depends(get_current_user_id)):
    """
    Get list of unique sources (jobs) for user's stills.
    Returns job_id and original_filename for populating source filter dropdown.
    """
    async with get_db() as db:
        rows = await fetchall(
            db,
            """
            SELECT DISTINCT cl.job_id, j.original_filename as source_file
            FROM content_library cl
            LEFT JOIN jobs j ON cl.job_id = j.id
            WHERE cl.user_id = ? AND cl.job_id IS NOT NULL
            ORDER BY j.original_filename
            """,
            (user_id,)
        )

        return {
            "sources": [
                {"job_id": row["job_id"], "source_file": row.get("source_file")}
                for row in rows
            ]
        }


@router.post("/generate-from-library", response_model=JobResponse)
async def generate_from_library(
    request: GenerateFromLibraryRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
):
    """
    Generate new content using existing Reserve stills.

    Select stills from the Reserve and generate content without uploading new source material.
    """
    # Support both still_ids and atom_ids for backwards compatibility
    ids_to_use = request.still_ids or request.atom_ids
    target_persona = request.target_persona
    asset_types = request.asset_types
    asset_quantities = request.asset_quantities
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


class PatchStillRequest(BaseModel):
    """Request model for partial still updates."""
    status: Optional[str] = None
    performance: Optional[str] = None
    funnel_stage: Optional[str] = None
    expiration_date: Optional[str] = None
    expiration_type: Optional[str] = None
    user_notes: Optional[str] = None


@router.patch("/library/{entry_id}")
async def patch_library_entry(
    entry_id: int,
    request: PatchStillRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Partially update a still in the Reserve.

    Allows updating individual fields like status, performance, funnel_stage,
    expiration settings, etc. without providing the full entry.
    """
    # Validate status if provided
    if request.status:
        valid_statuses = {"active", "evergreen", "needs_review", "retired"}
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}"
            )

    # Validate performance if provided
    if request.performance:
        valid_performance = {"low", "medium", "high"}
        if request.performance not in valid_performance:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid performance. Must be one of: {', '.join(sorted(valid_performance))}"
            )

    # Validate funnel_stage if provided
    if request.funnel_stage:
        valid_stages = {"awareness", "consideration", "decision"}
        if request.funnel_stage not in valid_stages:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid funnel_stage. Must be one of: {', '.join(sorted(valid_stages))}"
            )

    # Validate expiration_type if provided
    if request.expiration_type:
        valid_exp_types = {"evergreen", "date_bound", "event_bound"}
        if request.expiration_type not in valid_exp_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid expiration_type. Must be one of: {', '.join(sorted(valid_exp_types))}"
            )

    async with get_db() as db:
        # Verify ownership
        row = await fetchone(
            db,
            "SELECT id FROM content_library WHERE id = ? AND user_id = ?",
            (entry_id, user_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Entry not found")

        # Build dynamic update query
        updates = []
        params = []

        if request.status is not None:
            updates.append("status = ?")
            params.append(request.status)

        if request.performance is not None:
            updates.append("performance = ?")
            params.append(request.performance if request.performance else None)

        if request.funnel_stage is not None:
            updates.append("funnel_stage = ?")
            params.append(request.funnel_stage)

        if request.expiration_date is not None:
            updates.append("expiration_date = ?")
            params.append(request.expiration_date if request.expiration_date else None)

        if request.expiration_type is not None:
            updates.append("expiration_type = ?")
            params.append(request.expiration_type)

        if request.user_notes is not None:
            updates.append("user_notes = ?")
            params.append(request.user_notes)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(entry_id)
        query = f"UPDATE content_library SET {', '.join(updates)} WHERE id = ?"

        await execute(db, query, tuple(params))
        if not settings.use_postgres:
            await db.commit()

    return {"message": "Still updated successfully", "id": entry_id}


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
