"""Analytics API endpoints for usage tracking and ROI metrics."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends

from app.config import get_settings
from app.database import get_db
from app.db_utils import fetchone, fetchall
from app.api.auth import get_current_user_id

settings = get_settings()
from app.models.analytics import (
    UsageStats,
    CostStats,
    ContentBreakdown,
    TimeSeriesDataPoint,
    ROIMetrics,
    AnalyticsSummary,
)

router = APIRouter()

# ROI Calculation Constants
HOURLY_WRITER_RATE = 75.0  # $/hour
MINUTES_PER_LINKEDIN_POST = 45
MINUTES_PER_BLOG_POST = 180
MINUTES_PER_EMAIL = 30
MINUTES_PER_EMAIL_SEQUENCE = 120


@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(user_id: int = Depends(get_current_user_id)):
    """Get complete analytics summary including usage, costs, ROI, and trends."""
    usage = await get_usage_stats(user_id)
    costs = await get_cost_stats(user_id)
    content_breakdown = await get_content_breakdown(user_id)
    roi = await calculate_roi_metrics(user_id, content_breakdown, costs.total_cost)
    weekly_trend = await get_weekly_trend(user_id)
    monthly_trend = await get_monthly_trend(user_id)

    return AnalyticsSummary(
        usage=usage,
        costs=costs,
        content_breakdown=content_breakdown,
        roi=roi,
        weekly_trend=weekly_trend,
        monthly_trend=monthly_trend,
    )


@router.get("/analytics/usage", response_model=UsageStats)
async def get_usage_endpoint(user_id: int = Depends(get_current_user_id)):
    """Get usage statistics only."""
    return await get_usage_stats(user_id)


@router.get("/analytics/costs", response_model=CostStats)
async def get_costs_endpoint(user_id: int = Depends(get_current_user_id)):
    """Get cost statistics only."""
    return await get_cost_stats(user_id)


@router.get("/analytics/roi", response_model=ROIMetrics)
async def get_roi_endpoint(user_id: int = Depends(get_current_user_id)):
    """Get ROI metrics only."""
    content_breakdown = await get_content_breakdown(user_id)
    costs = await get_cost_stats(user_id)
    return await calculate_roi_metrics(user_id, content_breakdown, costs.total_cost)


async def get_usage_stats(user_id: int) -> UsageStats:
    """Calculate usage statistics from database."""
    async with get_db() as db:
        # Get job counts
        job_stats = await fetchone(
            db,
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM jobs
            WHERE user_id = ?
            """,
            (user_id,)
        )

        # Get total content pieces (outputs)
        output_count = await fetchone(
            db,
            """
            SELECT COUNT(*) as total
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE j.user_id = ?
            """,
            (user_id,)
        )

        # Get total stills (atoms)
        atom_count = await fetchone(
            db,
            """
            SELECT COUNT(*) as total
            FROM stills s
            JOIN jobs j ON s.job_id = j.id
            WHERE j.user_id = ?
            """,
            (user_id,)
        )

        # Get library size (unique stills in content_library)
        library_count = await fetchone(
            db,
            """
            SELECT COUNT(*) as total
            FROM content_library
            WHERE user_id = ?
            """,
            (user_id,)
        )

        return UsageStats(
            total_jobs=job_stats["total"] or 0,
            completed_jobs=job_stats["completed"] or 0,
            failed_jobs=job_stats["failed"] or 0,
            total_content_pieces=output_count["total"] or 0,
            total_atoms=atom_count["total"] or 0,
            library_size=library_count["total"] or 0,
        )


async def get_cost_stats(user_id: int) -> CostStats:
    """Calculate cost statistics from database."""
    now = datetime.utcnow()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    first_of_last_month = (first_of_month - timedelta(days=1)).replace(day=1)

    async with get_db() as db:
        # Total cost
        total = await fetchone(
            db,
            """
            SELECT COALESCE(SUM(cost_incurred), 0) as total
            FROM jobs
            WHERE user_id = ?
            """,
            (user_id,)
        )

        # Cost this month
        this_month = await fetchone(
            db,
            """
            SELECT COALESCE(SUM(cost_incurred), 0) as total
            FROM jobs
            WHERE user_id = ? AND created_at >= ?
            """,
            (user_id, first_of_month.isoformat())
        )

        # Cost last month
        last_month = await fetchone(
            db,
            """
            SELECT COALESCE(SUM(cost_incurred), 0) as total
            FROM jobs
            WHERE user_id = ? AND created_at >= ? AND created_at < ?
            """,
            (user_id, first_of_last_month.isoformat(), first_of_month.isoformat())
        )

        # Average cost per job
        avg = await fetchone(
            db,
            """
            SELECT
                COALESCE(AVG(cost_incurred), 0) as avg_cost
            FROM jobs
            WHERE user_id = ? AND status = 'complete'
            """,
            (user_id,)
        )

        return CostStats(
            total_cost=round(total["total"], 2),
            cost_this_month=round(this_month["total"], 2),
            cost_last_month=round(last_month["total"], 2),
            average_cost_per_job=round(avg["avg_cost"], 2),
        )


async def get_content_breakdown(user_id: int) -> ContentBreakdown:
    """Get breakdown of content by type."""
    async with get_db() as db:
        rows = await fetchall(
            db,
            """
            SELECT
                content_type,
                COUNT(*) as count
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE j.user_id = ?
            GROUP BY content_type
            """,
            (user_id,)
        )

        # Initialize counts
        breakdown = {
            "linkedin": 0,
            "blog": 0,
            "email": 0,
            "email_sequence": 0,
        }

        # Fill in actual counts
        for row in rows:
            content_type = row["content_type"]
            if content_type in breakdown:
                breakdown[content_type] = row["count"]

        return ContentBreakdown(**breakdown)


async def calculate_roi_metrics(
    user_id: int,
    content_breakdown: ContentBreakdown,
    total_cost: float
) -> ROIMetrics:
    """Calculate ROI metrics based on content created."""
    # Calculate total content pieces
    total_pieces = (
        content_breakdown.linkedin +
        content_breakdown.blog +
        content_breakdown.email +
        content_breakdown.email_sequence
    )

    # Calculate estimated time saved in minutes
    minutes_saved = (
        content_breakdown.linkedin * MINUTES_PER_LINKEDIN_POST +
        content_breakdown.blog * MINUTES_PER_BLOG_POST +
        content_breakdown.email * MINUTES_PER_EMAIL +
        content_breakdown.email_sequence * MINUTES_PER_EMAIL_SEQUENCE
    )

    # Convert to hours
    hours_saved = minutes_saved / 60

    # Calculate value generated (what it would cost to hire a writer)
    value_generated = hours_saved * HOURLY_WRITER_RATE

    # Calculate net ROI
    net_roi = value_generated - total_cost

    # Calculate ROI percentage
    roi_percentage = 0.0
    if total_cost > 0:
        roi_percentage = (net_roi / total_cost) * 100

    return ROIMetrics(
        content_pieces_created=total_pieces,
        estimated_writing_hours_saved=round(hours_saved, 1),
        estimated_value_generated=round(value_generated, 2),
        cost_incurred=round(total_cost, 2),
        net_roi=round(net_roi, 2),
        roi_percentage=round(roi_percentage, 1),
    )


async def get_weekly_trend(user_id: int) -> list[TimeSeriesDataPoint]:
    """Get content creation trend for the last 7 days."""
    async with get_db() as db:
        # Get daily counts for last 7 days
        if settings.use_postgres:
            rows = await db.fetch(
                """
                SELECT
                    DATE(o.created_at)::text as date,
                    COUNT(*) as count
                FROM outputs o
                JOIN jobs j ON o.job_id = j.id
                WHERE j.user_id = $1
                    AND o.created_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(o.created_at)
                ORDER BY date
                """,
                user_id
            )
        else:
            cursor = await db.execute(
                """
                SELECT
                    DATE(o.created_at) as date,
                    COUNT(*) as count
                FROM outputs o
                JOIN jobs j ON o.job_id = j.id
                WHERE j.user_id = ?
                    AND o.created_at >= DATE('now', '-7 days')
                GROUP BY DATE(o.created_at)
                ORDER BY date
                """,
                (user_id,)
            )
            rows = await cursor.fetchall()

        # Create a dict of existing data
        data_map = {row["date"]: row["count"] for row in rows}

        # Fill in all 7 days
        result = []
        for i in range(7):
            date = (datetime.utcnow() - timedelta(days=6-i)).strftime("%Y-%m-%d")
            result.append(TimeSeriesDataPoint(
                date=date,
                value=float(data_map.get(date, 0))
            ))

        return result


async def get_monthly_trend(user_id: int) -> list[TimeSeriesDataPoint]:
    """Get content creation trend for the last 30 days (weekly aggregates)."""
    async with get_db() as db:
        # Get weekly counts for last 4 weeks
        if settings.use_postgres:
            rows = await db.fetch(
                """
                SELECT
                    TO_CHAR(o.created_at, 'IYYY-IW') as week,
                    MIN(DATE(o.created_at))::text as week_start,
                    COUNT(*) as count
                FROM outputs o
                JOIN jobs j ON o.job_id = j.id
                WHERE j.user_id = $1
                    AND o.created_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY TO_CHAR(o.created_at, 'IYYY-IW')
                ORDER BY week
                """,
                user_id
            )
        else:
            cursor = await db.execute(
                """
                SELECT
                    strftime('%Y-%W', o.created_at) as week,
                    MIN(DATE(o.created_at)) as week_start,
                    COUNT(*) as count
                FROM outputs o
                JOIN jobs j ON o.job_id = j.id
                WHERE j.user_id = ?
                    AND o.created_at >= DATE('now', '-30 days')
                GROUP BY strftime('%Y-%W', o.created_at)
                ORDER BY week
                """,
                (user_id,)
            )
            rows = await cursor.fetchall()

        # Convert to time series points
        result = []
        for row in rows:
            result.append(TimeSeriesDataPoint(
                date=row["week_start"],
                value=float(row["count"])
            ))

        # If no data, return empty weeks
        if not result:
            for i in range(4):
                date = (datetime.utcnow() - timedelta(weeks=3-i)).strftime("%Y-%m-%d")
                result.append(TimeSeriesDataPoint(date=date, value=0.0))

        return result
