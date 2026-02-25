"""API endpoints for Autopilot Monitors."""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional

from app.config import get_settings
from app.api.auth import get_current_user_id
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall
from app.utils.background_tasks import create_background_task

settings = get_settings()
from app.models.autopilot import (
    SourceCreate,
    SourceUpdate,
    SourceResponse,
    SourceListResponse,
    AutopilotItem,
    AutopilotItemListResponse,
    AutopilotStats,
    ManualCheckResponse,
)

router = APIRouter()

VALID_SOURCE_TYPES = {"rss", "podcast", "youtube"}
VALID_CHECK_FREQUENCIES = {"hourly", "daily", "weekly"}
MAX_SOURCE_NAME_LEN = 200
MAX_SOURCE_URL_LEN = 2048


def parse_source_row(row) -> SourceResponse:
    """Convert database row to SourceResponse."""
    asset_types = json.loads(row["asset_types"]) if row["asset_types"] else ["linkedin"]
    return SourceResponse(
        id=row["id"],
        source_type=row["source_type"],
        source_url=row["source_url"],
        source_name=row["source_name"],
        check_frequency=row["check_frequency"],
        is_active=bool(row["is_active"]),
        target_persona=row["target_persona"] or "",
        asset_types=asset_types,
        last_checked=row["last_checked"],
        items_processed=row["items_processed"] or 0,
        error_count=row["error_count"] or 0,
        last_error=row["last_error"],
        created_at=row["created_at"],
    )


@router.post("/autopilot/sources", response_model=SourceResponse)
async def create_source(
    source: SourceCreate,
    user_id: int = Depends(get_current_user_id),
):
    """Add a new monitored source."""
    if source.source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source_type. Must be one of: {', '.join(sorted(VALID_SOURCE_TYPES))}"
        )
    if source.check_frequency not in VALID_CHECK_FREQUENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid check_frequency. Must be one of: {', '.join(sorted(VALID_CHECK_FREQUENCIES))}"
        )
    if not source.source_name or not source.source_name.strip():
        raise HTTPException(status_code=400, detail="source_name is required")
    if len(source.source_name) > MAX_SOURCE_NAME_LEN:
        raise HTTPException(status_code=400, detail=f"source_name must be less than {MAX_SOURCE_NAME_LEN} characters")
    if not source.source_url or not source.source_url.strip():
        raise HTTPException(status_code=400, detail="source_url is required")
    if len(source.source_url) > MAX_SOURCE_URL_LEN:
        raise HTTPException(status_code=400, detail=f"source_url must be less than {MAX_SOURCE_URL_LEN} characters")
    if not source.asset_types:
        raise HTTPException(status_code=400, detail="At least one asset_type is required")

    async with get_db() as db:
        # Check for duplicate URL
        existing = await fetchone(
            db,
            "SELECT id FROM autopilot_sources WHERE user_id = ? AND source_url = ?",
            (user_id, source.source_url),
        )
        if existing:
            raise HTTPException(status_code=400, detail="Source URL already exists")

        # Insert source
        from app.db_utils import execute_insert_returning_id
        source_id = await execute_insert_returning_id(
            db,
            """
            INSERT INTO autopilot_sources
            (user_id, source_type, source_url, source_name, check_frequency, target_persona, asset_types)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                source.source_type,
                source.source_url,
                source.source_name,
                source.check_frequency,
                source.target_persona,
                json.dumps(source.asset_types),
            ),
        )

        row = await fetchone(
            db,
            "SELECT * FROM autopilot_sources WHERE id = ?", (source_id,)
        )

    return parse_source_row(row)


@router.get("/autopilot/sources", response_model=SourceListResponse)
async def list_sources(
    user_id: int = Depends(get_current_user_id),
):
    """List all monitored sources for the user."""
    async with get_db() as db:
        rows = await fetchall(
            db,
            """
            SELECT * FROM autopilot_sources
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )

    sources = [parse_source_row(row) for row in rows]
    return SourceListResponse(sources=sources, total=len(sources))


@router.get("/autopilot/sources/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Get a specific source."""
    async with get_db() as db:
        row = await fetchone(
            db,
            "SELECT * FROM autopilot_sources WHERE id = ? AND user_id = ?",
            (source_id, user_id),
        )

    if not row:
        raise HTTPException(status_code=404, detail="Source not found")

    return parse_source_row(row)


@router.put("/autopilot/sources/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int,
    update: SourceUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """Update a monitored source."""
    if update.check_frequency is not None and update.check_frequency not in VALID_CHECK_FREQUENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid check_frequency. Must be one of: {', '.join(sorted(VALID_CHECK_FREQUENCIES))}"
        )
    if update.source_name is not None and len(update.source_name) > MAX_SOURCE_NAME_LEN:
        raise HTTPException(status_code=400, detail=f"source_name must be less than {MAX_SOURCE_NAME_LEN} characters")
    if update.asset_types is not None and not update.asset_types:
        raise HTTPException(status_code=400, detail="At least one asset_type is required")

    async with get_db() as db:
        # Verify ownership
        existing = await fetchone(
            db,
            "SELECT * FROM autopilot_sources WHERE id = ? AND user_id = ?",
            (source_id, user_id),
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Source not found")

        # Build update query
        updates = []
        params = []

        if update.source_name is not None:
            updates.append("source_name = ?")
            params.append(update.source_name)

        if update.check_frequency is not None:
            updates.append("check_frequency = ?")
            params.append(update.check_frequency)

        if update.target_persona is not None:
            updates.append("target_persona = ?")
            params.append(update.target_persona)

        if update.asset_types is not None:
            updates.append("asset_types = ?")
            params.append(json.dumps(update.asset_types))

        if update.is_active is not None:
            updates.append("is_active = ?")
            params.append(update.is_active)
            # Reset error count when re-enabling
            if update.is_active:
                updates.append("error_count = 0")
                updates.append("last_error = NULL")

        if updates:
            params.append(source_id)
            await execute(
                db,
                f"UPDATE autopilot_sources SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            if not settings.use_postgres:
                await db.commit()

        # Fetch updated source
        row = await fetchone(
            db,
            "SELECT * FROM autopilot_sources WHERE id = ?", (source_id,)
        )

    return parse_source_row(row)


@router.delete("/autopilot/sources/{source_id}")
async def delete_source(
    source_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Delete a monitored source."""
    async with get_db() as db:
        # Verify ownership
        existing = await fetchone(
            db,
            "SELECT id FROM autopilot_sources WHERE id = ? AND user_id = ?",
            (source_id, user_id),
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Source not found")

        # Delete associated items first
        await execute(
            db,
            "DELETE FROM autopilot_items WHERE source_id = ?", (source_id,)
        )

        # Delete source
        await execute(db, "DELETE FROM autopilot_sources WHERE id = ?", (source_id,))
        if not settings.use_postgres:
            await db.commit()

    return {"message": "Source deleted successfully"}


@router.post("/autopilot/sources/{source_id}/check", response_model=ManualCheckResponse)
async def manual_check_source(
    source_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
):
    """Manually trigger a check for a source."""
    async with get_db() as db:
        # Verify ownership
        source = await fetchone(
            db,
            "SELECT id, source_name FROM autopilot_sources WHERE id = ? AND user_id = ?",
            (source_id, user_id),
        )
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

    # Run check
    from app.services.autopilot import check_source

    result = await check_source(source_id)

    if result.get("error"):
        return ManualCheckResponse(
            new_items_found=0,
            message=f"Check failed: {result['error']}",
        )

    new_items = result.get("new_items", 0)
    return ManualCheckResponse(
        new_items_found=new_items,
        message=f"Found {new_items} new item(s)" if new_items else "No new items found",
    )


@router.get("/autopilot/sources/{source_id}/items", response_model=AutopilotItemListResponse)
async def get_source_items(
    source_id: int,
    limit: int = 20,
    offset: int = 0,
    user_id: int = Depends(get_current_user_id),
):
    """Get recent items from a source."""
    limit = max(1, min(limit, 100))
    async with get_db() as db:
        # Verify ownership
        existing = await fetchone(
            db,
            "SELECT id FROM autopilot_sources WHERE id = ? AND user_id = ?",
            (source_id, user_id),
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Source not found")

        # Get total count
        count_row = await fetchone(
            db,
            "SELECT COUNT(*) as count FROM autopilot_items WHERE source_id = ?",
            (source_id,),
        )
        total = count_row["count"] if count_row else 0

        # Get items
        rows = await fetchall(
            db,
            """
            SELECT * FROM autopilot_items
            WHERE source_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (source_id, limit, offset),
        )

    items = [
        AutopilotItem(
            id=row["id"],
            source_id=row["source_id"],
            item_guid=row["item_guid"],
            item_title=row["item_title"],
            item_url=row["item_url"],
            item_published=row["item_published"],
            job_id=row["job_id"],
            processing_status=row["processing_status"],
            created_at=row["created_at"],
        )
        for row in rows
    ]

    return AutopilotItemListResponse(items=items, total=total)


@router.get("/autopilot/stats", response_model=AutopilotStats)
async def get_autopilot_stats(
    user_id: int = Depends(get_current_user_id),
):
    """Get autopilot statistics for the user."""
    async with get_db() as db:
        # Active sources
        row = await fetchone(
            db,
            "SELECT COUNT(*) as count FROM autopilot_sources WHERE user_id = ? AND is_active = ?",
            (user_id, True),
        )
        active_sources = row["count"] if row else 0

        # Pending items
        row = await fetchone(
            db,
            """
            SELECT COUNT(*) as count FROM autopilot_items ai
            JOIN autopilot_sources s ON ai.source_id = s.id
            WHERE s.user_id = ? AND ai.processing_status = 'pending'
            """,
            (user_id,),
        )
        pending_items = row["count"] if row else 0

        # Items processed today
        today_date_expr = "CURRENT_DATE" if settings.use_postgres else "DATE('now')"
        row = await fetchone(
            db,
            f"""
            SELECT COUNT(*) as count FROM autopilot_items ai
            JOIN autopilot_sources s ON ai.source_id = s.id
            WHERE s.user_id = ?
            AND ai.processing_status = 'complete'
            AND DATE(ai.created_at) = {today_date_expr}
            """,
            (user_id,),
        )
        items_today = row["count"] if row else 0

        # Total items processed
        row = await fetchone(
            db,
            """
            SELECT COUNT(*) as count FROM autopilot_items ai
            JOIN autopilot_sources s ON ai.source_id = s.id
            WHERE s.user_id = ? AND ai.processing_status = 'complete'
            """,
            (user_id,),
        )
        items_total = row["count"] if row else 0

        # Sources with errors
        row = await fetchone(
            db,
            "SELECT COUNT(*) as count FROM autopilot_sources WHERE user_id = ? AND error_count > 0",
            (user_id,),
        )
        sources_with_errors = row["count"] if row else 0

    return AutopilotStats(
        active_sources=active_sources,
        pending_items=pending_items,
        items_processed_today=items_today,
        items_processed_total=items_total,
        sources_with_errors=sources_with_errors,
    )


@router.post("/autopilot/items/{item_id}/skip")
async def skip_item(
    item_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Skip processing an autopilot item."""
    async with get_db() as db:
        # Verify ownership
        existing = await fetchone(
            db,
            """
            SELECT ai.id FROM autopilot_items ai
            JOIN autopilot_sources s ON ai.source_id = s.id
            WHERE ai.id = ? AND s.user_id = ?
            """,
            (item_id, user_id),
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Item not found")

        await execute(
            db,
            "UPDATE autopilot_items SET processing_status = 'skipped' WHERE id = ?",
            (item_id,),
        )
        if not settings.use_postgres:
            await db.commit()

    return {"message": "Item skipped"}


@router.post("/autopilot/items/{item_id}/process")
async def process_item(
    item_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Manually trigger processing of an autopilot item."""
    async with get_db() as db:
        # Verify ownership and status
        item = await fetchone(
            db,
            """
            SELECT ai.* FROM autopilot_items ai
            JOIN autopilot_sources s ON ai.source_id = s.id
            WHERE ai.id = ? AND s.user_id = ? AND ai.processing_status IN ('pending', 'skipped', 'failed')
            """,
            (item_id, user_id),
        )
        if not item:
            raise HTTPException(
                status_code=404,
                detail="Item not found or already processed",
            )

        # Reset to pending
        await execute(
            db,
            "UPDATE autopilot_items SET processing_status = 'pending' WHERE id = ?",
            (item_id,),
        )
        if not settings.use_postgres:
            await db.commit()

    # Create job and process
    from app.services.autopilot import create_job_from_feed_item
    from app.services.pipeline import process_job

    job_id = await create_job_from_feed_item(item_id)
    if job_id:
        create_background_task(
            process_job(job_id),
            name=f"autopilot_reprocess_{job_id}"
        )
        return {"message": "Processing started", "job_id": job_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to create job")
