"""Content distillation service - Step 0 of the pipeline."""
import json
import uuid
from typing import Tuple

from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.services.prompt_manager import get_rendered_prompt
from app.services.persona_manager import get_persona
from app.utils.json_parser import parse_llm_json


async def distill_content(
    cleaned_transcript: str,
    target_persona_id: str,
    job_id: str,
    user_id: int,
) -> Tuple[list[dict], float]:
    """
    Extract reusable content stills from transcript.

    Stills are categorized as: data, insight, story, problem, solution, quote.
    Each still is scored for relevance to the target persona (if provided).

    Returns (stills_list, cost) tuple.
    """
    # Get persona details (optional for Quick Distill)
    persona = None
    if target_persona_id and target_persona_id not in ("general", "none", ""):
        persona = await get_persona(target_persona_id, user_id=user_id)

    # Build variables based on whether we have a persona
    if persona:
        variables = {
            "target_persona_title": persona["title"],
            "persona_pain_points": ", ".join(persona["pain_points"]),
            "persona_priorities": ", ".join(persona["priorities"]),
            "cleaned_transcript": cleaned_transcript,
        }
    else:
        # Generic distillation without persona context
        variables = {
            "target_persona_title": "general audience",
            "persona_pain_points": "common business challenges, efficiency, growth, staying competitive",
            "persona_priorities": "actionable insights, practical solutions, valuable information",
            "cleaned_transcript": cleaned_transcript,
        }

    prompt, config = await get_rendered_prompt("distillation", variables)

    # Add JSON output instruction
    full_prompt = prompt + """

IMPORTANT - EXTRACT QUOTES:
Look for memorable, impactful direct quotes from speakers in the source material.
These are exact words someone said that could be used in content like:
"As [Speaker] said: '...'" or as a pull quote.
Include the speaker/attribution when available.

TOPIC EXTRACTION:
For each still, identify 2-3 high-level topic keywords that categorize this content.
Topics should be broad, searchable themes like: "marketing", "leadership", "AI", "sales", "productivity", "customer success", "growth", "strategy", etc.
These help users find related content across different campaigns.

OUTPUT FORMAT:
Return valid JSON with this structure:
{
  "stills": [
    {
      "type": "data|insight|story|problem|solution|quote",
      "content": "The actual content extracted (for quotes, use the exact verbatim text)",
      "source_location": "timestamp or section reference",
      "relevance_to_persona": 1-5,
      "why_relevant": "Brief explanation",
      "tags": ["tag1", "tag2"],
      "topics": ["topic1", "topic2"],
      "speaker": "Name of person who said this (for quotes only, null otherwise)"
    }
  ],
  "summary": "Brief summary of what was extracted",
  "recommended_distribution": {
    "linkedin": ["still indexes best for LinkedIn"],
    "blog": ["still indexes best for blog"],
    "email": ["still indexes best for email"]
  }
}"""

    # Call LLM via unified client
    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=full_prompt,
        step="distillation",
        max_tokens=config.get("max_tokens", 4096),
        response_format="json",
        job_id=job_id,
        user_id=user_id,
    )

    # Use robust JSON parser that handles common LLM output issues
    try:
        result = parse_llm_json(response_text, context="distillation response")
    except ValueError as e:
        # If parsing still fails, return empty stills with error info
        result = {
            "stills": [],
            "summary": f"Could not parse LLM response: {str(e)}",
            "recommended_distribution": {}
        }

    # Process stills
    stills = []
    # Handle both "stills" and "atoms" keys for backwards compatibility with prompts
    still_data_list = result.get("stills", result.get("atoms", []))
    for still_data in still_data_list:
        # Build persona relevance - use "general" if no persona specified
        relevance_key = target_persona_id if persona else "general"
        still = {
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "user_id": user_id,
            "still_type": still_data.get("type", "insight"),
            "content": still_data.get("content", ""),
            "source_location": still_data.get("source_location"),
            "tags": still_data.get("tags", []),
            "topics": still_data.get("topics", []),
            "persona_relevance": {
                relevance_key: still_data.get("relevance_to_persona", 3)
            },
            "why_relevant": still_data.get("why_relevant"),
            "quote_attribution": still_data.get("speaker"),  # For quote stills
        }
        stills.append(still)

    # Calculate cost
    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return stills, cost


def select_stills_for_content_type(
    stills: list[dict],
    content_type: str,
    persona_id: str,
    count: int = 5,
) -> list[dict]:
    """
    Select the best stills for a specific content type.

    Prioritizes by persona relevance and still type appropriateness.
    """
    # Type preferences by content type
    type_preferences = {
        "linkedin": ["data", "insight", "story", "quote"],
        "blog": ["problem", "insight", "solution", "data", "story", "quote"],
        "email": ["problem", "solution", "data"],
    }

    preferred_types = type_preferences.get(content_type, ["insight", "data"])

    # Score stills
    scored_stills = []
    for still in stills:
        score = 0

        # Persona relevance (0-5)
        relevance = still.get("persona_relevance", {}).get(persona_id, 3)
        score += relevance * 2

        # Type preference bonus
        still_type = still.get("still_type", "insight")
        if still_type in preferred_types:
            score += (len(preferred_types) - preferred_types.index(still_type))

        scored_stills.append((score, still))

    # Sort by score descending and return top N
    scored_stills.sort(key=lambda x: x[0], reverse=True)

    return [still for _, still in scored_stills[:count]]


def group_stills_by_type(stills: list[dict]) -> dict[str, list[dict]]:
    """Group stills by their type for easier access in prompts."""
    grouped = {
        "data": [],
        "insight": [],
        "story": [],
        "problem": [],
        "solution": [],
        "quote": [],
    }

    for still in stills:
        still_type = still.get("still_type", "insight")
        if still_type in grouped:
            grouped[still_type].append(still)

    return grouped
