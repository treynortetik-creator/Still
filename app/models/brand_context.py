"""Brand context and persona models."""
from typing import Optional
from pydantic import BaseModel


class ContentPreferences(BaseModel):
    """Content preferences for a persona."""
    length: str = "Medium"
    data_density: str = "Moderate"
    tone: str = "Professional"


class Persona(BaseModel):
    """Target persona for content generation."""
    id: str
    title: str
    company_size: Optional[str] = None
    pain_points: list[str] = []
    language_level: str = "Professional"
    priorities: list[str] = []
    content_preferences: ContentPreferences = ContentPreferences()


class BrandVoice(BaseModel):
    """Brand voice configuration."""
    tone: str = "Professional and empathetic"
    style: str = "Conversational but authoritative"
    values: list[str] = []
    do_not_say: list[str] = []
    always_include: list[str] = []


class BrandContext(BaseModel):
    """Full brand context for a client."""
    company_name: str
    industry: str
    brand_voice: BrandVoice = BrandVoice()
    mission_statement: Optional[str] = None
    key_differentiators: list[str] = []
    competitor_names: list[str] = []
    personas: list[Persona] = []
