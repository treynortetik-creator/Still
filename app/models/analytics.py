"""Pydantic models for usage analytics."""
from typing import Optional
from pydantic import BaseModel


class UsageStats(BaseModel):
    """Basic usage statistics."""
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_content_pieces: int
    total_atoms: int
    library_size: int


class CostStats(BaseModel):
    """API cost statistics."""
    total_cost: float
    cost_this_month: float
    cost_last_month: float
    average_cost_per_job: float


class ContentBreakdown(BaseModel):
    """Content type breakdown."""
    linkedin: int
    blog: int
    email: int
    email_sequence: int


class TimeSeriesDataPoint(BaseModel):
    """Single data point for time series."""
    date: str
    value: float


class ROIMetrics(BaseModel):
    """ROI calculation metrics."""
    content_pieces_created: int
    estimated_writing_hours_saved: float
    estimated_value_generated: float
    cost_incurred: float
    net_roi: float
    roi_percentage: float


class AnalyticsSummary(BaseModel):
    """Complete analytics summary."""
    usage: UsageStats
    costs: CostStats
    content_breakdown: ContentBreakdown
    roi: ROIMetrics
    weekly_trend: list[TimeSeriesDataPoint]
    monthly_trend: list[TimeSeriesDataPoint]
