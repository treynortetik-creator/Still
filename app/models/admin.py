"""Pydantic models for admin API endpoints."""
from typing import Optional
from pydantic import BaseModel


class ApiKeyRequest(BaseModel):
    provider: str
    key: str


class OpenRouterToggle(BaseModel):
    enabled: bool


class ModelConfig(BaseModel):
    transcription: str
    distillation: str  # Frontend uses distillation, aliased to atomization
    distillation_pass2: str
    summarization: str
    drafting: str
    editing: str
    factcheck: str
    workshop_ai_edit: str


class AIEditorConfigRequest(BaseModel):
    """Request model for updating AI editor config."""
    system_prompt: Optional[str] = None
    model: Optional[str] = None


class SommelierConfigRequest(BaseModel):
    """Request model for updating Sommelier config."""
    parse_prompt: Optional[str] = None
    rerank_prompt: Optional[str] = None


class RefreshSettingsRequest(BaseModel):
    """Request model for refresh settings."""
    still_matching_model: Optional[str] = None
    fuzzy_match_high_threshold: Optional[float] = 0.85
    fuzzy_match_low_threshold: Optional[float] = 0.50
    auto_retire_expired: Optional[bool] = True
    expiration_warning_days: Optional[int] = 30


class AIModelConfigRequest(BaseModel):
    """Request model for updating AI model config."""
    model_id: str
    display_name: Optional[str] = None
    cost_per_1k_input: Optional[float] = 0.0
    cost_per_1k_output: Optional[float] = 0.0
    max_tokens: Optional[int] = 4096
    is_active: Optional[bool] = True
