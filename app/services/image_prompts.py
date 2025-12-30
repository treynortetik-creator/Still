"""Image prompt generation service for content pieces."""
import json
import logging
from typing import Tuple, Optional

from app.config import get_settings
from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.utils.json_parser import parse_llm_json

settings = get_settings()
logger = logging.getLogger(__name__)

# Platform-specific dimensions for images
PLATFORM_DIMENSIONS = {
    "linkedin": {"width": 1200, "height": 627, "aspect": "1.91:1", "name": "LinkedIn Post"},
    "blog": {"width": 1200, "height": 630, "aspect": "1.91:1", "name": "Blog Header"},
    "email": {"width": 600, "height": 400, "aspect": "3:2", "name": "Email Banner"},
    "email_sequence": {"width": 600, "height": 400, "aspect": "3:2", "name": "Email Banner"},
}


async def generate_image_prompts(
    content: str,
    content_type: str,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[list[dict], float]:
    """
    Generate 2-3 AI image prompts for a content piece.

    Args:
        content: The content text to generate prompts for
        content_type: Type of content (linkedin, blog, email)
        job_id: Optional job ID for cost tracking
        user_id: Optional user ID for cost tracking

    Returns:
        Tuple of (prompts_list, cost)
    """
    if not content or len(content.strip()) < 50:
        return [], 0.0

    dimensions = PLATFORM_DIMENSIONS.get(content_type, PLATFORM_DIMENSIONS["blog"])

    prompt = f"""You are an expert at creating AI image generation prompts for professional B2B content.

CONTENT TO VISUALIZE:
{content[:2000]}

PLATFORM: {dimensions['name']}
DIMENSIONS: {dimensions['width']}x{dimensions['height']} ({dimensions['aspect']})

Create 2-3 high-quality image generation prompts that:
1. Capture the key theme/message of the content
2. Are professional and appropriate for business content
3. Work well for the specified platform and dimensions
4. Include specific style modifiers for best results
5. Avoid generic stock photo cliches - be creative but professional

For each prompt, specify:
- Detailed scene description (subject, setting, composition)
- Lighting and mood
- Style (photorealistic, illustration, 3D render, etc.)
- Specific modifiers for AI generators

OUTPUT FORMAT (valid JSON):
{{
  "prompts": [
    {{
      "prompt_text": "Detailed prompt here with subject, setting, lighting, style, composition. Professional corporate setting with...",
      "platform": "midjourney",
      "style_modifiers": "professional, corporate, high quality, studio lighting, --ar {dimensions['aspect']}"
    }},
    {{
      "prompt_text": "Alternative approach with different visual angle...",
      "platform": "dalle",
      "style_modifiers": "photorealistic, clean, minimalist, business context"
    }}
  ]
}}

IMPORTANT: Create prompts that would work for Midjourney, DALL-E, or Stable Diffusion."""

    try:
        response_text, input_tokens, output_tokens, model = await call_llm_text(
            prompt=prompt,
            step="drafting",
            response_format="json",
            job_id=job_id,
            user_id=user_id,
        )

        result = parse_llm_json(response_text, context="image prompts")
        prompts = result.get("prompts", [])

        # Add dimensions to each prompt
        for p in prompts:
            p["dimensions"] = f"{dimensions['width']}x{dimensions['height']}"
            p["content_type"] = content_type

        cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

        return prompts, cost

    except Exception as e:
        logger.warning(f"Failed to generate image prompts: {e}")
        return [], 0.0


async def batch_generate_image_prompts(
    outputs: list[dict],
    job_id: str = None,
    user_id: int = None,
) -> Tuple[list[dict], float]:
    """
    Generate image prompts for all outputs in a batch.

    Args:
        outputs: List of output dictionaries with content
        job_id: Job ID for cost tracking
        user_id: User ID for cost tracking

    Returns:
        Tuple of (outputs_with_prompts, total_cost)
    """
    total_cost = 0.0

    for output in outputs:
        # Get the best available content version
        content = (
            output.get("step3_final") or
            output.get("step2_edited") or
            output.get("step1_draft") or
            output.get("content", "")
        )
        content_type = output.get("content_type", "blog")

        if content and len(content.strip()) >= 50:
            try:
                prompts, cost = await generate_image_prompts(
                    content, content_type, job_id, user_id
                )
                output["image_prompts"] = prompts
                total_cost += cost
            except Exception as e:
                logger.warning(f"Image prompt generation failed for output: {e}")
                output["image_prompts"] = []
        else:
            output["image_prompts"] = []

    return outputs, total_cost


async def save_image_prompts_to_db(output_id: int, prompts: list[dict]) -> None:
    """
    Save image prompts to the database.

    Args:
        output_id: The output ID to associate prompts with
        prompts: List of prompt dictionaries
    """
    if not prompts:
        return

    from app.database import get_db
    from app.db_utils import execute

    async with get_db() as db:
        for prompt in prompts:
            await execute(
                db,
                """
                INSERT INTO image_prompts (output_id, prompt_text, platform, dimensions, style_modifiers)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    output_id,
                    prompt.get("prompt_text", ""),
                    prompt.get("platform", "midjourney"),
                    prompt.get("dimensions", "1200x630"),
                    prompt.get("style_modifiers"),
                )
            )
        if not settings.use_postgres:
            await db.commit()


async def get_image_prompts_for_output(output_id: int) -> list[dict]:
    """
    Get image prompts for a specific output.

    Args:
        output_id: The output ID

    Returns:
        List of prompt dictionaries
    """
    from app.database import get_db
    from app.db_utils import fetchall

    async with get_db() as db:
        rows = await fetchall(
            db,
            "SELECT * FROM image_prompts WHERE output_id = ?",
            (output_id,)
        )

    return [
        {
            "id": row["id"],
            "prompt_text": row["prompt_text"],
            "platform": row["platform"],
            "dimensions": row["dimensions"],
            "style_modifiers": row["style_modifiers"],
        }
        for row in rows
    ]
