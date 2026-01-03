"""Still-related Pydantic models."""
from datetime import datetime, date
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
    FRAMEWORK = "framework"
    DEFINITION = "definition"
    QUESTION = "question"
    PROOF_POINT = "proof_point"


class StillStatus(str, Enum):
    """Lifecycle status of a still."""
    ACTIVE = "active"
    EVERGREEN = "evergreen"
    NEEDS_REVIEW = "needs_review"
    RETIRED = "retired"


class FunnelStage(str, Enum):
    """Where in the buyer journey this still fits."""
    AWARENESS = "awareness"
    CONSIDERATION = "consideration"
    DECISION = "decision"


class ExpirationType(str, Enum):
    """How this still expires."""
    DATE_BOUND = "date_bound"
    EVENT_BOUND = "event_bound"
    EVERGREEN = "evergreen"


class Performance(str, Enum):
    """Performance rating of a still."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNTESTED = "untested"


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
    # New lifecycle fields
    best_formats: list[str] = []
    funnel_stage: Optional[FunnelStage] = None
    expiration_type: Optional[ExpirationType] = None
    expiration_date: Optional[date] = None


class Still(StillCreate):
    """Full still model with database fields."""
    id: str
    job_id: str
    user_id: int
    created_at: datetime
    usage_count: int = 0  # renamed from times_used
    last_used_at: Optional[datetime] = None  # renamed from last_used
    status: StillStatus = StillStatus.ACTIVE
    performance: Performance = Performance.UNTESTED


class StillResponse(BaseModel):
    """Response model for still queries."""
    stills: list[Still]
    total: int
