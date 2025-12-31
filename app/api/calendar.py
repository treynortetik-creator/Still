"""Content Calendar API endpoints."""
import json
from datetime import datetime, timedelta, date, time
from typing import Optional
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Depends, Query

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall
from app.api.auth import get_current_user_id

settings = get_settings()
from app.models.calendar import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    ScheduledItem,
    UnscheduledOutput,
    CalendarView,
)

router = APIRouter()


@router.post("/calendar/schedule", response_model=ScheduleResponse)
async def schedule_content(
    data: ScheduleCreate,
    user_id: int = Depends(get_current_user_id),
):
    """Schedule content for a specific date."""
    # Validate platform
    valid_platforms = {"linkedin", "blog", "email", "email_sequence"}
    if data.platform not in valid_platforms:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {data.platform}")

    async with get_db() as db:
        # Verify output exists and belongs to user
        output = await fetchone(
            db,
            """
            SELECT o.id, o.content_type, o.step3_final
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE o.id = ? AND j.user_id = ?
            """,
            (data.output_id, user_id)
        )
        if not output:
            raise HTTPException(status_code=404, detail="Output not found")

        # Check if already scheduled for this platform
        existing = await fetchone(
            db,
            "SELECT id FROM content_schedule WHERE output_id = ? AND platform = ?",
            (data.output_id, data.platform)
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail="This content is already scheduled for this platform"
            )

        # Create schedule
        # Convert string date/time to proper objects for asyncpg (PostgreSQL requires proper types)
        try:
            scheduled_date_obj = date.fromisoformat(data.scheduled_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        try:
            scheduled_time_obj = time.fromisoformat(data.scheduled_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM:SS")

        if settings.use_postgres:
            row = await db.fetchrow(
                """
                INSERT INTO content_schedule
                (user_id, output_id, scheduled_date, scheduled_time, platform, notes)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                user_id,
                data.output_id,
                scheduled_date_obj,
                scheduled_time_obj,
                data.platform,
                data.notes
            )
            schedule = dict(row)
        else:
            await execute(
                db,
                """
                INSERT INTO content_schedule
                (user_id, output_id, scheduled_date, scheduled_time, platform, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    data.output_id,
                    scheduled_date_obj.isoformat(),  # SQLite stores dates as strings
                    scheduled_time_obj.isoformat(),  # SQLite stores times as strings
                    data.platform,
                    data.notes
                )
            )
            await db.commit()

            # Get created schedule
            cursor = await db.execute("SELECT last_insert_rowid()")
            schedule_id = (await cursor.fetchone())[0]

            schedule = await fetchone(
                db,
                "SELECT * FROM content_schedule WHERE id = ?",
                (schedule_id,)
            )

        if not schedule:
            raise HTTPException(
                status_code=500,
                detail="Failed to create schedule entry"
            )

    content_preview = (output["step3_final"] or "")[:100] + "..." if output["step3_final"] else ""

    return ScheduleResponse(
        id=schedule["id"],
        output_id=schedule["output_id"],
        scheduled_date=schedule["scheduled_date"],
        scheduled_time=schedule["scheduled_time"],
        platform=schedule["platform"],
        status=schedule["status"],
        notes=schedule["notes"],
        content_preview=content_preview,
        content_type=output["content_type"],
        created_at=schedule["created_at"]
    )


@router.get("/calendar", response_model=CalendarView)
async def get_calendar(
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
    user_id: int = Depends(get_current_user_id),
):
    """Get calendar view for a date range with scheduled and unscheduled content."""
    # Convert string dates to date objects for PostgreSQL
    try:
        start_date_obj = date.fromisoformat(start_date)
        end_date_obj = date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    async with get_db() as db:
        # Get scheduled content
        scheduled = await fetchall(
            db,
            """
            SELECT cs.id, cs.output_id, cs.scheduled_date, cs.scheduled_time,
                   cs.platform, cs.status, cs.notes,
                   o.content_type, o.step3_final
            FROM content_schedule cs
            JOIN outputs o ON cs.output_id = o.id
            WHERE cs.user_id = ?
            AND cs.scheduled_date >= ? AND cs.scheduled_date <= ?
            ORDER BY cs.scheduled_date, cs.scheduled_time
            """,
            (user_id, start_date_obj, end_date_obj)
        )

        # Group by date
        days = defaultdict(list)
        for item in scheduled:
            content_preview = (item["step3_final"] or "")[:100] + "..." if item["step3_final"] else ""
            days[item["scheduled_date"]].append(ScheduledItem(
                id=item["id"],
                output_id=item["output_id"],
                platform=item["platform"],
                scheduled_time=item["scheduled_time"],
                status=item["status"],
                content_preview=content_preview,
                content_type=item["content_type"],
                notes=item["notes"]
            ))

        # Get unscheduled outputs (not scheduled on any platform)
        unscheduled_rows = await fetchall(
            db,
            """
            SELECT o.id, o.content_type, o.step3_final, o.job_id, o.created_at
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE j.user_id = ?
            AND j.status = 'complete'
            AND o.id NOT IN (
                SELECT output_id FROM content_schedule WHERE user_id = ?
            )
            ORDER BY o.created_at DESC
            LIMIT 50
            """,
            (user_id, user_id)
        )

        unscheduled = []
        for row in unscheduled_rows:
            content_preview = (row["step3_final"] or "")[:100] + "..." if row["step3_final"] else ""
            # Convert datetime to string for Pydantic
            created_at = row["created_at"]
            if hasattr(created_at, 'isoformat'):
                created_at = created_at.isoformat()
            unscheduled.append(UnscheduledOutput(
                output_id=row["id"],
                content_type=row["content_type"],
                content_preview=content_preview,
                job_id=row["job_id"],
                created_at=created_at
            ))

    return CalendarView(
        start_date=start_date,
        end_date=end_date,
        days=dict(days),
        unscheduled=unscheduled,
        total_scheduled=len(scheduled),
        total_unscheduled=len(unscheduled)
    )


@router.get("/calendar/unscheduled")
async def get_unscheduled_content(
    limit: int = Query(50, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
):
    """Get outputs that haven't been scheduled yet."""
    async with get_db() as db:
        rows = await fetchall(
            db,
            """
            SELECT o.id, o.content_type, o.step3_final, o.job_id, o.created_at
            FROM outputs o
            JOIN jobs j ON o.job_id = j.id
            WHERE j.user_id = ?
            AND j.status = 'complete'
            AND o.id NOT IN (
                SELECT output_id FROM content_schedule WHERE user_id = ?
            )
            ORDER BY o.created_at DESC
            LIMIT ?
            """,
            (user_id, user_id, limit)
        )

    outputs = []
    for row in rows:
        content_preview = (row["step3_final"] or "")[:100] + "..." if row["step3_final"] else ""
        # Convert datetime to string for JSON serialization
        created_at = row["created_at"]
        if hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()
        outputs.append({
            "output_id": row["id"],
            "content_type": row["content_type"],
            "content_preview": content_preview,
            "job_id": row["job_id"],
            "created_at": created_at
        })

    return {"outputs": outputs, "total": len(outputs)}


@router.get("/calendar/schedule/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Get a specific schedule entry."""
    async with get_db() as db:
        schedule = await fetchone(
            db,
            """
            SELECT cs.*, o.content_type, o.step3_final
            FROM content_schedule cs
            JOIN outputs o ON cs.output_id = o.id
            WHERE cs.id = ? AND cs.user_id = ?
            """,
            (schedule_id, user_id)
        )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    content_preview = (schedule["step3_final"] or "")[:100] + "..." if schedule["step3_final"] else ""

    return ScheduleResponse(
        id=schedule["id"],
        output_id=schedule["output_id"],
        scheduled_date=schedule["scheduled_date"],
        scheduled_time=schedule["scheduled_time"],
        platform=schedule["platform"],
        status=schedule["status"],
        notes=schedule["notes"],
        content_preview=content_preview,
        content_type=schedule["content_type"],
        created_at=schedule["created_at"]
    )


@router.put("/calendar/schedule/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """Update a schedule entry (reschedule, change status, etc.)."""
    async with get_db() as db:
        # Check ownership
        schedule = await fetchone(
            db,
            "SELECT * FROM content_schedule WHERE id = ? AND user_id = ?",
            (schedule_id, user_id)
        )
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Build update query
        updates = []
        values = []

        if data.scheduled_date is not None:
            # Convert string to date object for asyncpg (PostgreSQL requires proper date types)
            try:
                scheduled_date_obj = date.fromisoformat(data.scheduled_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
            updates.append("scheduled_date = ?")
            # Use date object for PostgreSQL, string for SQLite
            values.append(scheduled_date_obj if settings.use_postgres else data.scheduled_date)

        if data.scheduled_time is not None:
            # Convert string to time object for asyncpg (PostgreSQL requires proper time types)
            try:
                scheduled_time_obj = time.fromisoformat(data.scheduled_time)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM:SS")
            updates.append("scheduled_time = ?")
            # Use time object for PostgreSQL, string for SQLite
            values.append(scheduled_time_obj if settings.use_postgres else data.scheduled_time)

        if data.platform is not None:
            valid_platforms = {"linkedin", "blog", "email", "email_sequence"}
            if data.platform not in valid_platforms:
                raise HTTPException(status_code=400, detail=f"Invalid platform: {data.platform}")
            updates.append("platform = ?")
            values.append(data.platform)

        if data.status is not None:
            valid_statuses = {"scheduled", "published", "cancelled"}
            if data.status not in valid_statuses:
                raise HTTPException(status_code=400, detail=f"Invalid status: {data.status}")
            updates.append("status = ?")
            values.append(data.status)

        if data.notes is not None:
            updates.append("notes = ?")
            values.append(data.notes)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            values.append(schedule_id)
            await execute(
                db,
                f"UPDATE content_schedule SET {', '.join(updates)} WHERE id = ?",
                tuple(values)
            )
            if not settings.use_postgres:
                await db.commit()

        # Get updated schedule with content
        updated = await fetchone(
            db,
            """
            SELECT cs.*, o.content_type, o.step3_final
            FROM content_schedule cs
            JOIN outputs o ON cs.output_id = o.id
            WHERE cs.id = ?
            """,
            (schedule_id,)
        )

    content_preview = (updated["step3_final"] or "")[:100] + "..." if updated["step3_final"] else ""

    return ScheduleResponse(
        id=updated["id"],
        output_id=updated["output_id"],
        scheduled_date=updated["scheduled_date"],
        scheduled_time=updated["scheduled_time"],
        platform=updated["platform"],
        status=updated["status"],
        notes=updated["notes"],
        content_preview=content_preview,
        content_type=updated["content_type"],
        created_at=updated["created_at"]
    )


@router.delete("/calendar/schedule/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Remove a content from the calendar."""
    async with get_db() as db:
        # Check ownership
        existing = await fetchone(
            db,
            "SELECT id FROM content_schedule WHERE id = ? AND user_id = ?",
            (schedule_id, user_id)
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Schedule not found")

        await execute(
            db,
            "DELETE FROM content_schedule WHERE id = ?",
            (schedule_id,)
        )
        if not settings.use_postgres:
            await db.commit()

    return {"message": "Schedule removed"}
