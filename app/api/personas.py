"""Persona management and brand voice preview API."""
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import get_current_user_id
from app.database import get_db
from app.db_utils import fetchall
from app.services.persona_manager import get_persona, list_personas, load_personas
from app.services.ai_client import call_llm_text
from app.utils.json_parser import parse_llm_json

router = APIRouter()


class BrandVoicePreviewRequest(BaseModel):
    """Request for brand voice preview."""
    sample_text: str
    persona_id: str


class BrandVoicePreviewResponse(BaseModel):
    """Response from brand voice preview."""
    original_text: str
    transformed_text: str
    changes_summary: list[str]
    persona_applied: dict


@router.get("/personas")
async def get_default_personas(
    user_id: int = Depends(get_current_user_id),
):
    """Get default personas only."""
    personas = await list_personas()
    return {"personas": personas}


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
        "language_level": "Professional",
        "tone_preferences": json.loads(row["tone_preferences"]) if row["tone_preferences"] else None,
        "content_preferences": json.loads(row["content_preferences"]) if row["content_preferences"] else None,
        "is_default": bool(row["is_default"]),
        "is_custom": True,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.get("/personas/all")
async def get_all_personas(
    user_id: int = Depends(get_current_user_id),
):
    """
    Get all personas (both default from JSON and custom from database).
    This endpoint is used to populate persona dropdowns across the app.
    """
    # Get default personas from JSON
    defaults_data = await load_personas()
    default_personas = []
    for p in defaults_data.get("personas", []):
        persona = dict(p)
        persona["is_default"] = True
        persona["is_custom"] = False
        default_personas.append(persona)

    # Get custom personas from database
    async with get_db() as db:
        rows = await fetchall(
            db,
            "SELECT * FROM personas WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )

    custom_personas = [_row_to_persona_dict(row) for row in rows]

    return {
        "default_personas": default_personas,
        "custom_personas": custom_personas,
        "all_personas": custom_personas + default_personas,
    }


@router.get("/personas/{persona_id}")
async def get_persona_details(
    persona_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """Get details for a specific persona."""
    persona = await get_persona(persona_id, user_id=user_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


@router.post("/personas/preview-voice", response_model=BrandVoicePreviewResponse)
async def preview_brand_voice(
    request: BrandVoicePreviewRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Preview how content will sound with a specific persona's brand voice applied.

    This is a quick preview that doesn't run the full pipeline - just transforms
    sample text to demonstrate the brand voice transformation.
    """
    if not request.sample_text or len(request.sample_text) < 10:
        raise HTTPException(status_code=400, detail="Sample text must be at least 10 characters")

    if len(request.sample_text) > 2000:
        raise HTTPException(status_code=400, detail="Sample text must be less than 2000 characters")

    # Pass user_id to get_persona so it can find custom personas
    persona = await get_persona(request.persona_id, user_id=user_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    # Build a focused prompt for quick brand voice transformation
    prompt = f"""Transform this text to match the following brand voice profile.

TARGET AUDIENCE:
- Title: {persona['title']}
- Language Level: {persona.get('language_level', 'Professional')}
- Priorities: {', '.join(persona.get('priorities', []))}
- Content Tone: {persona.get('content_preferences', {}).get('tone', 'Professional')}
- Preferred Length: {persona.get('content_preferences', {}).get('length', 'Medium')}

TRANSFORMATION GUIDELINES:
1. Adjust vocabulary and complexity for the target audience
2. Emphasize their priorities and pain points
3. Match the preferred tone and length
4. Keep the core message intact
5. Make it actionable for this specific audience

ORIGINAL TEXT:
{request.sample_text}

OUTPUT FORMAT (valid JSON):
{{
  "transformed_text": "The transformed text matching the brand voice",
  "changes_summary": [
    "Simplified technical jargon to executive-friendly language",
    "Added ROI-focused framing",
    "Shortened for time-constrained readers"
  ]
}}"""

    try:
        response_text, _, _, _ = await call_llm_text(
            prompt=prompt,
            step="drafting",
            max_tokens=1000,
            response_format="json",
        )

        result = parse_llm_json(response_text, context="brand voice preview")

        return BrandVoicePreviewResponse(
            original_text=request.sample_text,
            transformed_text=result.get("transformed_text", request.sample_text),
            changes_summary=result.get("changes_summary", []),
            persona_applied={
                "id": persona["id"],
                "title": persona["title"],
                "tone": persona.get("content_preferences", {}).get("tone", "Professional"),
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to transform text: {str(e)}"
        )
