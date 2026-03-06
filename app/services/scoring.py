"""Quality scoring service - evaluates content quality across 4 dimensions."""
import json
import logging
from typing import Tuple

from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.utils.json_parser import parse_llm_json

logger = logging.getLogger(__name__)


async def score_content(
    content: str,
    content_type: str,
    persona_title: str = "",
    brand_voice_summary: str = "",
    brand_tone_markers: str = "",
    brand_phrases_to_avoid: str = "",
    user_id: int = None,
    job_id: str = None,
) -> Tuple[dict, float]:
    """
    Score content quality across 4 dimensions (0-100 each).

    Dimensions:
    1. Hook Quality - Does the opening grab attention?
    2. Brand Alignment - Matches the brand voice and principles?
    3. Clarity - Easy to understand without jargon?
    4. Engagement Potential - Will this resonate with the audience?

    Returns (scores_dict, cost) tuple.
    """
    # Build brand alignment criteria based on provided brand voice
    if brand_voice_summary or brand_tone_markers:
        brand_criteria = f"""2. BRAND ALIGNMENT (0-100)
   - Does it match the brand voice: {brand_voice_summary or 'professional and authentic'}?
   - Does it reflect the tone markers: {brand_tone_markers or 'authoritative, helpful'}?
   - Does it AVOID these phrases/patterns: {brand_phrases_to_avoid or 'overly salesy language'}?
   - Would this sound like the brand if read aloud?"""
    else:
        brand_criteria = """2. BRAND ALIGNMENT (0-100)
   - Is the tone professional and authentic?
   - Does it avoid overly salesy language?
   - Would a thought leader share this?"""

    prompt = f"""Score this {content_type} content across 4 quality dimensions (0-100 each).

CONTENT:
{content}

TARGET AUDIENCE: {persona_title or "Business professionals"}

Evaluate these 4 dimensions:

1. HOOK QUALITY (0-100)
   - Does the opening grab attention?
   - Is there a compelling first line?
   - Would someone stop scrolling to read this?

{brand_criteria}

3. CLARITY (0-100)
   - Is it easy to understand?
   - Is jargon minimized or explained?
   - Is the message clear?

4. ENGAGEMENT POTENTIAL (0-100)
   - Will this resonate with the audience?
   - Does it provide value?
   - Is there a clear call to action?

OUTPUT FORMAT (valid JSON):
{{
  "hook_quality": {{"score": 85, "reason": "Opens with a thought-provoking question"}},
  "brand_alignment": {{"score": 90, "reason": "Professional tone without being salesy"}},
  "clarity": {{"score": 75, "reason": "Some industry terms could be simplified"}},
  "engagement_potential": {{"score": 80, "reason": "Provides actionable insights"}}
}}"""

    # Use unified AI client (no token limit)
    response_text, input_tokens, output_tokens, model_used = await call_llm_text(
        prompt=prompt,
        step="scoring",
        response_format="json",
        user_id=user_id,
        job_id=job_id,
    )

    try:
        result = parse_llm_json(response_text, context="content scoring")
    except ValueError as e:
        logger.warning(f"Failed to parse content scoring: {e}")
        # Return default scores if parsing fails
        result = {
            "hook_quality": {"score": 70, "reason": "Score pending"},
            "brand_alignment": {"score": 70, "reason": "Score pending"},
            "clarity": {"score": 70, "reason": "Score pending"},
            "engagement_potential": {"score": 70, "reason": "Score pending"},
        }

    # Calculate overall score
    scores = [
        result.get("hook_quality", {}).get("score", 70),
        result.get("brand_alignment", {}).get("score", 70),
        result.get("clarity", {}).get("score", 70),
        result.get("engagement_potential", {}).get("score", 70),
    ]
    result["overall_score"] = round(sum(scores) / len(scores))

    # Calculate cost
    cost = calculate_openrouter_cost(model_used, input_tokens, output_tokens)

    return result, cost


async def batch_score_content(
    outputs: list[dict],
    persona_title: str = "",
    brand_voice_summary: str = "",
    brand_tone_markers: str = "",
    brand_phrases_to_avoid: str = "",
    user_id: int = None,
    job_id: str = None,
) -> Tuple[list[dict], float]:
    """
    Score multiple content outputs.

    Returns (scored_outputs, total_cost) tuple.
    """
    scored_outputs = []
    total_cost = 0.0

    for output in outputs:
        content = output.get("step3_final") or output.get("step2_edited") or output.get("content", "")
        content_type = output.get("content_type", "linkedin")

        if not content:
            output["quality_scores"] = None
            scored_outputs.append(output)
            continue

        try:
            scores, cost = await score_content(
                content,
                content_type,
                persona_title,
                brand_voice_summary,
                brand_tone_markers,
                brand_phrases_to_avoid,
                user_id=user_id,
                job_id=job_id,
            )
            total_cost += cost

            output["quality_scores"] = scores
            scored_outputs.append(output)
        except Exception as e:
            # Don't fail the whole pipeline if scoring fails
            logger.warning(f"Scoring failed for {content_type}: {e}")
            output["quality_scores"] = None
            scored_outputs.append(output)

    return scored_outputs, total_cost
