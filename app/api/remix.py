"""Smart Content Remix API endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List

from app.api.auth import get_current_user_id
from app.services.remix import (
    analyze_library_for_remix,
    get_stills_by_topic,
    get_library_stats,
    generate_remix_content,
)

router = APIRouter()


class RemixRequest(BaseModel):
    """Request to generate remixed content."""
    still_ids: List[str]
    content_type: Optional[str] = "linkedin"
    angle: Optional[str] = None


@router.get("/remix/suggestions")
async def get_suggestions(
    user_id: int = Depends(get_current_user_id),
):
    """
    Analyze still library and suggest remix opportunities.

    Returns topic clusters, comparison opportunities, contrarian takes,
    story expansions, and roundup post ideas.
    """
    try:
        suggestions, cost = await analyze_library_for_remix(user_id)

        return {
            "suggestions": suggestions,
            "cost": cost,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/remix/stats")
async def get_stats(
    user_id: int = Depends(get_current_user_id),
):
    """Get library statistics for remix dashboard."""
    stats = await get_library_stats(user_id)
    return stats


@router.get("/remix/search")
async def search_stills(
    topic: str,
    user_id: int = Depends(get_current_user_id),
):
    """Search stills by topic/keyword."""
    if not topic or len(topic) < 2:
        raise HTTPException(status_code=400, detail="Search term must be at least 2 characters")

    stills = await get_stills_by_topic(user_id, topic)

    return {
        "query": topic,
        "results": stills,
        "count": len(stills),
    }


@router.post("/remix/generate")
async def generate_remix(
    data: RemixRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Generate remixed content from selected stills.

    Combines multiple stills into a cohesive piece of content.
    """
    if not data.still_ids or len(data.still_ids) < 1:
        raise HTTPException(status_code=400, detail="At least one still ID is required")

    if len(data.still_ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 stills per remix")

    try:
        content, cost = await generate_remix_content(
            user_id=user_id,
            still_ids=data.still_ids,
            content_type=data.content_type or "linkedin",
            angle=data.angle,
        )

        return {
            "content": content,
            "still_count": len(data.still_ids),
            "content_type": data.content_type,
            "cost": cost,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Remix failed: {str(e)}")
