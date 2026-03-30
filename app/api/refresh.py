"""Refresh API endpoints for content lifecycle management."""
import csv
import io
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.api.auth import get_current_user_id
from app.database import get_db
from app.db_utils import execute, fetchall, fetchone
from app.models.refresh import (
    BulkRetireRequest,
    BulkExtendReviewRequest,
    MarkPerformerRequest,
    RefreshCounts,
    MergeDuplicatesRequest,
)
from app.services.refresh_tasks import (
    get_stills_needing_attention,
    get_sources_needing_review,
    get_top_performers,
    get_refresh_counts,
    run_refresh_maintenance,
    find_duplicate_stills,
    merge_duplicate_stills,
)

router = APIRouter()


# Endpoints
@router.get("/refresh/counts")
async def get_counts(user_id: int = Depends(get_current_user_id)) -> RefreshCounts:
    """Get notification badge counts."""
    counts = await get_refresh_counts(user_id)
    return RefreshCounts(**counts)


@router.get("/refresh/dashboard")
async def get_dashboard(user_id: int = Depends(get_current_user_id)):
    """Get all dashboard data in one call."""
    sources = await get_sources_needing_review(user_id)
    stills = await get_stills_needing_attention(user_id)
    top_performers = await get_top_performers(user_id)
    counts = await get_refresh_counts(user_id)

    return {
        "sources_needing_review": sources,
        "stills_needing_attention": stills,
        "top_performers": top_performers,
        "counts": counts,
    }


@router.get("/refresh/sources-needing-review")
async def get_sources(user_id: int = Depends(get_current_user_id)):
    """Get sources needing review."""
    return await get_sources_needing_review(user_id)


@router.get("/refresh/stills-needing-attention")
async def get_stills(user_id: int = Depends(get_current_user_id)):
    """Get stills needing attention, grouped by reason."""
    return await get_stills_needing_attention(user_id)


@router.get("/refresh/top-performers")
async def get_performers(
    limit: int = Query(default=10, le=50),
    user_id: int = Depends(get_current_user_id)
):
    """Get top performing stills."""
    return await get_top_performers(user_id, limit)


@router.post("/refresh/run-maintenance")
async def trigger_maintenance(user_id: int = Depends(get_current_user_id)):
    """Manually trigger refresh maintenance."""
    results = await run_refresh_maintenance(user_id)
    return {"success": True, "results": results}


@router.post("/refresh/bulk-retire")
async def bulk_retire(
    request: BulkRetireRequest,
    user_id: int = Depends(get_current_user_id)
):
    """Retire multiple stills at once."""
    if not request.still_ids:
        raise HTTPException(status_code=400, detail="No still IDs provided")

    async with get_db() as db:
        placeholders = ",".join(["?" for _ in request.still_ids])
        await execute(db, f"""
            UPDATE stills
            SET status = 'retired'
            WHERE id IN ({placeholders})
            AND user_id = ?
        """, tuple(request.still_ids) + (user_id,))


    return {"success": True, "retired_count": len(request.still_ids)}


@router.post("/refresh/bulk-extend-review")
async def bulk_extend_review(
    request: BulkExtendReviewRequest,
    user_id: int = Depends(get_current_user_id)
):
    """Extend review dates for multiple sources."""
    if not request.source_ids:
        raise HTTPException(status_code=400, detail="No source IDs provided")

    new_date = (datetime.now() + timedelta(days=request.days)).date()

    async with get_db() as db:
        placeholders = ",".join(["?" for _ in request.source_ids])
        await execute(db, f"""
            UPDATE sources
            SET review_date = ?
            WHERE id IN ({placeholders})
            AND user_id = ?
        """, (new_date,) + tuple(request.source_ids) + (user_id,))


    return {"success": True, "extended_count": len(request.source_ids), "new_date": new_date.isoformat()}


@router.get("/refresh/export-stale")
async def export_stale_csv(user_id: int = Depends(get_current_user_id)):
    """Export stale content as CSV."""
    stills = await get_stills_needing_attention(user_id)

    # Flatten all categories with reason
    rows = []
    for reason, still_list in stills.items():
        for still in still_list:
            rows.append({
                "id": still["id"],
                "content": still["content"][:200] if still.get("content") else "",
                "type": still.get("still_type", ""),
                "status": still.get("status", ""),
                "reason": reason,
                "expiration_date": still.get("expiration_date", ""),
                "usage_count": still.get("usage_count", 0),
                "performance": still.get("performance", ""),
                "source": still.get("source_name", ""),
            })

    # Generate CSV
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=stale_content.csv"}
    )


# Performance tracking endpoints
@router.get("/refresh/stills/{still_id}/outputs")
async def get_still_outputs(
    still_id: str,
    user_id: int = Depends(get_current_user_id)
):
    """Get outputs that used a specific still."""
    async with get_db() as db:
        # Verify still belongs to user
        still = await fetchone(db,
            "SELECT id FROM stills WHERE id = ? AND user_id = ?",
            (still_id, user_id)
        )
        if not still:
            raise HTTPException(status_code=404, detail="Still not found")

        # Find outputs containing this still in stills_used
        rows = await fetchall(db, """
            SELECT o.id, o.content_type, o.created_at, o.status,
                   o.step3_final, o.subject, j.campaign_name
            FROM outputs o
            LEFT JOIN jobs j ON o.job_id = j.id
            WHERE o.stills_used LIKE ?
            ORDER BY o.created_at DESC
            LIMIT 20
        """, (f'%{still_id}%',))

        return [dict(r) for r in rows]


@router.post("/refresh/outputs/{output_id}/mark-performer")
async def mark_output_performer(
    output_id: int,
    request: MarkPerformerRequest,
    user_id: int = Depends(get_current_user_id)
):
    """Mark an output as high performer and update contributing stills."""
    async with get_db() as db:
        # Verify output exists
        output = await fetchone(db,
            "SELECT id, job_id FROM outputs WHERE id = ?",
            (output_id,)
        )
        if not output:
            raise HTTPException(status_code=404, detail="Output not found")

        # Update output status
        await execute(db,
            "UPDATE outputs SET status = 'high_performer' WHERE id = ?",
            (output_id,)
        )

        # Update selected stills to high performance
        if request.still_ids:
            placeholders = ",".join(["?" for _ in request.still_ids])
            await execute(db, f"""
                UPDATE stills
                SET performance = 'high'
                WHERE id IN ({placeholders})
                AND user_id = ?
            """, tuple(request.still_ids) + (user_id,))


    return {"success": True, "stills_updated": len(request.still_ids)}


@router.post("/refresh/find-duplicates")
async def find_duplicates(user_id: int = Depends(get_current_user_id)):
    """Scan for duplicate stills in user's library."""
    return await find_duplicate_stills(user_id)


@router.post("/refresh/merge-duplicates")
async def merge_duplicates(
    request: MergeDuplicatesRequest,
    user_id: int = Depends(get_current_user_id)
):
    """Merge duplicate stills by retiring the loser."""
    result = await merge_duplicate_stills(request.winner_id, request.loser_id, user_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Merge failed"))
    return result
