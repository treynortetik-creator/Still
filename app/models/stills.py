"""Still-related Pydantic models."""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class StillType(str, Enum):
    """Types of content stills."""
    DATA = "data"
    INSIGHT = "insight"
    STORY = "story"
    PROBLEM = "problem"
    SOLUTION = "solution"
    QUOTE = "quote"


class StillCreate(BaseModel):
    """Model for creating a still from distillation."""
    still_type: StillType
    content: str
    source_location: Optional[str] = None
    source_file: Optional[str] = None
    tags: list[str] = []
    persona_relevance: dict[str, int] = Field(
        default={},
        description="Relevance score (1-5) per persona"
    )
    quote_attribution: Optional[str] = None
    why_relevant: Optional[str] = None


class Still(StillCreate):
    """Full still model with database fields."""
    id: str
    job_id: str
    user_id: int
    created_at: datetime
    times_used: int = 0
    last_used: Optional[datetime] = None


class StillResponse(BaseModel):
    """Response model for still queries."""
    stills: list[Still]
    total: int
