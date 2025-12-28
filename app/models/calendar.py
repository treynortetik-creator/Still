"""Pydantic models for content calendar."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ScheduleCreate(BaseModel):
    """Request model for scheduling content."""
    output_id: int
    scheduled_date: str  # YYYY-MM-DD
    scheduled_time: str = "09:00:00"  # HH:MM:SS
    platform: str
    notes: Optional[str] = None


class ScheduleUpdate(BaseModel):
    """Request model for updating a schedule."""
    scheduled_date: Optional[str] = None
    scheduled_time: Optional[str] = None
    platform: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class ScheduleResponse(BaseModel):
    """Response model for a scheduled item."""
    id: int
    output_id: int
    scheduled_date: str
    scheduled_time: str
    platform: str
    status: str
    notes: Optional[str]
    content_preview: str
    content_type: str
    created_at: datetime


class ScheduledItem(BaseModel):
    """Scheduled item with content details for calendar view."""
    id: int
    output_id: int
    platform: str
    scheduled_time: str
    status: str
    content_preview: str
    content_type: str
    notes: Optional[str] = None


class UnscheduledOutput(BaseModel):
    """Output that hasn't been scheduled yet."""
    output_id: int
    content_type: str
    content_preview: str
    job_id: str
    created_at: str


class CalendarDay(BaseModel):
    """A single day with scheduled items."""
    date: str
    items: list[ScheduledItem]


class CalendarView(BaseModel):
    """Calendar view response with scheduled and unscheduled content."""
    start_date: str
    end_date: str
    days: dict[str, list[ScheduledItem]]
    unscheduled: list[UnscheduledOutput]
    total_scheduled: int
    total_unscheduled: int
