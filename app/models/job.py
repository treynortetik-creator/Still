"""Job-related Pydantic models."""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job processing status."""
    UPLOADING = "uploading"
    TRANSCRIBING = "transcribing"
    CLEANING = "cleaning"
    ANALYZING = "analyzing"
    AWAITING_APPROVAL = "awaiting_approval"
    DISTILLING = "distilling"
    DRAFTING = "drafting"
    EDITING = "editing"
    FACTCHECKING = "factchecking"
    COMPLETE = "complete"
    FAILED = "failed"


class JobCreate(BaseModel):
    """Request model for creating a new job."""
    target_persona: Optional[str] = Field(default=None, description="ID of the target persona (optional)")
    asset_types: list[str] = Field(
        default=["linkedin"],
        description="Types of assets to generate (linkedin, blog, email)"
    )
    asset_quantities: dict[str, int] = Field(
        default={"linkedin": 3, "blog": 1},
        description="Number of each asset type to generate"
    )
    processing_mode: str = Field(
        default="autopilot",
        description="Processing mode (autopilot for MVP)"
    )
    campaign_name: Optional[str] = Field(
        default=None,
        description="Optional name for this campaign"
    )


class Job(BaseModel):
    """Full job model."""
    id: str
    user_id: int
    status: JobStatus
    original_filename: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    target_persona: Optional[str] = None
    asset_types: list[str] = []
    asset_quantities: dict[str, int] = {}
    processing_mode: str = "autopilot"
    campaign_name: Optional[str] = None
    current_step: Optional[str] = None
    progress: int = 0
    transcript: Optional[str] = None
    cleaned_transcript: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    cost_incurred: float = 0.0


class JobStatusResponse(BaseModel):
    """Response model for job status endpoint."""
    job_id: str
    status: JobStatus
    current_step: Optional[str] = None
    progress: int = 0
    estimated_time_remaining: Optional[str] = None
    error_message: Optional[str] = None


class JobResponse(BaseModel):
    """Response model for job creation."""
    job_id: str
    status: JobStatus
    message: str = "Job created successfully"
