"""Pydantic models for batch processing."""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class BatchStatus(str, Enum):
    """Status of a batch."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    PARTIAL = "partial"  # Some jobs failed
    FAILED = "failed"


class BatchCreate(BaseModel):
    """Settings applied to all files in batch."""
    target_persona: Optional[str] = None
    asset_types: list[str] = Field(default=["linkedin", "blog"])
    asset_quantities: dict[str, int] = Field(default={"linkedin": 3, "blog": 1})
    campaign_name: Optional[str] = None
    magic_words: Optional[str] = None


class BatchJobStatus(BaseModel):
    """Status of a single job within a batch."""
    job_id: str
    filename: str
    status: str
    progress: int
    current_step: Optional[str] = None
    error_message: Optional[str] = None


class BatchStatusResponse(BaseModel):
    """Response for batch status endpoint."""
    batch_id: str
    status: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    jobs: list[BatchJobStatus]
    created_at: str
    completed_at: Optional[str] = None
    total_cost: float


class BatchResponse(BaseModel):
    """Response for batch creation."""
    batch_id: str
    job_ids: list[str]
    message: str


class BatchListItem(BaseModel):
    """Item in batch list response."""
    batch_id: str
    status: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    created_at: str
    completed_at: Optional[str] = None
    total_cost: float


class BatchListResponse(BaseModel):
    """Response for listing batches."""
    batches: list[BatchListItem]
    total: int
