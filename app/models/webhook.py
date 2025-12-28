"""Pydantic models for webhooks."""
from typing import Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class WebhookEvent(str, Enum):
    """Webhook trigger events."""
    JOB_COMPLETED = "job_completed"
    CONTENT_GENERATED = "content_generated"
    BATCH_FINISHED = "batch_finished"


class WebhookCreate(BaseModel):
    """Request model for creating a webhook."""
    name: str
    url: str
    trigger_events: list[str]


class WebhookUpdate(BaseModel):
    """Request model for updating a webhook."""
    name: Optional[str] = None
    url: Optional[str] = None
    trigger_events: Optional[list[str]] = None
    is_active: Optional[bool] = None


class WebhookResponse(BaseModel):
    """Response model for a webhook (masks secret for security)."""
    id: int
    name: str
    url: str
    secret_key_preview: str  # Masked version: "whk_****abcd"
    trigger_events: list[str]
    is_active: bool
    created_at: datetime


class WebhookCreateResponse(BaseModel):
    """Response model for webhook creation (shows full secret once)."""
    id: int
    name: str
    url: str
    secret_key: str  # Full secret - only shown on creation!
    trigger_events: list[str]
    is_active: bool
    created_at: datetime
    message: str = "Save this secret key now - it won't be shown again!"


class WebhookListResponse(BaseModel):
    """Response model for listing webhooks."""
    webhooks: list[WebhookResponse]
    total: int


class WebhookPayload(BaseModel):
    """Base webhook payload structure."""
    event: str
    timestamp: str
    webhook_id: int
    data: dict


class JobCompletedPayload(BaseModel):
    """Payload for job_completed event."""
    job_id: str
    user_id: int
    status: str
    original_filename: str
    file_type: str
    target_persona: str
    asset_types: list[str]
    cost_incurred: float
    created_at: str
    completed_at: str


class ContentGeneratedPayload(BaseModel):
    """Payload for content_generated event."""
    job_id: str
    user_id: int
    completed_at: str
    outputs: list[dict]
    atom_count: int


class BatchFinishedPayload(BaseModel):
    """Payload for batch_finished event."""
    batch_id: str
    user_id: int
    status: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_cost: float
    created_at: str
    completed_at: str


class WebhookDeliveryResponse(BaseModel):
    """Response model for webhook delivery status."""
    id: int
    webhook_id: int
    event_type: str
    response_status: Optional[int]
    attempts: int
    created_at: datetime


class WebhookTestResponse(BaseModel):
    """Response for webhook test endpoint."""
    success: bool
    status_code: Optional[int] = None
    message: str
