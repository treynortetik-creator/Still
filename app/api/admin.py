"""Admin API endpoints."""
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.database import get_db

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard():
    """
    Get admin dashboard overview.
    """
    async with get_db() as db:
        # Active jobs
        cursor = await db.execute(
            """
            SELECT COUNT(*) FROM jobs
            WHERE status NOT IN ('complete', 'failed')
            """
        )
        active_jobs = (await cursor.fetchone())[0]

        # Jobs completed today
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = await db.execute(
            """
            SELECT COUNT(*) FROM jobs
            WHERE status = 'complete'
            AND date(completed_at) = ?
            """,
            (today,)
        )
        completed_today = (await cursor.fetchone())[0]

        # Total cost today
        cursor = await db.execute(
            """
            SELECT COALESCE(SUM(cost_incurred), 0) FROM jobs
            WHERE date(created_at) = ?
            """,
            (today,)
        )
        cost_today = (await cursor.fetchone())[0]

        # Total cost this week
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        cursor = await db.execute(
            """
            SELECT COALESCE(SUM(cost_incurred), 0) FROM jobs
            WHERE date(created_at) >= ?
            """,
            (week_ago,)
        )
        cost_week = (await cursor.fetchone())[0]

        # Total cost this month
        month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        cursor = await db.execute(
            """
            SELECT COALESCE(SUM(cost_incurred), 0) FROM jobs
            WHERE date(created_at) >= ?
            """,
            (month_start,)
        )
        cost_month = (await cursor.fetchone())[0]

        # Library size
        cursor = await db.execute("SELECT COUNT(*) FROM content_library")
        library_size = (await cursor.fetchone())[0]

        # Recent activity
        cursor = await db.execute(
            """
            SELECT id, status, original_filename, created_at, completed_at
            FROM jobs
            ORDER BY created_at DESC
            LIMIT 10
            """
        )
        recent_jobs = [
            {
                "id": row["id"],
                "status": row["status"],
                "filename": row["original_filename"],
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
            }
            for row in await cursor.fetchall()
        ]

        return {
            "active_jobs": active_jobs,
            "completed_today": completed_today,
            "costs": {
                "today": round(cost_today, 4),
                "this_week": round(cost_week, 4),
                "this_month": round(cost_month, 4),
            },
            "library_size": library_size,
            "recent_activity": recent_jobs,
        }


@router.get("/prompts")
async def list_prompts():
    """
    List all prompt templates.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id, template_name, model, max_tokens, variables, version, updated_at
            FROM prompt_templates
            ORDER BY template_name
            """
        )
        prompts = [
            {
                "id": row["id"],
                "template_name": row["template_name"],
                "model": row["model"],
                "max_tokens": row["max_tokens"],
                "variables": json.loads(row["variables"]) if row["variables"] else [],
                "version": row["version"],
                "updated_at": row["updated_at"],
            }
            for row in await cursor.fetchall()
        ]

        return {"prompts": prompts}


@router.get("/prompts/{template_name}")
async def get_prompt(template_name: str):
    """
    Get a specific prompt template.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT * FROM prompt_templates WHERE template_name = ?
            """,
            (template_name,)
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Template not found")

        return {
            "id": row["id"],
            "template_name": row["template_name"],
            "model": row["model"],
            "max_tokens": row["max_tokens"],
            "prompt_content": row["prompt_content"],
            "variables": json.loads(row["variables"]) if row["variables"] else [],
            "version": row["version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


@router.put("/prompts/{template_name}")
async def update_prompt(
    template_name: str,
    prompt_content: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
):
    """
    Update a prompt template.
    """
    async with get_db() as db:
        # Check if exists
        cursor = await db.execute(
            "SELECT id, version FROM prompt_templates WHERE template_name = ?",
            (template_name,)
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Template not found")

        # Update with version increment
        new_version = row["version"] + 1
        update_fields = ["prompt_content = ?", "version = ?", "updated_at = CURRENT_TIMESTAMP"]
        params = [prompt_content, new_version]

        if model:
            update_fields.append("model = ?")
            params.append(model)

        if max_tokens:
            update_fields.append("max_tokens = ?")
            params.append(max_tokens)

        params.append(template_name)

        await db.execute(
            f"""
            UPDATE prompt_templates
            SET {", ".join(update_fields)}
            WHERE template_name = ?
            """,
            params
        )
        await db.commit()

        return {"message": "Template updated", "version": new_version}


@router.get("/clients")
async def list_clients():
    """
    List all clients/users.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT u.id, u.email, u.subscription_tier, u.created_at,
                   COUNT(j.id) as job_count,
                   COALESCE(SUM(j.cost_incurred), 0) as total_cost
            FROM users u
            LEFT JOIN jobs j ON u.id = j.user_id
            GROUP BY u.id
            ORDER BY u.created_at DESC
            """
        )
        clients = [
            {
                "id": row["id"],
                "email": row["email"],
                "subscription_tier": row["subscription_tier"],
                "created_at": row["created_at"],
                "job_count": row["job_count"],
                "total_cost": round(row["total_cost"], 4),
            }
            for row in await cursor.fetchall()
        ]

        return {"clients": clients}


@router.get("/clients/{client_id}")
async def get_client(client_id: int):
    """
    Get detailed client information.
    """
    async with get_db() as db:
        # Get user info
        cursor = await db.execute(
            "SELECT * FROM users WHERE id = ?",
            (client_id,)
        )
        user = await cursor.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Client not found")

        # Get job history
        cursor = await db.execute(
            """
            SELECT id, status, original_filename, created_at, completed_at, cost_incurred
            FROM jobs
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (client_id,)
        )
        jobs = [dict(row) for row in await cursor.fetchall()]

        # Get library stats
        cursor = await db.execute(
            """
            SELECT entry_type, COUNT(*) as count
            FROM content_library
            WHERE user_id = ?
            GROUP BY entry_type
            """,
            (client_id,)
        )
        library_stats = {row["entry_type"]: row["count"] for row in await cursor.fetchall()}

        # Total cost
        cursor = await db.execute(
            "SELECT COALESCE(SUM(cost_incurred), 0) FROM jobs WHERE user_id = ?",
            (client_id,)
        )
        total_cost = (await cursor.fetchone())[0]

        return {
            "id": user["id"],
            "email": user["email"],
            "subscription_tier": user["subscription_tier"],
            "created_at": user["created_at"],
            "total_cost": round(total_cost, 4),
            "library_stats": library_stats,
            "recent_jobs": jobs,
        }


@router.get("/costs")
async def get_costs(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    group_by: str = Query("day", description="Group by: day, user, or job"),
):
    """
    Get cost breakdown.
    """
    async with get_db() as db:
        if group_by == "day":
            query = """
                SELECT date(created_at) as date, SUM(cost_incurred) as cost
                FROM jobs
                WHERE 1=1
            """
            params = []

            if start_date:
                query += " AND date(created_at) >= ?"
                params.append(start_date)
            if end_date:
                query += " AND date(created_at) <= ?"
                params.append(end_date)

            query += " GROUP BY date(created_at) ORDER BY date DESC"

            cursor = await db.execute(query, params)
            results = [
                {"date": row["date"], "cost": round(row["cost"], 4)}
                for row in await cursor.fetchall()
            ]

        elif group_by == "user":
            query = """
                SELECT u.email, SUM(j.cost_incurred) as cost
                FROM jobs j
                JOIN users u ON j.user_id = u.id
                WHERE 1=1
            """
            params = []

            if start_date:
                query += " AND date(j.created_at) >= ?"
                params.append(start_date)
            if end_date:
                query += " AND date(j.created_at) <= ?"
                params.append(end_date)

            query += " GROUP BY u.id ORDER BY cost DESC"

            cursor = await db.execute(query, params)
            results = [
                {"user": row["email"], "cost": round(row["cost"], 4)}
                for row in await cursor.fetchall()
            ]

        else:  # group_by == "job"
            query = """
                SELECT id, original_filename, cost_incurred, created_at
                FROM jobs
                WHERE 1=1
            """
            params = []

            if start_date:
                query += " AND date(created_at) >= ?"
                params.append(start_date)
            if end_date:
                query += " AND date(created_at) <= ?"
                params.append(end_date)

            query += " ORDER BY created_at DESC LIMIT 100"

            cursor = await db.execute(query, params)
            results = [
                {
                    "job_id": row["id"],
                    "filename": row["original_filename"],
                    "cost": round(row["cost_incurred"], 4),
                    "created_at": row["created_at"],
                }
                for row in await cursor.fetchall()
            ]

        return {"costs": results, "group_by": group_by}


@router.get("/logs")
async def get_logs(
    level: Optional[str] = Query(None, description="Filter by level (error, warning, info)"),
    start_date: Optional[str] = Query(None),
    limit: int = Query(100),
):
    """
    Get job logs/errors.

    Note: For MVP, we extract errors from job records. A proper logging
    system would be implemented in production.
    """
    async with get_db() as db:
        query = """
            SELECT id, status, error_message, created_at, completed_at
            FROM jobs
            WHERE 1=1
        """
        params = []

        if level == "error":
            query += " AND status = 'failed'"

        if start_date:
            query += " AND date(created_at) >= ?"
            params.append(start_date)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = await db.execute(query, params)
        logs = [
            {
                "job_id": row["id"],
                "status": row["status"],
                "error_message": row["error_message"],
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
            }
            for row in await cursor.fetchall()
        ]

        return {"logs": logs}
