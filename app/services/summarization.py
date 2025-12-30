"""Source content summarization service.

Generates concise summaries of uploaded content for use as context during
cross-source content generation.
"""
import logging
from typing import Tuple

from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.services.prompt_manager import get_rendered_prompt

logger = logging.getLogger(__name__)


async def generate_source_summary(
    cleaned_transcript: str,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[str, float]:
    """
    Generate a summary of the source content.

    This summary is used to provide context when generating content from
    stills across multiple sources.

    Args:
        cleaned_transcript: The extracted/transcribed content
        job_id: Job ID for logging
        user_id: User ID for logging

    Returns:
        (summary_text, cost_in_dollars) tuple
        Returns ("", 0.0) if generation fails (non-fatal)
    """
    if not cleaned_transcript or len(cleaned_transcript.strip()) < 100:
        logger.warning(f"Job {job_id}: Transcript too short for summarization")
        return "", 0.0

    # Truncate if very long (summary doesn't need full context)
    max_chars = 50000  # ~12k tokens, plenty for summary
    transcript_for_summary = cleaned_transcript[:max_chars]

    try:
        # Get the summarization prompt template
        variables = {
            "transcript": transcript_for_summary,
        }

        prompt, config = await get_rendered_prompt("summarization", variables)

        # Call LLM with summarization step
        response_text, input_tokens, output_tokens, model = await call_llm_text(
            prompt=prompt,
            step="summarization",
            max_tokens=500,  # Summary should be concise
            job_id=job_id,
            user_id=user_id,
        )

        summary = response_text.strip()
        cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

        logger.info(f"Job {job_id}: Generated source summary ({len(summary)} chars)")
        return summary, cost

    except Exception as e:
        logger.error(f"Job {job_id}: Summary generation failed: {e}")
        return "", 0.0  # Non-fatal - don't fail the pipeline over a summary
