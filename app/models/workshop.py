"""Pydantic models for Workshop API."""
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class WorkshopOutputListItem(BaseModel):
    """Output item for list view."""
    id: int
    job_id: str
    content_type: str
    status: str
    preview: str
    last_edited: Optional[str] = None
    created_at: str
    # Email sequence specific
    subject: Optional[str] = None
    email_day: Optional[int] = None


class WorkshopOutputList(BaseModel):
    """List of outputs for workshop."""
    outputs: List[WorkshopOutputListItem]
    total: int


class StillPreview(BaseModel):
    """Still preview for sidebar."""
    id: str  # UUID stored as text in database
    still_type: str
    content: str
    source_location: Optional[str] = None


class WorkshopOutputDetail(BaseModel):
    """Full output detail for editing."""
    id: int
    job_id: str
    content_type: str
    status: str
    content: str  # edited_content or step3_final
    original_content: str  # Always step3_final for reference
    last_edited: Optional[str] = None
    created_at: str
    character_count: int
    # Email specific fields
    subject: Optional[str] = None
    email_day: Optional[int] = None
    email_purpose: Optional[str] = None
    sequence_name: Optional[str] = None
    # Source stills from parent job
    stills: List[StillPreview]


class WorkshopContentUpdate(BaseModel):
    """Request body for updating content."""
    content: str


class WorkshopStatusUpdate(BaseModel):
    """Request body for updating status."""
    status: Literal['draft', 'polished', 'published']


class WorkshopUpdateResponse(BaseModel):
    """Response after update."""
    id: int
    status: str
    last_edited: Optional[str] = None
    message: str


class AIEditRequest(BaseModel):
    """Request for AI editing suggestions."""
    content: str = Field(..., min_length=1, max_length=50000)
    prompt: str = Field(..., min_length=1, max_length=500)
    persona_id: Optional[str] = None
    content_type: Optional[str] = None


class AIEditSuggestion(BaseModel):
    """A single AI edit suggestion."""
    id: int
    original_text: str
    suggested_text: str
    explanation: str
    type: str  # grammar, clarity, impact, tone, structure


class AIEditResponse(BaseModel):
    """Response with AI editing suggestions."""
    suggestions: List[AIEditSuggestion]
    summary: str
    cost: float
