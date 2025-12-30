"""Hook variation generator for LinkedIn posts.

Generates multiple hook variations for each LinkedIn post,
allowing users to pick their favorite opening line.
"""
import json
from typing import Tuple

from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.services.persona_manager import get_persona
from app.utils.json_parser import parse_llm_json


# Hook types with descriptions
HOOK_TYPES = {
    "question": "Opens with a thought-provoking question that creates curiosity",
    "stat": "Opens with a surprising statistic or data point",
    "story": "Opens with a brief story or personal anecdote",
    "bold_claim": "Opens with a contrarian or bold statement",
    "problem": "Opens by addressing a specific pain point directly",
}


async def generate_hook_variations(
    post_content: str,
    persona_id: str,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[list[dict], float]:
    """
    Generate 5 hook variations for a LinkedIn post.

    Takes the post content and generates alternative opening hooks
    in different styles: question, stat, story, bold claim, problem.

    Args:
        post_content: The full LinkedIn post content
        persona_id: Target persona ID for context
        job_id: Optional job ID for logging
        user_id: Optional user ID for logging

    Returns:
        (hooks_list, cost) tuple where hooks_list contains:
        [
            {
                "hook_type": "question",
                "hook_text": "The opening line...",
                "full_post": "Complete post with this hook...",
                "explanation": "Why this hook works..."
            },
            ...
        ]
    """
    persona = await get_persona(persona_id, user_id=user_id)
    persona_title = persona["title"] if persona else "Professional"
    persona_pain_points = ", ".join(persona.get("pain_points", [])) if persona else ""

    prompt = f"""You are an expert LinkedIn content strategist. Generate 5 different hook variations for this LinkedIn post.

TARGET AUDIENCE: {persona_title}
PAIN POINTS: {persona_pain_points}

ORIGINAL POST:
{post_content}

Create 5 hook variations, one for each type:

1. QUESTION HOOK: Opens with a thought-provoking question that creates curiosity
2. STAT HOOK: Opens with a surprising statistic or data point (can be implied/estimated if no exact stat in original)
3. STORY HOOK: Opens with a brief story starter or personal angle
4. BOLD CLAIM HOOK: Opens with a contrarian or provocative statement
5. PROBLEM HOOK: Opens by directly addressing a specific pain point

RULES:
- Each hook should be 1-2 sentences max
- The hook must lead naturally into the rest of the post
- Keep the core message and CTA of the original post
- Adapt the hook style to resonate with the target persona
- Make each hook distinctly different in approach

OUTPUT FORMAT (valid JSON):
{{
  "hooks": [
    {{
      "hook_type": "question",
      "hook_text": "The opening hook line only",
      "full_post": "Complete post starting with this hook (include the rest of the content)",
      "explanation": "Brief explanation of why this hook works for this audience"
    }},
    {{
      "hook_type": "stat",
      "hook_text": "The opening hook line only",
      "full_post": "Complete post starting with this hook",
      "explanation": "Brief explanation"
    }},
    {{
      "hook_type": "story",
      "hook_text": "The opening hook line only",
      "full_post": "Complete post starting with this hook",
      "explanation": "Brief explanation"
    }},
    {{
      "hook_type": "bold_claim",
      "hook_text": "The opening hook line only",
      "full_post": "Complete post starting with this hook",
      "explanation": "Brief explanation"
    }},
    {{
      "hook_type": "problem",
      "hook_text": "The opening hook line only",
      "full_post": "Complete post starting with this hook",
      "explanation": "Brief explanation"
    }}
  ]
}}"""

    # Call LLM via unified client (no token limit)
    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=prompt,
        step="drafting",
        response_format="json",
        job_id=job_id,
        user_id=user_id,
    )

    # Parse response with robust JSON parser
    result = parse_llm_json(response_text, context="hook variations")

    hooks = result.get("hooks", [])

    # Ensure we have hook_type labels
    for hook in hooks:
        if "hook_type" not in hook:
            hook["hook_type"] = "unknown"

    # Calculate cost
    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return hooks, cost


async def batch_generate_hooks(
    linkedin_outputs: list[dict],
    persona_id: str,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[list[dict], float]:
    """
    Generate hook variations for multiple LinkedIn posts.

    Args:
        linkedin_outputs: List of LinkedIn output dicts with 'content' or 'step3_final'
        persona_id: Target persona ID
        job_id: Optional job ID
        user_id: Optional user ID

    Returns:
        (updated_outputs, total_cost) tuple where each output now has a 'hook_variations' field
    """
    total_cost = 0.0

    for output in linkedin_outputs:
        if output.get("content_type") != "linkedin":
            continue

        # Get the final content
        content = output.get("step3_final") or output.get("step2_edited") or output.get("content", "")

        if not content:
            continue

        # Generate hooks for this post
        hooks, cost = await generate_hook_variations(
            post_content=content,
            persona_id=persona_id,
            job_id=job_id,
            user_id=user_id,
        )

        output["hook_variations"] = hooks
        total_cost += cost

    return linkedin_outputs, total_cost


def get_hook_type_label(hook_type: str) -> str:
    """Get a human-readable label for a hook type."""
    labels = {
        "question": "Question Hook",
        "stat": "Statistic Hook",
        "story": "Story Hook",
        "bold_claim": "Bold Claim Hook",
        "problem": "Problem Hook",
    }
    return labels.get(hook_type, hook_type.replace("_", " ").title())
