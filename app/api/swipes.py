"""Swipe File API endpoints for collecting and managing content examples."""
import json
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall
from app.api.auth import get_current_user_id
from app.rate_limiter import limiter

settings = get_settings()
from app.services.swipe_analyzer import (
    analyze_swipe_collection,
    get_style_dna,
    analyze_single_swipe,
)

router = APIRouter()

VALID_SOURCE_TYPES = {"linkedin", "twitter", "email", "blog", "general"}
MAX_SWIPE_CONTENT = 50_000
MAX_SWIPE_TITLE = 200
MAX_SWIPE_NOTES = 2_000
MAX_SWIPE_TAGS = 20
MAX_TAG_LENGTH = 50


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
    limit = max(1, min(limit, 200))
    async with get_db() as db:
        # Build query with optional filters
        query = "SELECT * FROM swipe_files WHERE user_id = ?"
        count_query = "SELECT COUNT(*) as count FROM swipe_files WHERE user_id = ?"
        params: list = [user_id]
        count_params: list = [user_id]

        if source_type:
            query += " AND source_type = ?"
            count_query += " AND source_type = ?"
            params.append(source_type)
            count_params.append(source_type)

        # Filter by tag in the database using JSON array contains check
        if tag:
            if settings.use_postgres:
                # Use @> (contains) operator so db_utils ? placeholder conversion doesn't
                # collide with the JSONB ? (key-exists) operator
                query += " AND tags::jsonb @> ?::jsonb"
                count_query += " AND tags::jsonb @> ?::jsonb"
                import json as _json
                params.append(_json.dumps([tag]))
                count_params.append(_json.dumps([tag]))
            else:
                query += " AND json_extract(tags, '$') LIKE ?"
                count_query += " AND json_extract(tags, '$') LIKE ?"
                tag_like = f'%"{tag}"%'
                params.append(tag_like)
                count_params.append(tag_like)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await fetchall(db, query, tuple(params))

        swipes = [
            {
                "id": row["id"],
                "content": row["content"],
                "source_url": row["source_url"],
                "source_type": row["source_type"],
                "title": row["title"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "notes": row["notes"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

        # Get total count (respects all filters including tag)
        count_row = await fetchone(db, count_query, tuple(count_params))
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

    if len(data.content) > MAX_SWIPE_CONTENT:
        raise HTTPException(status_code=400, detail=f"Content must be less than {MAX_SWIPE_CONTENT:,} characters")

    if data.source_type and data.source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid source_type. Must be one of: {', '.join(sorted(VALID_SOURCE_TYPES))}")

    if data.title and len(data.title) > MAX_SWIPE_TITLE:
        raise HTTPException(status_code=400, detail=f"Title must be less than {MAX_SWIPE_TITLE} characters")

    if data.notes and len(data.notes) > MAX_SWIPE_NOTES:
        raise HTTPException(status_code=400, detail=f"Notes must be less than {MAX_SWIPE_NOTES} characters")

    if data.tags:
        if len(data.tags) > MAX_SWIPE_TAGS:
            raise HTTPException(status_code=400, detail=f"Maximum {MAX_SWIPE_TAGS} tags allowed")
        for t in data.tags:
            if len(t) > MAX_TAG_LENGTH:
                raise HTTPException(status_code=400, detail=f"Each tag must be less than {MAX_TAG_LENGTH} characters")

    async with get_db() as db:
        if settings.use_postgres:
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
        else:
            cursor = await db.execute(
                """
                INSERT INTO swipe_files (user_id, content, source_url, source_type, title, tags, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    data.content.strip(),
                    data.source_url,
                    data.source_type or "general",
                    data.title,
                    json.dumps(data.tags) if data.tags else None,
                    data.notes,
                )
            )
            await db.commit()
            swipe_id = cursor.lastrowid

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
            "tags": json.loads(row["tags"]) if row["tags"] else [],
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
    if data.content is not None:
        if len(data.content.strip()) < 10:
            raise HTTPException(status_code=400, detail="Content must be at least 10 characters")
        if len(data.content) > MAX_SWIPE_CONTENT:
            raise HTTPException(status_code=400, detail=f"Content must be less than {MAX_SWIPE_CONTENT:,} characters")

    if data.source_type is not None and data.source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid source_type. Must be one of: {', '.join(sorted(VALID_SOURCE_TYPES))}")

    if data.title is not None and len(data.title) > MAX_SWIPE_TITLE:
        raise HTTPException(status_code=400, detail=f"Title must be less than {MAX_SWIPE_TITLE} characters")

    if data.notes is not None and len(data.notes) > MAX_SWIPE_NOTES:
        raise HTTPException(status_code=400, detail=f"Notes must be less than {MAX_SWIPE_NOTES} characters")

    if data.tags is not None:
        if len(data.tags) > MAX_SWIPE_TAGS:
            raise HTTPException(status_code=400, detail=f"Maximum {MAX_SWIPE_TAGS} tags allowed")
        for t in data.tags:
            if len(t) > MAX_TAG_LENGTH:
                raise HTTPException(status_code=400, detail=f"Each tag must be less than {MAX_TAG_LENGTH} characters")

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
        if not settings.use_postgres:
            await db.commit()

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
        if not settings.use_postgres:
            await db.commit()

        # Check if any rows were affected
        if settings.use_postgres:
            # PostgreSQL returns command tag like "DELETE 1"
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="Swipe not found")
        else:
            if result == 0:
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
            tags = json.loads(row["tags"]) if row["tags"] else []
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
@limiter.limit("10/hour")
async def run_analysis(
    request: Request,
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
@limiter.limit("20/hour")
async def analyze_single(
    request: Request,
    data: SingleSwipeAnalysis,
    user_id: int = Depends(get_current_user_id),
):
    """
    Analyze a single piece of content for quick insights.

    Useful for understanding what makes a specific piece effective.
    """
    if not data.content or len(data.content.strip()) < 20:
        raise HTTPException(status_code=400, detail="Content must be at least 20 characters")

    if len(data.content) > MAX_SWIPE_CONTENT:
        raise HTTPException(status_code=400, detail=f"Content must be less than {MAX_SWIPE_CONTENT:,} characters")

    try:
        result, cost = await analyze_single_swipe(data.content, user_id)

        return {
            "analysis": result,
            "cost": cost,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
