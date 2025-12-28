"""Admin API endpoints."""
import json
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Body, Depends
from typing import Optional, Dict
from pydantic import BaseModel
import httpx

from app.database import get_db
from app.services import settings_manager
from app.api.auth import verify_admin
from app.services.ai_editor import get_editor_config, save_editor_config, DEFAULT_EDITOR_PROMPT

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(_: bool = Depends(verify_admin)):
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
async def list_prompts(_: bool = Depends(verify_admin)):
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
async def get_prompt(template_name: str, _: bool = Depends(verify_admin)):
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
    _: bool = Depends(verify_admin),
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
async def list_clients(_: bool = Depends(verify_admin)):
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
async def get_client(client_id: int, _: bool = Depends(verify_admin)):
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
    _: bool = Depends(verify_admin),
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
    _: bool = Depends(verify_admin),
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


# Pydantic models for settings endpoints
class ApiKeyRequest(BaseModel):
    provider: str
    key: str


class OpenRouterToggle(BaseModel):
    enabled: bool


class ModelConfig(BaseModel):
    transcription: str
    atomization: str
    drafting: str
    editing: str
    factcheck: str


class AIEditorConfigRequest(BaseModel):
    """Request model for updating AI editor config."""
    system_prompt: Optional[str] = None
    model: Optional[str] = None


@router.get("/settings")
async def get_settings(_: bool = Depends(verify_admin)):
    """Get current settings including API key status and model config."""
    settings = settings_manager.get_settings()
    api_keys = settings_manager.get_api_key_status()
    
    return {
        "api_keys": api_keys,
        "use_openrouter": settings.get("use_openrouter", False),
        "models": settings.get("models", {})
    }


@router.post("/settings/apikey")
async def save_api_key(request: ApiKeyRequest, _: bool = Depends(verify_admin)):
    """
    Save API key - stores in environment for current session.
    Note: For permanent storage, keys should be set in Replit Secrets.
    """
    provider = request.provider.lower()
    key = request.key
    
    if provider == "openrouter":
        os.environ["OPENROUTER_API_KEY"] = key
    elif provider == "gemini":
        os.environ["GEMINI_API_KEY"] = key
    elif provider == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = key
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    return {"status": "ok", "message": f"{provider} API key saved for this session"}


@router.post("/settings/openrouter")
async def toggle_openrouter(request: OpenRouterToggle, _: bool = Depends(verify_admin)):
    """Toggle OpenRouter usage."""
    settings_manager.set_openrouter_enabled(request.enabled)
    return {"status": "ok", "use_openrouter": request.enabled}


@router.post("/settings/models")
async def save_model_config(config: ModelConfig, _: bool = Depends(verify_admin)):
    """Save model configuration for each pipeline step."""
    settings_manager.set_model_config({
        "transcription": config.transcription,
        "atomization": config.atomization,
        "drafting": config.drafting,
        "editing": config.editing,
        "factcheck": config.factcheck
    })
    return {"status": "ok", "models": config.model_dump()}


@router.get("/error-logs")
async def get_error_logs(
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    limit: int = Query(50, description="Max number of logs to return"),
    _: bool = Depends(verify_admin),
):
    """
    Get detailed error logs with stack traces for debugging.
    """
    async with get_db() as db:
        # First check if the error_logs table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='error_logs'"
        )
        table_exists = await cursor.fetchone()

        if not table_exists:
            # Create the table if it doesn't exist
            await db.execute("""
                CREATE TABLE IF NOT EXISTS error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    user_id INTEGER,
                    error_type TEXT,
                    error_message TEXT,
                    stack_trace TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            return {"error_logs": [], "message": "Error logs table created"}

        query = """
            SELECT el.*, j.original_filename, u.email
            FROM error_logs el
            LEFT JOIN jobs j ON el.job_id = j.id
            LEFT JOIN users u ON el.user_id = u.id
            WHERE 1=1
        """
        params = []

        if job_id:
            query += " AND el.job_id = ?"
            params.append(job_id)

        query += " ORDER BY el.created_at DESC LIMIT ?"
        params.append(limit)

        cursor = await db.execute(query, params)
        logs = []
        for row in await cursor.fetchall():
            logs.append({
                "id": row["id"],
                "job_id": row["job_id"],
                "user_id": row["user_id"],
                "error_type": row["error_type"],
                "error_message": row["error_message"],
                "stack_trace": row["stack_trace"],
                "created_at": row["created_at"],
                "filename": row["original_filename"] if "original_filename" in row.keys() else None,
                "user_email": row["email"] if "email" in row.keys() else None,
            })

        return {"error_logs": logs}


@router.get("/openrouter-models")
async def get_openrouter_models(_: bool = Depends(verify_admin)):
    """Fetch available models from OpenRouter."""
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    if not openrouter_key:
        raise HTTPException(status_code=400, detail="OpenRouter API key not configured")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {openrouter_key}"}
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to fetch OpenRouter models"
                )

            data = response.json()
            models = data.get("data", [])

            # Format models for frontend (id and name)
            formatted_models = [
                {
                    "id": model.get("id"),
                    "name": model.get("name", model.get("id")),
                    "pricing": model.get("pricing", {})
                }
                for model in models
                if model.get("id")
            ]

            # Sort by name
            formatted_models.sort(key=lambda x: x["name"])

            return {"models": formatted_models}

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to OpenRouter: {str(e)}"
        )


# ========== AI Model Configuration (Database-backed) ==========

class AIModelConfigRequest(BaseModel):
    """Request model for updating AI model config."""
    model_id: str
    display_name: Optional[str] = None
    cost_per_1k_input: Optional[float] = 0.0
    cost_per_1k_output: Optional[float] = 0.0
    max_tokens: Optional[int] = 4096
    is_active: Optional[bool] = True


# Service names that can have models configured
PIPELINE_SERVICES = ["transcription", "atomization", "drafting", "editing", "factcheck"]


@router.get("/model-config")
async def get_all_model_config(_: bool = Depends(verify_admin)):
    """Get all AI model configurations from database."""
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT service_name, model_id, display_name, is_active,
                   cost_per_1k_input, cost_per_1k_output, max_tokens,
                   created_at, updated_at
            FROM ai_model_config
            ORDER BY service_name
            """
        )
        rows = await cursor.fetchall()

        configs = {}
        for row in rows:
            configs[row["service_name"]] = {
                "model_id": row["model_id"],
                "display_name": row["display_name"],
                "is_active": bool(row["is_active"]),
                "cost_per_1k_input": row["cost_per_1k_input"],
                "cost_per_1k_output": row["cost_per_1k_output"],
                "max_tokens": row["max_tokens"],
                "updated_at": row["updated_at"],
            }

        # Add missing services with defaults
        for service in PIPELINE_SERVICES:
            if service not in configs:
                configs[service] = {
                    "model_id": "google/gemini-2.0-flash",
                    "display_name": "Gemini 2.0 Flash",
                    "is_active": True,
                    "cost_per_1k_input": 0.0001,
                    "cost_per_1k_output": 0.0004,
                    "max_tokens": 4096,
                    "updated_at": None,
                }

        return {"model_configs": configs, "services": PIPELINE_SERVICES}


@router.put("/model-config/{service_name}")
async def update_model_config(
    service_name: str,
    config: AIModelConfigRequest,
    _: bool = Depends(verify_admin),
):
    """Update AI model configuration for a specific service."""
    if service_name not in PIPELINE_SERVICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service name. Must be one of: {PIPELINE_SERVICES}"
        )

    async with get_db() as db:
        # Check if exists
        cursor = await db.execute(
            "SELECT id FROM ai_model_config WHERE service_name = ?",
            (service_name,)
        )
        exists = await cursor.fetchone()

        if exists:
            # Update
            await db.execute(
                """
                UPDATE ai_model_config
                SET model_id = ?, display_name = ?, cost_per_1k_input = ?,
                    cost_per_1k_output = ?, max_tokens = ?, is_active = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE service_name = ?
                """,
                (
                    config.model_id,
                    config.display_name or config.model_id,
                    config.cost_per_1k_input,
                    config.cost_per_1k_output,
                    config.max_tokens,
                    1 if config.is_active else 0,
                    service_name,
                )
            )
        else:
            # Insert
            await db.execute(
                """
                INSERT INTO ai_model_config
                (service_name, model_id, display_name, cost_per_1k_input,
                 cost_per_1k_output, max_tokens, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    service_name,
                    config.model_id,
                    config.display_name or config.model_id,
                    config.cost_per_1k_input,
                    config.cost_per_1k_output,
                    config.max_tokens,
                    1 if config.is_active else 0,
                )
            )

        await db.commit()

        # Also update the settings file so it persists
        current_models = settings_manager.get_settings().get("models", {})
        current_models[service_name] = config.model_id
        settings_manager.set_model_config(current_models)

        return {
            "message": f"Model config for {service_name} updated",
            "service_name": service_name,
            "model_id": config.model_id,
        }


@router.post("/model-config/init-defaults")
async def init_default_model_configs(_: bool = Depends(verify_admin)):
    """Initialize default model configurations for all services."""
    default_model = "google/gemini-2.0-flash"

    async with get_db() as db:
        for service in PIPELINE_SERVICES:
            # Check if exists
            cursor = await db.execute(
                "SELECT id FROM ai_model_config WHERE service_name = ?",
                (service,)
            )
            if not await cursor.fetchone():
                await db.execute(
                    """
                    INSERT INTO ai_model_config
                    (service_name, model_id, display_name, cost_per_1k_input,
                     cost_per_1k_output, max_tokens, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        service,
                        default_model,
                        "Gemini 2.0 Flash",
                        0.0001,
                        0.0004,
                        4096,
                        1,
                    )
                )

        await db.commit()

    return {"message": "Default model configs initialized", "services": PIPELINE_SERVICES}


# ========== AI Editor Configuration ==========

@router.get("/ai-editor-config")
async def get_ai_editor_config(_: bool = Depends(verify_admin)):
    """Get AI editor configuration."""
    config = await get_editor_config()
    return {
        "system_prompt": config.get("system_prompt", DEFAULT_EDITOR_PROMPT),
        "model": config.get("model", "google/gemini-2.5-flash-preview"),
        "default_prompt": DEFAULT_EDITOR_PROMPT,
    }


@router.put("/ai-editor-config")
async def update_ai_editor_config(
    request: AIEditorConfigRequest,
    _: bool = Depends(verify_admin),
):
    """Update AI editor configuration."""
    if request.system_prompt is not None:
        await save_editor_config("system_prompt", request.system_prompt)

    if request.model is not None:
        await save_editor_config("model", request.model)

    return {"message": "AI editor configuration saved"}


@router.post("/ai-editor-config/reset")
async def reset_ai_editor_config(_: bool = Depends(verify_admin)):
    """Reset AI editor configuration to defaults."""
    await save_editor_config("system_prompt", DEFAULT_EDITOR_PROMPT)
    await save_editor_config("model", "google/gemini-2.5-flash-preview")
    return {"message": "AI editor configuration reset to defaults"}
