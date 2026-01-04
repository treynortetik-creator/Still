"""Pydantic models for refresh API endpoints."""
from typing import List
from pydantic import BaseModel


class BulkRetireRequest(BaseModel):
    still_ids: List[str]


class BulkExtendReviewRequest(BaseModel):
    source_ids: List[int]
    days: int = 180


class MarkPerformerRequest(BaseModel):
    still_ids: List[str]


class RefreshCounts(BaseModel):
    sources: int
    stills: int
