"""The Sommelier - AI-powered semantic search API endpoints."""
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from pydantic import BaseModel
from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.auth import get_current_user_id
from app.services.sommelier import search_stills, get_example_queries

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class SommelierSearchRequest(BaseModel):
    """Request model for Sommelier search."""
    query: str
    limit: int = 10


class SommelierSearchResponse(BaseModel):
    """Response model for Sommelier search."""
    results: list[dict]
    query_understood: str
    example_queries: list[str]
    cost: float


@router.post("/sommelier/search", response_model=SommelierSearchResponse)
@limiter.limit("30/hour")
async def sommelier_search(
    request: Request,
    search_request: SommelierSearchRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Ask the Sommelier to find relevant stills from your Reserve.

    Uses AI to understand your query, search semantically, and rank results
    by relevance with explanations.
    """
    if not search_request.query or len(search_request.query.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Query must be at least 3 characters"
        )

    try:
        results, query_understood, cost = await search_stills(
            query=search_request.query,
            user_id=user_id,
            limit=min(search_request.limit, 20),  # Max 20 results
        )

        examples = await get_example_queries()

        return SommelierSearchResponse(
            results=results,
            query_understood=query_understood,
            example_queries=examples,
            cost=round(cost, 4),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/sommelier/examples")
async def get_examples(user_id: int = Depends(get_current_user_id)):
    """Get example queries for the Sommelier."""
    examples = await get_example_queries()
    return {"examples": examples}
