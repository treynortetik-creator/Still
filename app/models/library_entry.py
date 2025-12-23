"""Content library entry models."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class LibraryEntryCreate(BaseModel):
    """Model for creating a library entry."""
    entry_type: str
    content: str
    source: Optional[str] = None
    source_timestamp: Optional[str] = None
    speaker: Optional[str] = None
    tags: list[str] = []
    persona_relevance: dict[str, int] = {}
    user_notes: Optional[str] = None


class LibraryEntry(LibraryEntryCreate):
    """Full library entry model with database fields."""
    id: int
    user_id: int
    date_added: datetime
    times_used: int = 0
    last_used: Optional[datetime] = None


class LibraryResponse(BaseModel):
    """Response model for library queries."""
    entries: list[LibraryEntry]
    total: int
