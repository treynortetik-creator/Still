"""Smart Content Remix API endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List

from app.api.auth import get_current_user_id
from app.services.remix import (
    analyze_library_for_remix,
    get_atoms_by_topic,
    get_library_stats,
    generate_remix_content,
)

router = APIRouter()


class RemixRequest(BaseModel):
    """Request to generate remixed content."""
    atom_ids: List[str]
    content_type: Optional[str] = "linkedin"
    angle: Optional[str] = None


@router.get("/remix/suggestions")
async def get_suggestions(
    user_id: int = Depends(get_current_user_id),
):
    """
    Analyze atom library and suggest remix opportunities.

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
async def search_atoms(
    topic: str,
    user_id: int = Depends(get_current_user_id),
):
    """Search atoms by topic/keyword."""
    if not topic or len(topic) < 2:
        raise HTTPException(status_code=400, detail="Search term must be at least 2 characters")

    atoms = await get_atoms_by_topic(user_id, topic)

    return {
        "query": topic,
        "results": atoms,
        "count": len(atoms),
    }


@router.post("/remix/generate")
async def generate_remix(
    data: RemixRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Generate remixed content from selected atoms.

    Combines multiple atoms into a cohesive piece of content.
    """
    if not data.atom_ids or len(data.atom_ids) < 1:
        raise HTTPException(status_code=400, detail="At least one atom ID is required")

    if len(data.atom_ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 atoms per remix")

    try:
        content, cost = await generate_remix_content(
            user_id=user_id,
            atom_ids=data.atom_ids,
            content_type=data.content_type or "linkedin",
            angle=data.angle,
        )

        return {
            "content": content,
            "atom_count": len(data.atom_ids),
            "content_type": data.content_type,
            "cost": cost,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Remix failed: {str(e)}")
