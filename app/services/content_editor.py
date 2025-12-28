"""Content editor service for tone adjustments and AI post-editing."""
import json
import logging
from typing import Tuple, Optional

from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.utils.json_parser import parse_llm_json

logger = logging.getLogger(__name__)


# Tone presets with descriptions and instructions
TONE_PRESETS = {
    "professional": {
        "label": "Professional",
        "description": "Formal, polished, industry-appropriate language",
        "instructions": "Rewrite in a professional, formal tone. Use industry-standard terminology, avoid slang or casual expressions, maintain credibility and authority."
    },
    "casual": {
        "label": "Casual",
        "description": "Friendly, conversational, approachable",
        "instructions": "Rewrite in a casual, conversational tone. Use friendly language, contractions, and a warm approachable style as if speaking to a colleague."
    },
    "bold": {
        "label": "Bold",
        "description": "Confident, direct, attention-grabbing",
        "instructions": "Rewrite in a bold, confident tone. Use strong statements, powerful words, and direct language that commands attention. Don't hedge or qualify unnecessarily."
    },
    "empathetic": {
        "label": "Empathetic",
        "description": "Understanding, supportive, emotionally intelligent",
        "instructions": "Rewrite in an empathetic, understanding tone. Acknowledge challenges, show compassion, and connect emotionally with the reader's situation."
    },
    "educational": {
        "label": "Educational",
        "description": "Informative, clear, teaching-focused",
        "instructions": "Rewrite in an educational tone. Focus on clarity, explain concepts thoroughly, and guide the reader through the information step by step."
    },
    "urgent": {
        "label": "Urgent",
        "description": "Time-sensitive, action-oriented, compelling",
        "instructions": "Rewrite with a sense of urgency. Emphasize time-sensitivity, create momentum, and compel immediate action without being pushy."
    },
    "storytelling": {
        "label": "Storytelling",
        "description": "Narrative-driven, engaging, memorable",
        "instructions": "Rewrite in a storytelling style. Use narrative elements, paint pictures with words, and create an engaging flow that draws readers in."
    },
    "data_driven": {
        "label": "Data-Driven",
        "description": "Analytical, fact-based, evidence-focused",
        "instructions": "Rewrite in a data-driven tone. Emphasize facts, statistics, and evidence. Be precise and analytical while maintaining readability."
    },
    "inspirational": {
        "label": "Inspirational",
        "description": "Motivating, uplifting, vision-oriented",
        "instructions": "Rewrite in an inspirational tone. Motivate the reader, paint a compelling vision, and use uplifting language that energizes action."
    },
    "concise": {
        "label": "Concise",
        "description": "Brief, to-the-point, no fluff",
        "instructions": "Rewrite to be more concise. Remove unnecessary words, get to the point quickly, and deliver maximum value in minimum words."
    }
}


async def adjust_tone(
    content: str,
    tone_preset: str,
    content_type: str = "linkedin",
    custom_instructions: Optional[str] = None,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[str, float]:
    """
    Adjust the tone of content using a preset or custom instructions.

    Args:
        content: The original content to adjust
        tone_preset: One of the TONE_PRESETS keys
        content_type: Type of content (linkedin, blog, email)
        custom_instructions: Optional custom instructions (overrides preset if provided)
        job_id: Optional job ID for logging
        user_id: Optional user ID for logging

    Returns:
        (adjusted_content, cost) tuple
    """
    # Get tone instructions
    if custom_instructions:
        tone_instructions = custom_instructions
        tone_name = "Custom"
    elif tone_preset in TONE_PRESETS:
        tone_instructions = TONE_PRESETS[tone_preset]["instructions"]
        tone_name = TONE_PRESETS[tone_preset]["label"]
    else:
        raise ValueError(f"Unknown tone preset: {tone_preset}")

    # Content type context
    content_context = {
        "linkedin": "This is a LinkedIn post. Keep it optimized for LinkedIn's format and audience.",
        "blog": "This is a blog post. Maintain the structure with headings and proper formatting.",
        "email": "This is an email. Keep the subject line and maintain email conventions.",
        "email_sequence": "This is part of an email sequence. Maintain the email format and purpose."
    }.get(content_type, "")

    prompt = f"""You are an expert content editor specializing in tone adjustment.

TASK: Adjust the tone of the following content to be more "{tone_name}".

TONE INSTRUCTIONS:
{tone_instructions}

CONTENT TYPE CONTEXT:
{content_context}

ORIGINAL CONTENT:
{content}

RULES:
1. Preserve the core message and key points
2. Maintain the same structure and length (approximately)
3. Keep any statistics, data, or quotes intact
4. Adjust vocabulary, sentence structure, and phrasing to match the new tone
5. Do NOT add new information not present in the original
6. Do NOT remove important content

Return ONLY the adjusted content, nothing else. No explanations or preamble."""

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=prompt,
        step="editing",
        max_tokens=4096,
        job_id=job_id,
        user_id=user_id,
    )

    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return response_text.strip(), cost


async def apply_edit_instructions(
    content: str,
    instructions: str,
    content_type: str = "linkedin",
    job_id: str = None,
    user_id: int = None,
) -> Tuple[str, str, float]:
    """
    Apply custom edit instructions to content.

    Args:
        content: The original content to edit
        instructions: User's edit instructions (e.g., "make shorter", "add more stats")
        content_type: Type of content
        job_id: Optional job ID
        user_id: Optional user ID

    Returns:
        (edited_content, change_summary, cost) tuple
    """
    prompt = f"""You are an expert content editor. Apply the user's requested changes to this content.

USER'S EDIT REQUEST:
{instructions}

CONTENT TYPE: {content_type}

ORIGINAL CONTENT:
{content}

RULES:
1. Apply the requested changes while preserving the core message
2. Maintain appropriate length for the content type
3. Keep the same general tone unless told otherwise
4. Preserve any important data, statistics, or quotes
5. Make the changes feel natural and professional

OUTPUT FORMAT (valid JSON):
{{
    "edited_content": "The full edited content here...",
    "change_summary": "Brief summary of changes made (1-2 sentences)"
}}"""

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=prompt,
        step="editing",
        max_tokens=4096,
        response_format="json",
        job_id=job_id,
        user_id=user_id,
    )

    try:
        result = parse_llm_json(response_text, context="content editor")
    except ValueError as e:
        logger.warning(f"Failed to parse content editor response: {e}")
        # Fallback: treat entire response as edited content
        result = {
            "edited_content": response_text.strip(),
            "change_summary": "Applied requested changes"
        }

    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return result["edited_content"], result.get("change_summary", ""), cost


async def regenerate_section(
    content: str,
    section_to_regenerate: str,
    instructions: str,
    content_type: str = "linkedin",
    job_id: str = None,
    user_id: int = None,
) -> Tuple[str, float]:
    """
    Regenerate a specific section of content.

    Args:
        content: The full original content
        section_to_regenerate: The specific section/paragraph to regenerate
        instructions: How to regenerate it
        content_type: Type of content
        job_id: Optional job ID
        user_id: Optional user ID

    Returns:
        (full_content_with_new_section, cost) tuple
    """
    prompt = f"""You are an expert content editor. Regenerate a specific section of this content.

FULL CONTENT:
{content}

SECTION TO REGENERATE:
{section_to_regenerate}

REGENERATION INSTRUCTIONS:
{instructions}

CONTENT TYPE: {content_type}

RULES:
1. Replace the specified section with a new version following the instructions
2. Keep all other parts of the content unchanged
3. Ensure the new section flows naturally with the rest
4. Maintain consistent tone and style

Return the FULL content with the regenerated section in place. No explanations."""

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=prompt,
        step="editing",
        max_tokens=4096,
        job_id=job_id,
        user_id=user_id,
    )

    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return response_text.strip(), cost


def get_tone_presets() -> list[dict]:
    """Get all available tone presets for the frontend."""
    return [
        {
            "id": key,
            "label": value["label"],
            "description": value["description"]
        }
        for key, value in TONE_PRESETS.items()
    ]
