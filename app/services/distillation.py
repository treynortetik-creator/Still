"""Content distillation service - Step 0 of the pipeline."""
import json
import uuid
from datetime import datetime
from typing import Optional, Tuple

from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.services.prompt_manager import get_rendered_prompt
from app.services.persona_manager import get_persona
from app.utils.json_parser import parse_llm_json


# All 10 still types
ALL_STILL_TYPES = [
    "data", "insight", "story", "problem", "solution", "quote",
    "framework", "definition", "question", "proof_point"
]


def _parse_expiration_date(date_value) -> Optional[str]:
    """
    Parse expiration date from LLM response.

    Accepts various formats and returns YYYY-MM-DD string or None.
    """
    if not date_value or date_value in ("null", "None", ""):
        return None

    if isinstance(date_value, str):
        # Try to parse YYYY-MM-DD format
        try:
            parsed = datetime.strptime(date_value, "%Y-%m-%d")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

        # Try other common formats
        for fmt in ["%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]:
            try:
                parsed = datetime.strptime(date_value, fmt)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue

    return None


async def distill_content(
    cleaned_transcript: str,
    target_persona_id: str,
    job_id: str,
    user_id: int,
    source_of_truth: Optional[dict] = None,
) -> Tuple[list[dict], float]:
    """
    Extract reusable content stills from transcript.

    Stills are categorized into 10 types: data, insight, story, problem, solution,
    quote, framework, definition, question, proof_point.
    Each still is scored for relevance to the target persona (if provided).

    Args:
        cleaned_transcript: The transcript text to distill
        target_persona_id: ID of target persona (optional)
        job_id: ID of the processing job
        user_id: ID of the user
        source_of_truth: Optional dict with Source of Truth context containing:
            - core_narratives: JSON array of narrative objects
            - primary_pain_point: Main pain point string
            - the_promise: Brand promise string

    Returns (stills_list, cost) tuple.
    """
    # Get persona details (optional for Quick Distill)
    persona = None
    if target_persona_id and target_persona_id not in ("general", "none", ""):
        persona = await get_persona(target_persona_id, user_id=user_id)

    # Extract Source of Truth values (with defaults)
    sot = source_of_truth or {}
    core_narratives = sot.get("core_narratives", [])
    primary_pain_point = sot.get("primary_pain_point", "")
    the_promise = sot.get("the_promise", "")

    # Format core_narratives as JSON string if it's a list
    if isinstance(core_narratives, list):
        core_narratives_str = json.dumps(core_narratives, indent=2)
    else:
        core_narratives_str = str(core_narratives) if core_narratives else "[]"

    # Build variables based on whether we have a persona
    if persona:
        variables = {
            "target_persona_title": persona["title"],
            "persona_pain_points": ", ".join(persona["pain_points"]),
            "persona_priorities": ", ".join(persona["priorities"]),
            "cleaned_transcript": cleaned_transcript,
            # Source of Truth context
            "core_narratives": core_narratives_str,
            "primary_pain_point": primary_pain_point,
            "the_promise": the_promise,
        }
    else:
        # Generic distillation without persona context
        variables = {
            "target_persona_title": "general audience",
            "persona_pain_points": "common business challenges, efficiency, growth, staying competitive",
            "persona_priorities": "actionable insights, practical solutions, valuable information",
            "cleaned_transcript": cleaned_transcript,
            # Source of Truth context
            "core_narratives": core_narratives_str,
            "primary_pain_point": primary_pain_point,
            "the_promise": the_promise,
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
      "type": "data|insight|story|problem|solution|quote|framework|definition|question|proof_point",
      "content": "The actual content extracted (for quotes, use the exact verbatim text)",
      "source_location": "timestamp or section reference",
      "relevance_to_persona": 1-5,
      "why_relevant": "Brief explanation",
      "tags": ["tag1", "tag2"],
      "topics": ["topic1", "topic2"],
      "speaker": "Name of person who said this (for quotes only, null otherwise)",
      "best_formats": ["linkedin", "email", "blog"],
      "funnel_stage": "awareness|consideration|decision",
      "expiration_date": "YYYY-MM-DD or null if evergreen"
    }
  ],
  "summary": "Brief summary of what was extracted",
  "recommended_distribution": {
    "linkedin": ["still indexes best for LinkedIn"],
    "blog": ["still indexes best for blog"],
    "email": ["still indexes best for email"]
  }
}

STILL TYPE GUIDELINES:
- data: Statistics, metrics, research findings
- insight: Observations, analysis, lessons learned
- story: Anecdotes, case studies, examples
- problem: Pain points, challenges, obstacles
- solution: Answers, fixes, approaches
- quote: Direct verbatim quotes from speakers
- framework: Step-by-step processes, methodologies
- definition: Key term explanations, concepts
- question: Thought-provoking questions, prompts
- proof_point: Credentials, testimonials, social proof"""

    # Call LLM via unified client (no token limit - use model's maximum)
    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=full_prompt,
        step="distillation",
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

        # Parse expiration_date if provided
        expiration_date = _parse_expiration_date(still_data.get("expiration_date"))

        # Parse best_formats - ensure it's a list
        best_formats = still_data.get("best_formats", [])
        if not isinstance(best_formats, list):
            best_formats = []

        # Parse funnel_stage - validate against known values
        funnel_stage = still_data.get("funnel_stage")
        valid_funnel_stages = ["awareness", "consideration", "decision"]
        if funnel_stage and funnel_stage not in valid_funnel_stages:
            funnel_stage = None

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
            # New lifecycle fields
            "best_formats": best_formats,
            "funnel_stage": funnel_stage,
            "expiration_date": expiration_date,
        }
        stills.append(still)

    # Calculate cost
    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return stills, cost


def format_stills_for_review(stills: list[dict]) -> str:
    """Format first pass stills for display in second pass prompt."""
    if not stills:
        return "No stills extracted in first pass."

    lines = []
    for i, still in enumerate(stills, 1):
        still_type = still.get("still_type", "insight")
        content = still.get("content", "")[:200]  # Truncate long content
        source = still.get("source_location", "unknown")
        lines.append(f"{i}. [{still_type.upper()}] {content} (source: {source})")

    return "\n".join(lines)


async def distill_content_pass2(
    cleaned_transcript: str,
    first_pass_stills: list[dict],
    target_persona_id: str,
    job_id: str,
    user_id: int,
    source_of_truth: Optional[dict] = None,
) -> Tuple[list[dict], float]:
    """
    Second pass extraction - finds content overlooked in first pass.

    Reviews what was already extracted and looks for:
    - Additional quotes from different speakers
    - Missed data points/statistics
    - Brief anecdotes glossed over
    - Secondary problems/solutions
    - Insights buried in longer passages
    - New still types: frameworks, definitions, questions, proof_points

    Args:
        cleaned_transcript: The transcript text to distill
        first_pass_stills: Stills extracted in first pass
        target_persona_id: ID of target persona (optional)
        job_id: ID of the processing job
        user_id: ID of the user
        source_of_truth: Optional dict with Source of Truth context

    Returns (stills_list, cost) tuple.
    """
    # Get persona details (optional)
    persona = None
    if target_persona_id and target_persona_id not in ("general", "none", ""):
        persona = await get_persona(target_persona_id, user_id=user_id)

    # Format first pass stills for the prompt
    first_pass_summary = format_stills_for_review(first_pass_stills)

    # Extract Source of Truth values (with defaults)
    sot = source_of_truth or {}
    core_narratives = sot.get("core_narratives", [])
    primary_pain_point = sot.get("primary_pain_point", "")
    the_promise = sot.get("the_promise", "")

    # Format core_narratives as JSON string if it's a list
    if isinstance(core_narratives, list):
        core_narratives_str = json.dumps(core_narratives, indent=2)
    else:
        core_narratives_str = str(core_narratives) if core_narratives else "[]"

    # Build variables based on whether we have a persona
    if persona:
        variables = {
            "target_persona_title": persona["title"],
            "persona_pain_points": ", ".join(persona["pain_points"]),
            "persona_priorities": ", ".join(persona["priorities"]),
            "cleaned_transcript": cleaned_transcript,
            "first_pass_stills": first_pass_summary,
            "first_pass_count": len(first_pass_stills),
            # Source of Truth context
            "core_narratives": core_narratives_str,
            "primary_pain_point": primary_pain_point,
            "the_promise": the_promise,
        }
    else:
        variables = {
            "target_persona_title": "general audience",
            "persona_pain_points": "common business challenges, efficiency, growth, staying competitive",
            "persona_priorities": "actionable insights, practical solutions, valuable information",
            "cleaned_transcript": cleaned_transcript,
            "first_pass_stills": first_pass_summary,
            "first_pass_count": len(first_pass_stills),
            # Source of Truth context
            "core_narratives": core_narratives_str,
            "primary_pain_point": primary_pain_point,
            "the_promise": the_promise,
        }

    prompt, config = await get_rendered_prompt("distillation_pass2", variables)

    # Add JSON output instruction
    full_prompt = prompt + """

OUTPUT FORMAT:
Return valid JSON with this structure:
{
  "stills": [
    {
      "type": "data|insight|story|problem|solution|quote|framework|definition|question|proof_point",
      "content": "The actual content extracted (for quotes, use exact verbatim text)",
      "source_location": "timestamp or section reference",
      "relevance_to_persona": 1-5,
      "why_relevant": "Brief explanation",
      "tags": ["tag1", "tag2"],
      "topics": ["topic1", "topic2"],
      "speaker": "Name of person who said this (for quotes only, null otherwise)",
      "best_formats": ["linkedin", "email", "blog"],
      "funnel_stage": "awareness|consideration|decision",
      "expiration_date": "YYYY-MM-DD or null if evergreen"
    }
  ],
  "summary": "Brief summary of what additional content was found"
}

STILL TYPE GUIDELINES:
- data: Statistics, metrics, research findings
- insight: Observations, analysis, lessons learned
- story: Anecdotes, case studies, examples
- problem: Pain points, challenges, obstacles
- solution: Answers, fixes, approaches
- quote: Direct verbatim quotes from speakers
- framework: Step-by-step processes, methodologies
- definition: Key term explanations, concepts
- question: Thought-provoking questions, prompts
- proof_point: Credentials, testimonials, social proof

Remember: ONLY include NEW stills not already in the first pass. Quality over quantity."""

    # Call LLM via unified client
    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=full_prompt,
        step="distillation_pass2",
        response_format="json",
        job_id=job_id,
        user_id=user_id,
    )

    # Use robust JSON parser
    try:
        result = parse_llm_json(response_text, context="distillation pass 2 response")
    except ValueError as e:
        result = {
            "stills": [],
            "summary": f"Could not parse LLM response: {str(e)}",
        }

    # Process stills
    stills = []
    still_data_list = result.get("stills", [])
    for still_data in still_data_list:
        relevance_key = target_persona_id if persona else "general"

        # Parse expiration_date if provided
        expiration_date = _parse_expiration_date(still_data.get("expiration_date"))

        # Parse best_formats - ensure it's a list
        best_formats = still_data.get("best_formats", [])
        if not isinstance(best_formats, list):
            best_formats = []

        # Parse funnel_stage - validate against known values
        funnel_stage = still_data.get("funnel_stage")
        valid_funnel_stages = ["awareness", "consideration", "decision"]
        if funnel_stage and funnel_stage not in valid_funnel_stages:
            funnel_stage = None

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
            "quote_attribution": still_data.get("speaker"),
            # New lifecycle fields
            "best_formats": best_formats,
            "funnel_stage": funnel_stage,
            "expiration_date": expiration_date,
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
    """Group stills by their type for easier access in prompts.

    Includes all 10 still types:
    - Original 6: data, insight, story, problem, solution, quote
    - New 4: framework, definition, question, proof_point
    """
    # Initialize with all 10 still types
    grouped = {still_type: [] for still_type in ALL_STILL_TYPES}

    for still in stills:
        still_type = still.get("still_type", "insight")
        if still_type in grouped:
            grouped[still_type].append(still)

    return grouped
