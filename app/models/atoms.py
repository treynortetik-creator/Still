"""Atom-related Pydantic models."""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class AtomType(str, Enum):
    """Types of content atoms."""
    DATA = "data"
    INSIGHT = "insight"
    STORY = "story"
    PROBLEM = "problem"
    SOLUTION = "solution"


class AtomCreate(BaseModel):
    """Model for creating an atom from atomization."""
    atom_type: AtomType
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


class Atom(AtomCreate):
    """Full atom model with database fields."""
    id: str
    job_id: str
    user_id: int
    created_at: datetime
    times_used: int = 0
    last_used: Optional[datetime] = None


class AtomResponse(BaseModel):
    """Response model for atom queries."""
    atoms: list[Atom]
    total: int
