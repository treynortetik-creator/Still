"""Pydantic models for Autopilot Monitors."""
from typing import Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class SourceType(str, Enum):
    """Types of sources that can be monitored."""
    RSS = "rss"
    PODCAST = "podcast"
    YOUTUBE = "youtube"


class CheckFrequency(str, Enum):
    """How often to check for new content."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class ProcessingStatus(str, Enum):
    """Status of a feed item being processed."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceCreate(BaseModel):
    """Request model for creating a monitored source."""
    source_type: str
    source_url: str
    source_name: str
    check_frequency: str = "daily"
    target_persona: Optional[str] = None
    asset_types: list[str] = ["linkedin"]


class SourceUpdate(BaseModel):
    """Request model for updating a source."""
    source_name: Optional[str] = None
    check_frequency: Optional[str] = None
    target_persona: Optional[str] = None
    asset_types: Optional[list[str]] = None
    is_active: Optional[bool] = None


class SourceResponse(BaseModel):
    """Response model for a monitored source."""
    id: int
    source_type: str
    source_url: str
    source_name: str
    check_frequency: str
    is_active: bool
    target_persona: Optional[str] = None
    asset_types: list[str]
    last_checked: Optional[datetime]
    items_processed: int
    error_count: int
    last_error: Optional[str]
    created_at: datetime


class SourceListResponse(BaseModel):
    """Response for listing sources."""
    sources: list[SourceResponse]
    total: int


class AutopilotItem(BaseModel):
    """A single item found in a monitored feed."""
    id: int
    source_id: int
    item_guid: str
    item_title: Optional[str]
    item_url: str
    item_published: Optional[datetime]
    job_id: Optional[str]
    processing_status: str
    created_at: datetime


class AutopilotItemListResponse(BaseModel):
    """Response for listing feed items."""
    items: list[AutopilotItem]
    total: int


class AutopilotStats(BaseModel):
    """Autopilot statistics for user."""
    active_sources: int
    pending_items: int
    items_processed_today: int
    items_processed_total: int
    sources_with_errors: int


class ManualCheckResponse(BaseModel):
    """Response from manually checking a source."""
    new_items_found: int
    message: str
