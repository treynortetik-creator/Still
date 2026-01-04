"""Pydantic models for the ContentMultiplier application."""
from app.models.job import Job, JobCreate, JobStatus, JobResponse
from app.models.stills import Still, StillCreate, StillType
from app.models.library_entry import LibraryEntry, LibraryEntryCreate
from app.models.brand_context import BrandContext, Persona
from app.models.admin import (
    ApiKeyRequest,
    OpenRouterToggle,
    ModelConfig,
    AIEditorConfigRequest,
    SommelierConfigRequest,
    RefreshSettingsRequest,
    AIModelConfigRequest,
)
from app.models.auth import UserRegister, UserLogin, TokenResponse, UserResponse
from app.models.refresh import (
    BulkRetireRequest,
    BulkExtendReviewRequest,
    MarkPerformerRequest,
    RefreshCounts,
)

__all__ = [
    # Job models
    "Job", "JobCreate", "JobStatus", "JobResponse",
    # Still models
    "Still", "StillCreate", "StillType",
    # Library models
    "LibraryEntry", "LibraryEntryCreate",
    # Brand context models
    "BrandContext", "Persona",
    # Admin models
    "ApiKeyRequest", "OpenRouterToggle", "ModelConfig",
    "AIEditorConfigRequest", "SommelierConfigRequest",
    "RefreshSettingsRequest", "AIModelConfigRequest",
    # Auth models
    "UserRegister", "UserLogin", "TokenResponse", "UserResponse",
    # Refresh models
    "BulkRetireRequest", "BulkExtendReviewRequest",
    "MarkPerformerRequest", "RefreshCounts",
]
