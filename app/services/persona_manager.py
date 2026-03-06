"""Persona management service."""
import json
import time
import aiofiles
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.db_utils import fetchone, fetchall

settings = get_settings()

# Cache for personas with TTL
_personas_cache: Optional[dict] = None
_personas_cache_time: float = 0
_PERSONAS_CACHE_TTL: int = 300  # 5 minutes in seconds


async def load_personas() -> dict:
    """Load default personas from the JSON file with TTL caching."""
    global _personas_cache, _personas_cache_time

    # Check if cache is valid (exists and not expired)
    if _personas_cache is not None:
        if time.time() - _personas_cache_time < _PERSONAS_CACHE_TTL:
            return _personas_cache

    personas_file = settings.data_dir / "personas.json"

    if not personas_file.exists():
        # Return default personas if file doesn't exist
        _personas_cache = get_default_personas()
        _personas_cache_time = time.time()
        # Save to file for future edits
        await save_personas(_personas_cache)
        return _personas_cache

    async with aiofiles.open(personas_file, "r") as f:
        content = await f.read()
        _personas_cache = json.loads(content)
        _personas_cache_time = time.time()

    return _personas_cache


async def save_personas(personas_data: dict):
    """Save personas to the JSON file and update cache."""
    global _personas_cache, _personas_cache_time

    personas_file = settings.data_dir / "personas.json"
    personas_file.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(personas_file, "w") as f:
        await f.write(json.dumps(personas_data, indent=2))

    _personas_cache = personas_data
    _personas_cache_time = time.time()


async def get_persona(persona_id: str, user_id: int = None) -> Optional[dict]:
    """
    Get a specific persona by ID.

    First checks custom personas in DB (if user_id provided), then falls back to defaults.
    """
    # Check custom personas in DB first if user_id is provided
    if user_id:
        from app.database import get_db
        async with get_db() as db:
            row = await fetchone(
                db,
                "SELECT * FROM personas WHERE id = ? AND user_id = ?",
                (persona_id, user_id)
            )
            if row:
                return _row_to_persona_dict(row)

    # Fall back to default personas from JSON
    personas = await load_personas()
    for persona in personas.get("personas", []):
        if persona.get("id") == persona_id:
            persona_copy = dict(persona)
            persona_copy["is_default"] = True
            persona_copy["is_custom"] = False
            return persona_copy

    return None


async def get_persona_for_job(persona_id: str, user_id: int = None) -> Optional[dict]:
    """
    Get persona for use in job processing.

    Returns a normalized persona dict that works with drafting/editing services.
    """
    persona = await get_persona(persona_id, user_id)
    if not persona:
        return None

    # Normalize the persona to ensure it has all fields needed by the pipeline
    normalized = {
        "id": persona.get("id"),
        "title": persona.get("title") or f"{persona.get('name', '')} ({persona.get('role', '')})",
        "name": persona.get("name") or persona.get("title", ""),
        "role": persona.get("role", ""),
        "industry": persona.get("industry"),
        "pain_points": persona.get("pain_points", []),
        "priorities": persona.get("priorities") or persona.get("goals", []),
        "goals": persona.get("goals") or persona.get("priorities", []),
        "language_level": persona.get("language_level", "Professional"),
        "content_preferences": persona.get("content_preferences", {}),
        "tone_preferences": persona.get("tone_preferences", {}),
        "is_default": persona.get("is_default", False),
        "is_custom": persona.get("is_custom", False),
    }
    return normalized


async def list_personas() -> list[dict]:
    """List all default personas from JSON."""
    personas = await load_personas()
    return personas.get("personas", [])


async def list_all_personas(user_id: int) -> list[dict]:
    """List default personas + user's custom personas."""
    from app.database import get_db

    # Get defaults from JSON
    defaults = await load_personas()
    result = []
    for p in defaults.get("personas", []):
        persona = dict(p)
        persona["is_default"] = True
        persona["is_custom"] = False
        result.append(persona)

    # Add custom personas from DB
    async with get_db() as db:
        rows = await fetchall(
            db,
            "SELECT * FROM personas WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        for row in rows:
            result.append(_row_to_persona_dict(row))

    return result


def _row_to_persona_dict(row) -> dict:
    """Convert a database row to a persona dictionary."""
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "role": row["role"],
        "title": f"{row['name']} ({row['role']})",
        "industry": row["industry"],
        "pain_points": json.loads(row["pain_points"]) if row["pain_points"] else [],
        "goals": json.loads(row["goals"]) if row["goals"] else [],
        "priorities": json.loads(row["goals"]) if row["goals"] else [],
        "language_level": row["language_level"] if "language_level" in (row.keys() if hasattr(row, 'keys') else dict(row).keys()) else "Professional",
        "tone_preferences": json.loads(row["tone_preferences"]) if row["tone_preferences"] else None,
        "content_preferences": json.loads(row["content_preferences"]) if row["content_preferences"] else None,
        "is_default": bool(row["is_default"]),
        "is_custom": True,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_default_personas() -> dict:
    """Return the default hardcoded personas for MVP."""
    return {
        "personas": [
            {
                "id": "general_audience",
                "title": "General Audience",
                "company_size": "Any",
                "pain_points": [
                    "Information overload",
                    "Time constraints",
                    "Relevance to their needs"
                ],
                "language_level": "Professional - clear and accessible",
                "priorities": [
                    "Clear communication",
                    "Actionable insights",
                    "Value and relevance"
                ],
                "content_preferences": {
                    "length": "Medium - balanced",
                    "data_density": "Moderate - mix of insights and evidence",
                    "tone": "Professional and engaging"
                }
            },
            {
                "id": "ceo_longterm_care",
                "title": "CEO of Long-Term Care Facility",
                "company_size": "1000+ beds",
                "pain_points": [
                    "Staffing shortages",
                    "Resident retention",
                    "Regulatory compliance",
                    "Profitability pressure"
                ],
                "language_level": "Executive - high-level ROI focus",
                "priorities": [
                    "Bottom line impact",
                    "Competitive advantage",
                    "Operational efficiency"
                ],
                "content_preferences": {
                    "length": "Short - time-constrained",
                    "data_density": "High - wants metrics immediately",
                    "tone": "Confident and outcome-focused"
                }
            },
            {
                "id": "don_memory_care",
                "title": "Director of Nursing (Memory Care)",
                "company_size": "100-300 beds",
                "pain_points": [
                    "Resident safety",
                    "Staff training and retention",
                    "Family communication",
                    "Care quality documentation"
                ],
                "language_level": "Professional - clinical but accessible",
                "priorities": [
                    "Resident outcomes",
                    "Staff empowerment",
                    "Family trust"
                ],
                "content_preferences": {
                    "length": "Medium - wants actionable detail",
                    "data_density": "Moderate - clinical evidence appreciated",
                    "tone": "Empathetic and supportive"
                }
            },
            {
                "id": "marketing_director",
                "title": "Marketing Director (Senior Living)",
                "company_size": "500+ beds across multiple communities",
                "pain_points": [
                    "Lead generation",
                    "Brand differentiation",
                    "Content production at scale",
                    "ROI measurement"
                ],
                "language_level": "Professional - marketing-savvy",
                "priorities": [
                    "Conversion rates",
                    "Content velocity",
                    "Brand consistency"
                ],
                "content_preferences": {
                    "length": "Long - wants comprehensive insight",
                    "data_density": "Moderate - case studies over raw stats",
                    "tone": "Creative but strategic"
                }
            }
        ]
    }


def invalidate_cache():
    """Invalidate the personas cache to force reload."""
    global _personas_cache, _personas_cache_time
    _personas_cache = None
    _personas_cache_time = 0
