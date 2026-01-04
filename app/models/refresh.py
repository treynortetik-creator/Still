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


class MergeDuplicatesRequest(BaseModel):
    winner_id: str
    loser_id: str


class DuplicatePair(BaseModel):
    still_a: dict
    still_b: dict
    similarity: float


class FindDuplicatesResponse(BaseModel):
    duplicates: List[DuplicatePair]
    threshold_used: float
    stills_scanned: int
