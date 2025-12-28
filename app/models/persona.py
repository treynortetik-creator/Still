"""Pydantic models for custom personas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ContentPreferencesModel(BaseModel):
    """Content preferences for a persona."""
    length: Optional[str] = Field(default="Medium", description="Preferred content length")
    data_density: Optional[str] = Field(default="Moderate", description="How data-heavy content should be")
    tone: Optional[str] = Field(default="Professional", description="Content tone")


class TonePreferencesModel(BaseModel):
    """Tone preferences for a persona."""
    formality: Optional[str] = Field(default="Professional", description="Level of formality")
    emotion: Optional[str] = Field(default="Neutral", description="Emotional tone")
    style: Optional[str] = Field(default="Clear and direct", description="Writing style")


class PersonaCreate(BaseModel):
    """Request model for creating a custom persona."""
    name: str = Field(..., min_length=1, max_length=100, description="Persona name")
    role: str = Field(..., min_length=1, max_length=200, description="Job title/role")
    industry: Optional[str] = Field(default=None, max_length=100, description="Industry")
    pain_points: list[str] = Field(..., min_length=1, max_length=10, description="Key challenges/pain points")
    goals: list[str] = Field(..., min_length=1, max_length=10, description="Goals/priorities")
    tone_preferences: Optional[TonePreferencesModel] = Field(default=None, description="Tone preferences")
    content_preferences: Optional[ContentPreferencesModel] = Field(default=None, description="Content preferences")


class PersonaUpdate(BaseModel):
    """Request model for updating a persona."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    role: Optional[str] = Field(default=None, min_length=1, max_length=200)
    industry: Optional[str] = Field(default=None, max_length=100)
    pain_points: Optional[list[str]] = Field(default=None, max_length=10)
    goals: Optional[list[str]] = Field(default=None, max_length=10)
    tone_preferences: Optional[TonePreferencesModel] = None
    content_preferences: Optional[ContentPreferencesModel] = None


class PersonaResponse(BaseModel):
    """Response model for a persona."""
    id: str
    user_id: int
    name: str
    role: str
    industry: Optional[str] = None
    pain_points: list[str]
    goals: list[str]
    tone_preferences: Optional[dict] = None
    content_preferences: Optional[dict] = None
    is_default: bool = False
    created_at: datetime
    updated_at: datetime


class PersonaListResponse(BaseModel):
    """Response model for listing personas."""
    personas: list[dict]
    total: int
