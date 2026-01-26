"""Output models for generated content."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class OutputCreate(BaseModel):
    """Model for creating an output."""
    job_id: str
    content_type: str
    variation_number: Optional[int] = None
    step1_draft: Optional[str] = None
    step2_edited: Optional[str] = None
    step3_final: Optional[str] = None
    stills_used: list[str] = []
    citations: list[dict] = []
    warnings: list[str] = []


class Output(OutputCreate):
    """Full output model with database fields."""
    id: int
    user_edits: int = 0
    created_at: datetime


class OutputResponse(BaseModel):
    """Response model for job results."""
    job_id: str
    status: str
    outputs: list[Output]
    stills: list[dict]
    cost_incurred: float
