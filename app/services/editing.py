"""Content editing service - Step 2 of the pipeline."""
import json
from typing import Tuple

from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.services.prompt_manager import get_rendered_prompt
from app.services.persona_manager import get_persona
from app.services.brand_voice_analyzer import get_brand_voice_template_vars
from app.services.source_of_truth import get_source_of_truth_template_vars
from app.utils.json_parser import parse_llm_json

# Default persona values when no persona is selected
DEFAULT_PERSONA = {
    "title": "General Professional Audience",
    "priorities": ["actionable insights", "practical solutions", "valuable information"],
    "pain_points": ["common business challenges", "efficiency", "growth"],
    "language_level": "Professional",
    "content_preferences": {"tone": "Professional"},
}


async def edit_for_audience(
    draft_content: str,
    persona_id: str,
    content_type: str = "linkedin",
    job_id: str = None,
    user_id: int = None,
) -> Tuple[dict, float]:
    """
    Edit content for target audience - simplify jargon, check guardrails, improve flow.

    Returns (edited_result, cost) tuple.
    """
    # Get persona or use defaults if not provided
    persona = None
    if persona_id:
        persona = await get_persona(persona_id, user_id=user_id)
    if not persona:
        persona = DEFAULT_PERSONA

    variables = {
        "persona_title": persona["title"],
        "persona_language_level": persona.get("language_level", "Professional"),
        "persona_priorities": ", ".join(persona["priorities"]),
        "draft_from_step1": draft_content,
    }

    # Inject brand voice variables if user_id provided
    if user_id:
        brand_vars = await get_brand_voice_template_vars(user_id, content_type=content_type)
        variables.update(brand_vars)

    # Inject SOT variables if job_id provided
    if job_id:
        sot_vars = await get_source_of_truth_template_vars(job_id)
        variables.update(sot_vars)

    prompt, config = await get_rendered_prompt("audience_edit", variables)

    # Add output instruction
    full_prompt = prompt + f"""

CONTENT TYPE: {content_type}

OUTPUT FORMAT (valid JSON):
{{
  "edited_content": "The fully edited content",
  "changes_made": [
    {{"type": "simplification|flow|tone|guardrail", "description": "What was changed"}}
  ],
  "warnings": ["Any warnings about content that needs attention"],
  "guardrails_status": {{
    "active_voice": true,
    "empowerment_close": true,
    "no_competitors": true,
    "appropriate_tone": true,
    "citations_flagged": true
  }},
  "citations_needed": ["List of claims that need citation/verification"]
}}"""

    # Call LLM via unified client (no token limit)
    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=full_prompt,
        step="editing",
        response_format="json",
        job_id=job_id,
        user_id=user_id,
    )

    # Use robust JSON parser that handles common LLM output issues
    try:
        result = parse_llm_json(response_text, context="editing response")
    except ValueError as e:
        # If parsing still fails, return a minimal result with the raw content
        # This allows the pipeline to continue rather than fail completely
        result = {
            "edited_content": draft_content,  # Return original content
            "changes_made": [],
            "warnings": [f"Could not parse LLM response: {str(e)}"],
            "guardrails_status": {},
            "citations_needed": []
        }

    # Calculate cost
    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return result, cost


async def batch_edit_content(
    drafts: list[dict],
    persona_id: str,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[list[dict], float]:
    """
    Edit multiple drafts for audience.

    Returns (edited_drafts, total_cost) tuple.
    """
    edited_results = []
    total_cost = 0.0

    for draft in drafts:
        content = draft.get("content", "")
        content_type = draft.get("content_type", "linkedin")

        if not content:
            edited_results.append(draft)
            continue

        result, cost = await edit_for_audience(
            content, persona_id, content_type, job_id, user_id
        )
        total_cost += cost

        edited_draft = {
            **draft,
            "step2_edited": result.get("edited_content", content),
            "changes_made": result.get("changes_made", []),
            "warnings": result.get("warnings", []),
            "guardrails_status": result.get("guardrails_status", {}),
            "citations_needed": result.get("citations_needed", []),
        }
        edited_results.append(edited_draft)

    return edited_results, total_cost
