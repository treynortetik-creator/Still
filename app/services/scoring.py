"""Quality scoring service - evaluates content quality across 4 dimensions."""
import json
from typing import Tuple
import google.generativeai as genai

from app.config import get_settings, calculate_cost
from app.utils.retry import retry_async, gemini_circuit_breaker

settings = get_settings()


async def score_content(
    content: str,
    content_type: str,
    persona_title: str = "",
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
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""Score this {content_type} content across 4 quality dimensions (0-100 each).

CONTENT:
{content}

TARGET AUDIENCE: {persona_title or "Business professionals"}

Evaluate these 4 dimensions:

1. HOOK QUALITY (0-100)
   - Does the opening grab attention?
   - Is there a compelling first line?
   - Would someone stop scrolling to read this?

2. BRAND ALIGNMENT (0-100)
   - Is the tone professional and authentic?
   - Does it avoid overly salesy language?
   - Would a thought leader share this?

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

    async def do_score():
        return model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                max_output_tokens=1000,
            )
        )

    # Use retry logic for API call
    response = await retry_async(
        do_score,
        max_retries=2,
        base_delay=1.0,
        context="score_content",
    )

    try:
        result = json.loads(response.text)
    except json.JSONDecodeError:
        text = response.text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
        else:
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
    input_tokens = response.usage_metadata.prompt_token_count
    output_tokens = response.usage_metadata.candidates_token_count
    cost = calculate_cost("gemini-2.0-flash", input_tokens, output_tokens)

    return result, cost


async def batch_score_content(
    outputs: list[dict],
    persona_title: str = "",
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
            scores, cost = await score_content(content, content_type, persona_title)
            total_cost += cost

            output["quality_scores"] = scores
            scored_outputs.append(output)
        except Exception as e:
            # Don't fail the whole pipeline if scoring fails
            print(f"Scoring failed for {content_type}: {e}")
            output["quality_scores"] = None
            scored_outputs.append(output)

    return scored_outputs, total_cost
