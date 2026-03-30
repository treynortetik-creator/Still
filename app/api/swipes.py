"""Swipe File API endpoints for collecting and managing content examples."""
import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.db_utils import execute, fetchone, fetchall, safe_json
from app.api.auth import get_current_user_id

from app.services.swipe_analyzer import (
    analyze_swipe_collection,
    get_style_dna,
    analyze_single_swipe,
)

router = APIRouter()


class SwipeCreate(BaseModel):
    """Request to create a new swipe file entry."""
    content: str
    source_url: Optional[str] = None
    source_type: Optional[str] = "general"  # linkedin, twitter, email, blog, general
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class SwipeUpdate(BaseModel):
    """Request to update a swipe file entry."""
    content: Optional[str] = None
    source_url: Optional[str] = None
    source_type: Optional[str] = None
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


@router.get("/swipes")
async def list_swipes(
    source_type: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user_id: int = Depends(get_current_user_id),
):
    """List all swipe files for the current user."""
    async with get_db() as db:
        # Build query with optional filters
        query = "SELECT * FROM swipe_files WHERE user_id = ?"
        params = [user_id]

        if source_type:
            query += " AND source_type = ?"
            params.append(source_type)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await fetchall(db, query, tuple(params))

        swipes = []
        for row in rows:
            swipe = {
                "id": row["id"],
                "content": row["content"],
                "source_url": row["source_url"],
                "source_type": row["source_type"],
                "title": row["title"],
                "tags": safe_json(row["tags"], []),
                "notes": row["notes"],
                "created_at": row["created_at"],
            }

            # Filter by tag if specified
            if tag and tag not in swipe["tags"]:
                continue

            swipes.append(swipe)

        # Get total count
        count_row = await fetchone(
            db,
            "SELECT COUNT(*) as count FROM swipe_files WHERE user_id = ?",
            (user_id,)
        )
        total = count_row["count"]

        return {
            "swipes": swipes,
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.post("/swipes")
async def create_swipe(
    data: SwipeCreate,
    user_id: int = Depends(get_current_user_id),
):
    """Create a new swipe file entry."""
    if not data.content or len(data.content.strip()) < 10:
        raise HTTPException(status_code=400, detail="Content must be at least 10 characters")

    async with get_db() as db:
        row = await db.fetchrow(
            """
            INSERT INTO swipe_files (user_id, content, source_url, source_type, title, tags, notes)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            user_id,
            data.content.strip(),
            data.source_url,
            data.source_type or "general",
            data.title,
            json.dumps(data.tags) if data.tags else None,
            data.notes,
        )
        swipe_id = row["id"]

        return {
            "id": swipe_id,
            "message": "Swipe file created successfully",
        }


@router.get("/swipes/{swipe_id}")
async def get_swipe(
    swipe_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Get a specific swipe file entry."""
    async with get_db() as db:
        row = await fetchone(
            db,
            "SELECT * FROM swipe_files WHERE id = ? AND user_id = ?",
            (swipe_id, user_id)
        )

        if not row:
            raise HTTPException(status_code=404, detail="Swipe not found")

        return {
            "id": row["id"],
            "content": row["content"],
            "source_url": row["source_url"],
            "source_type": row["source_type"],
            "title": row["title"],
            "tags": safe_json(row["tags"], []),
            "notes": row["notes"],
            "created_at": row["created_at"],
        }


@router.put("/swipes/{swipe_id}")
async def update_swipe(
    swipe_id: int,
    data: SwipeUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """Update a swipe file entry."""
    async with get_db() as db:
        # Check ownership
        existing = await fetchone(
            db,
            "SELECT id FROM swipe_files WHERE id = ? AND user_id = ?",
            (swipe_id, user_id)
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Swipe not found")

        # Build update query dynamically
        updates = []
        params = []

        if data.content is not None:
            updates.append("content = ?")
            params.append(data.content.strip())
        if data.source_url is not None:
            updates.append("source_url = ?")
            params.append(data.source_url)
        if data.source_type is not None:
            updates.append("source_type = ?")
            params.append(data.source_type)
        if data.title is not None:
            updates.append("title = ?")
            params.append(data.title)
        if data.tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(data.tags))
        if data.notes is not None:
            updates.append("notes = ?")
            params.append(data.notes)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(swipe_id)
        await execute(
            db,
            f"UPDATE swipe_files SET {', '.join(updates)} WHERE id = ?",
            tuple(params)
        )

        return {"message": "Swipe updated successfully"}


@router.delete("/swipes/{swipe_id}")
async def delete_swipe(
    swipe_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Delete a swipe file entry."""
    async with get_db() as db:
        result = await execute(
            db,
            "DELETE FROM swipe_files WHERE id = ? AND user_id = ?",
            (swipe_id, user_id)
        )

        # Check if any rows were affected
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Swipe not found")

        return {"message": "Swipe deleted successfully"}


@router.get("/swipes/stats/summary")
async def get_swipe_stats(
    user_id: int = Depends(get_current_user_id),
):
    """Get statistics about user's swipe collection."""
    async with get_db() as db:
        # Total count
        count_row = await fetchone(
            db,
            "SELECT COUNT(*) as count FROM swipe_files WHERE user_id = ?",
            (user_id,)
        )
        total = count_row["count"]

        # Count by source type
        type_rows = await fetchall(
            db,
            """
            SELECT source_type, COUNT(*) as count
            FROM swipe_files
            WHERE user_id = ?
            GROUP BY source_type
            """,
            (user_id,)
        )
        by_type = {row["source_type"]: row["count"] for row in type_rows}

        # Get all tags and count occurrences
        tag_rows = await fetchall(
            db,
            "SELECT tags FROM swipe_files WHERE user_id = ? AND tags IS NOT NULL",
            (user_id,)
        )
        tag_counts = {}
        for row in tag_rows:
            tags = safe_json(row["tags"], [])
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Sort tags by count
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total_swipes": total,
            "by_source_type": by_type,
            "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
        }


@router.get("/swipes/analysis")
async def get_analysis(
    user_id: int = Depends(get_current_user_id),
):
    """Get the user's Style DNA analysis."""
    analysis = await get_style_dna(user_id)

    if not analysis:
        return {"analysis": None, "message": "No analysis yet. Add at least 3 swipes and run analysis."}

    return {"analysis": analysis}


@router.post("/swipes/analyze")
async def run_analysis(
    user_id: int = Depends(get_current_user_id),
):
    """
    Analyze the user's swipe collection to extract Style DNA.

    Requires at least 3 swipes.
    """
    try:
        result, cost = await analyze_swipe_collection(user_id, min_swipes=3)

        return {
            "analysis": result,
            "cost": cost,
            "message": "Style DNA analysis complete"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


class SingleSwipeAnalysis(BaseModel):
    """Request to analyze a single swipe."""
    content: str


@router.post("/swipes/analyze-single")
async def analyze_single(
    data: SingleSwipeAnalysis,
    user_id: int = Depends(get_current_user_id),
):
    """
    Analyze a single piece of content for quick insights.

    Useful for understanding what makes a specific piece effective.
    """
    if not data.content or len(data.content.strip()) < 20:
        raise HTTPException(status_code=400, detail="Content must be at least 20 characters")

    try:
        result, cost = await analyze_single_swipe(data.content, user_id)

        return {
            "analysis": result,
            "cost": cost,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
