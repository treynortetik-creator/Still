"""Custom Persona CRUD API endpoints."""
import json
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall
from app.api.auth import get_current_user_id
from app.models.persona import PersonaCreate, PersonaUpdate, PersonaResponse, PersonaListResponse

settings = get_settings()
router = APIRouter()


def _row_to_persona_dict(row) -> dict:
    """Convert a database row to a persona dictionary."""
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "role": row["role"],
        "title": f"{row['name']} ({row['role']})",  # For compatibility with default personas
        "industry": row["industry"],
        "pain_points": json.loads(row["pain_points"]) if row["pain_points"] else [],
        "goals": json.loads(row["goals"]) if row["goals"] else [],
        "priorities": json.loads(row["goals"]) if row["goals"] else [],  # Alias for compatibility
        "tone_preferences": json.loads(row["tone_preferences"]) if row["tone_preferences"] else None,
        "content_preferences": json.loads(row["content_preferences"]) if row["content_preferences"] else None,
        "is_default": bool(row["is_default"]),
        "is_custom": True,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.post("/custom-personas", response_model=PersonaResponse)
async def create_persona(
    persona_data: PersonaCreate,
    user_id: int = Depends(get_current_user_id),
):
    """Create a new custom persona."""
    persona_id = str(uuid.uuid4())
    now = datetime.utcnow()

    async with get_db() as db:
        await execute(
            db,
            """
            INSERT INTO personas (id, user_id, name, role, industry, pain_points, goals,
                                  tone_preferences, content_preferences, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                persona_id,
                user_id,
                persona_data.name,
                persona_data.role,
                persona_data.industry,
                json.dumps(persona_data.pain_points),
                json.dumps(persona_data.goals),
                json.dumps(persona_data.tone_preferences.model_dump() if persona_data.tone_preferences else None),
                json.dumps(persona_data.content_preferences.model_dump() if persona_data.content_preferences else None),
                False,
                now,
                now,
            )
        )
        if not settings.use_postgres:
            await db.commit()

        # Fetch the created persona
        row = await fetchone(
            db,
            "SELECT * FROM personas WHERE id = ?",
            (persona_id,)
        )

    return PersonaResponse(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        role=row["role"],
        industry=row["industry"],
        pain_points=json.loads(row["pain_points"]),
        goals=json.loads(row["goals"]),
        tone_preferences=json.loads(row["tone_preferences"]) if row["tone_preferences"] else None,
        content_preferences=json.loads(row["content_preferences"]) if row["content_preferences"] else None,
        is_default=bool(row["is_default"]),
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
        updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
    )


@router.get("/custom-personas")
async def list_custom_personas(
    user_id: int = Depends(get_current_user_id),
):
    """List all custom personas for the current user."""
    async with get_db() as db:
        rows = await fetchall(
            db,
            "SELECT * FROM personas WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )

    personas = [_row_to_persona_dict(row) for row in rows]
    return {"personas": personas, "total": len(personas)}


@router.get("/custom-personas/{persona_id}")
async def get_custom_persona(
    persona_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """Get a specific custom persona."""
    async with get_db() as db:
        row = await fetchone(
            db,
            "SELECT * FROM personas WHERE id = ? AND user_id = ?",
            (persona_id, user_id)
        )

    if not row:
        raise HTTPException(status_code=404, detail="Persona not found")

    return _row_to_persona_dict(row)


@router.put("/custom-personas/{persona_id}")
async def update_persona(
    persona_id: str,
    persona_data: PersonaUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """Update an existing custom persona."""
    async with get_db() as db:
        # Check persona exists and belongs to user
        existing = await fetchone(
            db,
            "SELECT * FROM personas WHERE id = ? AND user_id = ?",
            (persona_id, user_id)
        )

        if not existing:
            raise HTTPException(status_code=404, detail="Persona not found")

        # Build update fields
        update_fields = []
        params = []

        if persona_data.name is not None:
            update_fields.append("name = ?")
            params.append(persona_data.name)
        if persona_data.role is not None:
            update_fields.append("role = ?")
            params.append(persona_data.role)
        if persona_data.industry is not None:
            update_fields.append("industry = ?")
            params.append(persona_data.industry)
        if persona_data.pain_points is not None:
            update_fields.append("pain_points = ?")
            params.append(json.dumps(persona_data.pain_points))
        if persona_data.goals is not None:
            update_fields.append("goals = ?")
            params.append(json.dumps(persona_data.goals))
        if persona_data.tone_preferences is not None:
            update_fields.append("tone_preferences = ?")
            params.append(json.dumps(persona_data.tone_preferences.model_dump()))
        if persona_data.content_preferences is not None:
            update_fields.append("content_preferences = ?")
            params.append(json.dumps(persona_data.content_preferences.model_dump()))

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        update_fields.append("updated_at = ?")
        params.append(datetime.utcnow())
        params.append(persona_id)
        params.append(user_id)

        await execute(
            db,
            f"UPDATE personas SET {', '.join(update_fields)} WHERE id = ? AND user_id = ?",
            tuple(params)
        )
        if not settings.use_postgres:
            await db.commit()

        # Fetch updated persona
        row = await fetchone(
            db,
            "SELECT * FROM personas WHERE id = ?",
            (persona_id,)
        )

    return _row_to_persona_dict(row)


@router.delete("/custom-personas/{persona_id}")
async def delete_persona(
    persona_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """Delete a custom persona."""
    async with get_db() as db:
        # Check persona exists and belongs to user
        existing = await fetchone(
            db,
            "SELECT id FROM personas WHERE id = ? AND user_id = ?",
            (persona_id, user_id)
        )

        if not existing:
            raise HTTPException(status_code=404, detail="Persona not found")

        await execute(
            db,
            "DELETE FROM personas WHERE id = ? AND user_id = ?",
            (persona_id, user_id)
        )
        if not settings.use_postgres:
            await db.commit()

    return {"message": "Persona deleted successfully"}
