"""Persona management and brand voice preview API."""
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import google.generativeai as genai

from app.config import get_settings, calculate_cost
from app.api.auth import get_current_user_id
from app.services.persona_manager import get_persona, list_personas
from app.utils.retry import retry_async

router = APIRouter()
settings = get_settings()


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
async def get_all_personas(
    user_id: int = Depends(get_current_user_id),
):
    """Get all available personas."""
    personas = await list_personas()
    return {"personas": personas}


@router.get("/personas/{persona_id}")
async def get_persona_details(
    persona_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """Get details for a specific persona."""
    persona = await get_persona(persona_id)
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

    persona = await get_persona(request.persona_id)
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

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    async def do_transform():
        return model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                max_output_tokens=1000,
            )
        )

    try:
        response = await retry_async(
            do_transform,
            max_retries=2,
            base_delay=1.0,
            context="preview_brand_voice",
        )

        result = json.loads(response.text)

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
