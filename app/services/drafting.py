"""Content drafting service - Step 2 of the pipeline."""
import json
import logging
from datetime import datetime
from typing import Tuple, Dict, Optional, List

from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.services.prompt_manager import get_rendered_prompt
from app.services.persona_manager import get_persona_for_job
from app.services.distillation import select_stills_for_content_type, group_stills_by_type
from app.services.brand_voice_analyzer import get_brand_voice_template_vars
from app.services.source_of_truth import get_source_of_truth_template_vars
from app.utils.json_parser import parse_llm_json
from app.database import get_db
from app.db_utils import execute, fetchall

logger = logging.getLogger(__name__)

# Default persona values when no persona is selected
DEFAULT_PERSONA = {
    "title": "General Professional Audience",
    "priorities": ["actionable insights", "practical solutions", "valuable information"],
    "pain_points": ["common business challenges", "efficiency", "growth"],
    "content_preferences": {"tone": "Professional"},
}


async def record_still_usage(still_ids: List[str], output_id: int) -> None:
    """
    Increment usage counts and update timestamps for stills used in output.

    Args:
        still_ids: List of still IDs that were used
        output_id: ID of the output they were used in
    """
    if not still_ids:
        return

    now = datetime.utcnow().isoformat()

    try:
        async with get_db() as db:
            await db.execute("""
                UPDATE stills
                SET usage_count = COALESCE(usage_count, 0) + 1,
                    last_used_at = $1
                WHERE id = ANY($2)
            """, now, still_ids)

            await db.execute("""
                UPDATE outputs
                SET stills_used = $1
                WHERE id = $2
            """, json.dumps(still_ids), output_id)

        logger.info(f"Recorded usage of {len(still_ids)} stills for output {output_id}")

    except Exception as e:
        logger.error(f"Failed to record still usage: {e}")
        # Don't re-raise - this is a non-critical operation


async def get_user_context(user_id: int, content_type: str = None) -> str:
    """
    Get user-specific context to inject into drafting prompts.

    Includes memory rules, style DNA, brand voice profile, and brand voice config.

    Args:
        user_id: User ID
        content_type: Optional content type ("linkedin", "blog", "email") for
                      platform-specific brand voice tone
    """
    context_parts = []

    try:
        # Memory rules
        from app.api.memory import get_memory_rules_context
        memory_context = await get_memory_rules_context(user_id)
        if memory_context:
            context_parts.append(memory_context)
    except Exception as e:
        logger.warning(f"Memory context failed for user {user_id}: {e}")

    try:
        # Style DNA from swipes
        from app.services.swipe_analyzer import get_style_context_for_drafting
        style_context = await get_style_context_for_drafting(user_id)
        if style_context:
            context_parts.append(style_context)
    except Exception as e:
        logger.warning(f"Style context failed for user {user_id}: {e}")

    try:
        # Brand voice profile (AI-analyzed from samples)
        from app.services.brand_voice_analyzer import get_voice_context_for_drafting
        voice_context = await get_voice_context_for_drafting(user_id)
        if voice_context:
            context_parts.append(voice_context)
    except Exception as e:
        logger.warning(f"Brand voice context failed for user {user_id}: {e}")

    try:
        # Brand voice config (manual settings with per-platform tones)
        from app.services.brand_voice_analyzer import get_brand_voice_config_context
        config_context = await get_brand_voice_config_context(user_id, content_type)
        if config_context:
            context_parts.append(config_context)
    except Exception as e:
        logger.warning(f"Brand voice config context failed for user {user_id}: {e}")

    return "\n".join(context_parts)


async def get_source_summaries(job_ids: list[str]) -> Dict[str, Dict[str, str]]:
    """
    Fetch source summaries for multiple job IDs.

    Args:
        job_ids: List of job IDs to fetch summaries for

    Returns:
        Dict mapping job_id -> {"campaign_name": str, "summary": str}
    """
    if not job_ids:
        return {}

    summaries = {}

    try:
        async with get_db() as db:
            # Build query for multiple job IDs
            placeholders = ", ".join(["?" for _ in job_ids])
            query = f"SELECT id, campaign_name, source_summary FROM jobs WHERE id IN ({placeholders})"

            rows = await fetchall(db, query, tuple(job_ids))

            for row in rows:
                job_id = row["id"]
                summaries[job_id] = {
                    "campaign_name": row["campaign_name"] or "Unknown Source",
                    "summary": row["source_summary"] or ""
                }
    except Exception as e:
        logger.warning(f"Failed to fetch source summaries: {e}")

    return summaries


async def build_source_context(stills: list[dict]) -> str:
    """
    Build source context block for multi-source generation.

    When generating content from stills that came from multiple sources,
    this function builds a context block that helps the AI understand
    where each piece of content originated.

    Args:
        stills: List of still dicts, each with a 'job_id' field

    Returns:
        Context string to inject into prompts, or empty string if single source
    """
    # Extract unique job IDs from stills
    job_ids = list(set(
        s.get("job_id") for s in stills
        if s.get("job_id") and s.get("job_id") != "manual"
    ))

    # Only add context for multi-source generation
    if len(job_ids) <= 1:
        return ""

    # Fetch summaries for all sources
    summaries = await get_source_summaries(job_ids)

    if not summaries:
        return ""

    # Build context block
    context_parts = ["SOURCE CONTEXT:", "---"]

    for job_id in job_ids:
        info = summaries.get(job_id, {})
        campaign = info.get("campaign_name", "Unknown Source")
        summary = info.get("summary", "")

        # Count stills from this source
        source_stills = [s for s in stills if s.get("job_id") == job_id]
        still_count = len(source_stills)

        context_parts.append(f'\nSource: "{campaign}"')
        if summary:
            context_parts.append(f"Summary: {summary}")
        context_parts.append(f"({still_count} pieces selected from this source)")

    context_parts.append("\n---\n")

    return "\n".join(context_parts)


async def draft_linkedin_posts(
    stills: list[dict],
    persona_id: str,
    count: int = 3,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[list[dict], float]:
    """
    Generate LinkedIn post drafts.

    Returns (drafts_list, cost) tuple.
    """
    # Get persona or use defaults if not provided
    persona = None
    if persona_id:
        persona = await get_persona_for_job(persona_id, user_id)
    if not persona:
        persona = DEFAULT_PERSONA

    # Select best stills for LinkedIn
    selected_stills = select_stills_for_content_type(stills, "linkedin", persona_id, count=count * 2)

    # Format stills for prompt (include attribution for quotes)
    def format_still(s):
        still_type = s.get('still_type', 'insight').upper()
        content = s['content']
        if still_type == 'QUOTE' and s.get('quote_attribution'):
            return f"- [{still_type}] \"{content}\" — {s['quote_attribution']}"
        return f"- [{still_type}] {content}"

    stills_text = "\n".join([format_still(s) for s in selected_stills])

    variables = {
        "selected_stills_for_linkedin": stills_text,
        "persona_title": persona["title"],
        "persona_priorities": ", ".join(persona["priorities"]),
        "persona_pain_points": ", ".join(persona["pain_points"]),
    }

    # Inject brand voice variables if user_id provided
    if user_id:
        brand_vars = await get_brand_voice_template_vars(user_id, content_type="linkedin")
        variables.update(brand_vars)

    # Inject source of truth variables if job_id provided
    if job_id:
        sot_vars = await get_source_of_truth_template_vars(job_id)
        variables.update(sot_vars)

    prompt, config = await get_rendered_prompt("linkedin_draft", variables)

    # Get user-specific context (memory rules, style DNA, brand voice)
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id, content_type="linkedin")

    # Get source context for multi-source generation
    source_context = await build_source_context(selected_stills)

    # Add JSON output instruction
    # Source context is injected right before the stills content
    full_prompt = source_context + prompt + user_context + f"""

Generate exactly {count} LinkedIn post variations.

OUTPUT FORMAT (valid JSON):
{{
  "posts": [
    {{
      "variation": 1,
      "hook_type": "question|stat|problem|benefit",
      "content": "Full post text here...",
      "stills_used": ["still content snippets used"],
      "cta": "Call to action text"
    }}
  ]
}}"""

    # Call LLM via unified client
    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=full_prompt,
        step="drafting",
                response_format="json",
        job_id=job_id,
        user_id=user_id,
    )

    # Parse response with robust JSON parser
    result = parse_llm_json(response_text, context="LinkedIn drafts")

    drafts = result.get("posts", [])

    # Calculate cost
    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return drafts, cost


async def draft_blog_post(
    stills: list[dict],
    persona_id: str,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[dict, float]:
    """
    Generate a blog post draft.

    Returns (draft, cost) tuple.
    """
    # Get persona or use defaults if not provided
    persona = None
    if persona_id:
        persona = await get_persona_for_job(persona_id, user_id)
    if not persona:
        persona = DEFAULT_PERSONA

    # Group stills by type
    grouped = group_stills_by_type(stills)

    # Format stills for each category
    def format_stills(still_list):
        if not still_list:
            return "None available"
        return "\n".join([f"- {s['content']}" for s in still_list[:5]])

    # Format quotes with attribution
    def format_quotes(still_list):
        if not still_list:
            return "None available"
        formatted = []
        for s in still_list[:5]:
            if s.get('quote_attribution'):
                formatted.append(f"- \"{s['content']}\" — {s['quote_attribution']}")
            else:
                formatted.append(f"- \"{s['content']}\"")
        return "\n".join(formatted)

    variables = {
        "problem_stills": format_stills(grouped["problem"]),
        "insight_stills": format_stills(grouped["insight"]),
        "solution_stills": format_stills(grouped["solution"]),
        "data_stills": format_stills(grouped["data"]),
        "story_stills": format_stills(grouped["story"]),
        "quote_stills": format_quotes(grouped["quote"]),
        "persona_title": persona["title"],
    }

    # Inject brand voice variables if user_id provided
    if user_id:
        brand_vars = await get_brand_voice_template_vars(user_id, content_type="blog")
        variables.update(brand_vars)

    # Inject source of truth variables if job_id provided
    if job_id:
        sot_vars = await get_source_of_truth_template_vars(job_id)
        variables.update(sot_vars)

    prompt, config = await get_rendered_prompt("blog_draft", variables)

    # Get user-specific context (memory rules, style DNA, brand voice)
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id, content_type="blog")

    # Get source context for multi-source generation
    source_context = await build_source_context(stills)

    # Add JSON output instruction
    full_prompt = source_context + prompt + user_context + """

OUTPUT FORMAT (valid JSON):
{
  "title": "Blog post title",
  "content": "Full blog post content with markdown formatting (## for H2 headings)",
  "stills_used": ["still content snippets used"],
  "word_count": 0,
  "sections": ["Section 1 title", "Section 2 title", "Section 3 title"]
}"""

    # Call LLM via unified client
    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=full_prompt,
        step="drafting",
                response_format="json",
        job_id=job_id,
        user_id=user_id,
    )

    # Parse response with robust JSON parser
    result = parse_llm_json(response_text, context="blog draft")

    # Calculate cost
    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return result, cost


async def draft_email(
    stills: list[dict],
    persona_id: str,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[dict, float]:
    """
    Generate an email draft.

    Returns (draft, cost) tuple.
    """
    # Get persona or use defaults if not provided
    persona = None
    if persona_id:
        persona = await get_persona_for_job(persona_id, user_id)
    if not persona:
        persona = DEFAULT_PERSONA

    # Select stills for email
    selected_stills = select_stills_for_content_type(stills, "email", persona_id, count=4)

    stills_text = "\n".join([
        f"- [{s.get('still_type', 'insight').upper()}] {s['content']}"
        for s in selected_stills
    ])

    variables = {
        "selected_stills": stills_text,
        "persona_title": persona["title"],
        "persona_priorities": ", ".join(persona["priorities"]),
        "persona_pain_points": ", ".join(persona["pain_points"]),
    }

    # Inject brand voice variables if user_id provided
    if user_id:
        brand_vars = await get_brand_voice_template_vars(user_id, content_type="email")
        variables.update(brand_vars)

    # Inject source of truth variables if job_id provided
    if job_id:
        sot_vars = await get_source_of_truth_template_vars(job_id)
        variables.update(sot_vars)

    prompt, config = await get_rendered_prompt("email_draft", variables)

    # Get user-specific context (memory rules, style DNA, brand voice)
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id, content_type="email")

    # Get source context for multi-source generation
    source_context = await build_source_context(selected_stills)

    # Add output instruction
    full_prompt = source_context + prompt + user_context + """

OUTPUT FORMAT (valid JSON):
{
  "subject": "Email subject line",
  "preview_text": "Email preview text (first line)",
  "body": "Full email body",
  "cta": "Call to action",
  "stills_used": ["still content snippets used"]
}"""

    # Call LLM via unified client
    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=full_prompt,
        step="drafting",
                response_format="json",
        job_id=job_id,
        user_id=user_id,
    )

    # Parse response with robust JSON parser
    result = parse_llm_json(response_text, context="email draft")

    # Calculate cost
    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return result, cost


async def draft_email_sequence(
    stills: list[dict],
    persona_id: str,
    job_id: str = None,
    user_id: int = None,
) -> Tuple[list[dict], float]:
    """
    Generate a 5-email drip campaign sequence.

    Emails are structured for Days 0, 3, 7, 14, and 30.
    Each email has a distinct purpose in the nurture journey.

    Returns (emails_list, cost) tuple.
    """
    # Get persona or use defaults if not provided
    persona = None
    if persona_id:
        persona = await get_persona_for_job(persona_id, user_id)
    if not persona:
        persona = DEFAULT_PERSONA

    # Group stills by type for comprehensive sequence
    grouped = group_stills_by_type(stills)

    # Format all stills for the sequence
    def format_stills_for_sequence(still_list, limit=3):
        if not still_list:
            return "None available"
        formatted = []
        for s in still_list[:limit]:
            if s.get('quote_attribution'):
                formatted.append(f"- \"{s['content']}\" — {s['quote_attribution']}")
            else:
                formatted.append(f"- {s['content']}")
        return "\n".join(formatted)

    all_stills_text = f"""
PROBLEMS/PAIN POINTS:
{format_stills_for_sequence(grouped.get("problem", []))}

INSIGHTS:
{format_stills_for_sequence(grouped.get("insight", []))}

SOLUTIONS:
{format_stills_for_sequence(grouped.get("solution", []))}

DATA/STATISTICS:
{format_stills_for_sequence(grouped.get("data", []))}

STORIES:
{format_stills_for_sequence(grouped.get("story", []))}

QUOTES:
{format_stills_for_sequence(grouped.get("quote", []))}
"""

    variables = {
        "persona_title": persona["title"],
        "persona_pain_points": ", ".join(persona.get("pain_points", [])),
        "persona_priorities": ", ".join(persona.get("priorities", [])),
        "persona_tone": persona.get("content_preferences", {}).get("tone", "Professional"),
        "all_stills_text": all_stills_text,
    }

    # Inject brand voice if available
    if user_id:
        brand_vars = await get_brand_voice_template_vars(user_id, content_type="email")
        variables.update(brand_vars)

    if job_id:
        sot_vars = await get_source_of_truth_template_vars(job_id)
        variables.update(sot_vars)

    prompt, config = await get_rendered_prompt("email_sequence_draft", variables)

    # Get user-specific context (memory rules, style DNA, brand voice)
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id, content_type="email")

    # Get source context for multi-source generation
    source_context = await build_source_context(stills)

    # Build full prompt with source/user context and JSON output format
    full_prompt = source_context + prompt + user_context + """

OUTPUT FORMAT (valid JSON):
{
  "sequence_name": "Name for this email sequence",
  "emails": [
    {
      "day": 0,
      "purpose": "Welcome/Hook",
      "subject": "Subject line",
      "preview_text": "Preview text",
      "body": "Full email body with paragraphs",
      "cta": "Call to action text",
      "stills_used": ["still snippets used"]
    },
    {
      "day": 3,
      "purpose": "Value/Education",
      "subject": "Subject line",
      "preview_text": "Preview text",
      "body": "Full email body",
      "cta": "Call to action text",
      "stills_used": ["still snippets used"]
    },
    {
      "day": 7,
      "purpose": "Story/Credibility",
      "subject": "Subject line",
      "preview_text": "Preview text",
      "body": "Full email body",
      "cta": "Call to action text",
      "stills_used": ["still snippets used"]
    },
    {
      "day": 14,
      "purpose": "Solution",
      "subject": "Subject line",
      "preview_text": "Preview text",
      "body": "Full email body",
      "cta": "Call to action text",
      "stills_used": ["still snippets used"]
    },
    {
      "day": 30,
      "purpose": "Action/Urgency",
      "subject": "Subject line",
      "preview_text": "Preview text",
      "body": "Full email body",
      "cta": "Call to action text",
      "stills_used": ["still snippets used"]
    }
  ]
}"""

    # Call LLM via unified client
    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=full_prompt,
        step="drafting",
        response_format="json",
        job_id=job_id,
        user_id=user_id,
    )

    # Parse response with robust JSON parser
    result = parse_llm_json(response_text, context="email sequence")

    # Handle both formats: {"emails": [...]} or just [...]
    if isinstance(result, list):
        emails = result
        sequence_name = "Email Nurture Sequence"
    else:
        emails = result.get("emails", [])
        sequence_name = result.get("sequence_name", "Email Nurture Sequence")

    # Add sequence metadata to each email
    for email in emails:
        email["sequence_name"] = sequence_name

    # Calculate cost
    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return emails, cost
