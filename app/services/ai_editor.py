"""AI-powered content editor service for Workshop."""
import json
import logging
from typing import List, Dict, Optional, Tuple
from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchall

settings = get_settings()
logger = logging.getLogger(__name__)
from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.services.brand_voice_analyzer import get_brand_voice_profile
from app.utils.json_parser import parse_llm_json

# Default system prompt for the AI editor
DEFAULT_EDITOR_PROMPT = """You are a skilled content editor helping refine marketing content. Your role is to make LIGHT, targeted edits that improve the content while preserving the author's voice and intent.

EDITING GUIDELINES:
1. Make minimal, surgical edits - never rewrite more than 20-30% of the content
2. Preserve the author's unique voice and style
3. Focus on clarity, impact, and engagement
4. Fix grammar and punctuation errors
5. Improve flow and readability
6. Strengthen hooks and calls-to-action when requested
7. Never add information that wasn't implied in the original
8. Never change the core message or meaning

BRAND VOICE (when provided):
- Match the vocabulary patterns and tone markers
- Use preferred phrases and avoid restricted phrases
- Maintain the specified tone for the platform

OUTPUT FORMAT:
Return a JSON object with an array of suggested edits. Each edit should identify the original text and the suggested replacement, along with a brief explanation.

{
  "suggestions": [
    {
      "id": 1,
      "original_text": "The exact text to replace",
      "suggested_text": "The improved version",
      "explanation": "Brief reason for this change",
      "type": "grammar|clarity|impact|tone|structure"
    }
  ],
  "summary": "Brief overall summary of changes made"
}

IMPORTANT: Only suggest changes that meaningfully improve the content. If the content is already good, return fewer or no suggestions."""


async def get_editor_config() -> Dict[str, str]:
    """Get AI editor configuration from database."""
    async with get_db() as db:
        rows = await fetchall(
            db,
            "SELECT config_key, config_value FROM ai_editor_config",
            ()
        )

        config = {}
        for row in rows:
            config[row["config_key"]] = row["config_value"]

        # Return defaults if not configured
        if "system_prompt" not in config:
            config["system_prompt"] = DEFAULT_EDITOR_PROMPT
        if "model" not in config:
            config["model"] = "google/gemini-2.5-flash-preview"

        return config


async def save_editor_config(config_key: str, config_value: str) -> None:
    """Save AI editor configuration to database."""
    async with get_db() as db:
        if settings.use_postgres:
            await db.execute(
                """
                INSERT INTO ai_editor_config (config_key, config_value, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT(config_key) DO UPDATE SET
                    config_value = EXCLUDED.config_value,
                    updated_at = NOW()
                """,
                config_key, config_value
            )
        else:
            await db.execute(
                """
                INSERT INTO ai_editor_config (config_key, config_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(config_key) DO UPDATE SET
                    config_value = excluded.config_value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (config_key, config_value)
            )
            await db.commit()


async def get_ai_edit_suggestions(
    content: str,
    user_prompt: str,
    user_id: int,
    persona_id: Optional[str] = None,
    content_type: Optional[str] = None,
) -> Tuple[Dict, float]:
    """
    Get AI editing suggestions for content.

    Args:
        content: The content to edit
        user_prompt: User's editing instruction (e.g., "make it punchier")
        user_id: User ID for brand voice lookup
        persona_id: Optional target persona ID
        content_type: Optional content type (linkedin, blog, email)

    Returns:
        (suggestions_dict, cost)
    """
    # Get editor config
    config = await get_editor_config()
    system_prompt = config.get("system_prompt", DEFAULT_EDITOR_PROMPT)

    # Get brand voice profile if available
    brand_voice_context = ""
    try:
        profile = await get_brand_voice_profile(user_id)
        if profile:
            brand_voice_context = f"""
BRAND VOICE PROFILE:
- Tone: {profile.get('overall_summary', 'Professional and engaging')}
- Vocabulary Patterns: {json.dumps(profile.get('vocabulary_patterns', {}))}
- Phrases to Use: {json.dumps(profile.get('phrases_to_use', []))}
- Phrases to Avoid: {json.dumps(profile.get('phrases_to_avoid', []))}
"""
    except Exception as e:
        logger.warning(f"Failed to fetch brand voice for user {user_id}: {e}")

    # Get persona context if provided
    persona_context = ""
    if persona_id:
        try:
            from app.services.persona_manager import get_persona
            persona = await get_persona(persona_id, user_id=user_id)
            if persona:
                persona_context = f"""
TARGET PERSONA:
- Title: {persona.get('title', 'General audience')}
- Pain Points: {json.dumps(persona.get('pain_points', []))}
- Goals: {json.dumps(persona.get('goals', []))}
- Preferred Tone: {persona.get('content_preferences', {}).get('tone', 'Professional')}
"""
        except Exception as e:
            logger.warning(f"Failed to fetch persona {persona_id} for user {user_id}: {e}")

    # Build the full prompt
    full_prompt = f"""{system_prompt}

{brand_voice_context}

{persona_context}

CONTENT TYPE: {content_type or 'general'}

USER REQUEST: {user_prompt}

CONTENT TO EDIT:
{content}

Provide your editing suggestions as valid JSON."""

    # Call the LLM
    response_text, input_tokens, output_tokens, model_used = await call_llm_text(
        prompt=full_prompt,
        step="workshop_ai_edit",
        max_tokens=2048,
        response_format="json",
    )

    # Parse response
    try:
        result = parse_llm_json(response_text, context="ai_editor")
    except Exception:
        result = {
            "suggestions": [],
            "summary": "Failed to parse AI response",
            "error": True
        }

    # Calculate cost
    cost = calculate_openrouter_cost(model_used, input_tokens, output_tokens)

    return result, cost
