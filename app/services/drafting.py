"""Content drafting service - Step 2 of the pipeline."""
import logging
from typing import Tuple

from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.services.prompt_manager import get_rendered_prompt
from app.services.persona_manager import get_persona_for_job
from app.services.distillation import select_stills_for_content_type, group_stills_by_type
from app.utils.json_parser import parse_llm_json

logger = logging.getLogger(__name__)

# Default persona values when no persona is selected
DEFAULT_PERSONA = {
    "title": "General Professional Audience",
    "priorities": ["actionable insights", "practical solutions", "valuable information"],
    "pain_points": ["common business challenges", "efficiency", "growth"],
    "content_preferences": {"tone": "Professional"},
}


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
        still_type = s.get('still_type', s.get('atom_type', 'insight')).upper()
        content = s['content']
        if still_type == 'QUOTE' and s.get('quote_attribution'):
            return f"- [{still_type}] \"{content}\" — {s['quote_attribution']}"
        return f"- [{still_type}] {content}"

    stills_text = "\n".join([format_still(s) for s in selected_stills])

    variables = {
        "selected_atoms_for_linkedin": stills_text,  # Keep prompt variable name for compatibility
        "persona_title": persona["title"],
        "persona_priorities": ", ".join(persona["priorities"]),
        "persona_pain_points": ", ".join(persona["pain_points"]),
    }

    prompt, config = await get_rendered_prompt("linkedin_draft", variables)

    # Get user-specific context (memory rules, style DNA, brand voice)
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id, content_type="linkedin")

    # Add JSON output instruction
    full_prompt = prompt + user_context + f"""

Generate exactly {count} LinkedIn post variations.

OUTPUT FORMAT (valid JSON):
{{
  "posts": [
    {{
      "variation": 1,
      "hook_type": "question|stat|problem|benefit",
      "content": "Full post text here...",
      "atoms_used": ["atom content snippets used"],
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
        "problem_atoms": format_stills(grouped["problem"]),
        "insight_atoms": format_stills(grouped["insight"]),
        "solution_atoms": format_stills(grouped["solution"]),
        "data_atoms": format_stills(grouped["data"]),
        "story_atoms": format_stills(grouped["story"]),
        "quote_atoms": format_quotes(grouped["quote"]),
        "persona_title": persona["title"],
    }

    prompt, config = await get_rendered_prompt("blog_draft", variables)

    # Get user-specific context (memory rules, style DNA, brand voice)
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id, content_type="blog")

    # Add JSON output instruction
    full_prompt = prompt + user_context + """

OUTPUT FORMAT (valid JSON):
{
  "title": "Blog post title",
  "content": "Full blog post content with markdown formatting (## for H2 headings)",
  "atoms_used": ["atom content snippets used"],
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
        f"- [{s.get('still_type', s.get('atom_type', 'insight')).upper()}] {s['content']}"
        for s in selected_stills
    ])

    variables = {
        "selected_atoms": stills_text,  # Keep prompt variable name for compatibility
        "persona_title": persona["title"],
        "persona_priorities": ", ".join(persona["priorities"]),
        "persona_pain_points": ", ".join(persona["pain_points"]),
    }

    prompt, config = await get_rendered_prompt("email_draft", variables)

    # Get user-specific context (memory rules, style DNA, brand voice)
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id, content_type="email")

    # Add output instruction
    full_prompt = prompt + user_context + """

OUTPUT FORMAT (valid JSON):
{
  "subject": "Email subject line",
  "preview_text": "Email preview text (first line)",
  "body": "Full email body",
  "cta": "Call to action",
  "atoms_used": ["atom content snippets used"]
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

    # Get user-specific context (memory rules, style DNA, brand voice)
    user_context = ""
    if user_id:
        user_context = await get_user_context(user_id, content_type="email")

    prompt = f"""You are an expert email marketing strategist creating a 5-email nurture sequence.
{user_context}

TARGET AUDIENCE:
- Role: {persona["title"]}
- Pain Points: {", ".join(persona.get("pain_points", []))}
- Priorities: {", ".join(persona.get("priorities", []))}
- Preferred Tone: {persona.get("content_preferences", {}).get("tone", "Professional")}

AVAILABLE CONTENT STILLS:
{all_stills_text}

Create a 5-email drip campaign with the following structure:

EMAIL 1 (Day 0 - Welcome/Hook):
- Purpose: Capture attention, establish relevance, promise value
- Use a compelling problem or insight atom
- Short and punchy

EMAIL 2 (Day 3 - Value/Education):
- Purpose: Deliver educational value, build trust
- Use data or insight atoms
- Position yourself as a helpful resource

EMAIL 3 (Day 7 - Story/Credibility):
- Purpose: Social proof, share a success story or case study
- Use story atoms or quotes
- Build emotional connection

EMAIL 4 (Day 14 - Solution):
- Purpose: Present your solution, address objections
- Use solution atoms
- Clear value proposition

EMAIL 5 (Day 30 - Action/Urgency):
- Purpose: Drive action, create urgency
- Summarize key benefits
- Strong call-to-action

Each email should:
- Have a compelling subject line (under 50 chars)
- Include preview text
- Be appropriately lengthed for the persona
- Reference specific atoms used
- Have a clear CTA

OUTPUT FORMAT (valid JSON):
{{
  "sequence_name": "Name for this email sequence",
  "emails": [
    {{
      "day": 0,
      "purpose": "Welcome/Hook",
      "subject": "Subject line",
      "preview_text": "Preview text",
      "body": "Full email body with paragraphs",
      "cta": "Call to action text",
      "atoms_used": ["atom snippets used"]
    }},
    {{
      "day": 3,
      "purpose": "Value/Education",
      "subject": "Subject line",
      "preview_text": "Preview text",
      "body": "Full email body",
      "cta": "Call to action text",
      "atoms_used": ["atom snippets used"]
    }},
    {{
      "day": 7,
      "purpose": "Story/Credibility",
      "subject": "Subject line",
      "preview_text": "Preview text",
      "body": "Full email body",
      "cta": "Call to action text",
      "atoms_used": ["atom snippets used"]
    }},
    {{
      "day": 14,
      "purpose": "Solution",
      "subject": "Subject line",
      "preview_text": "Preview text",
      "body": "Full email body",
      "cta": "Call to action text",
      "atoms_used": ["atom snippets used"]
    }},
    {{
      "day": 30,
      "purpose": "Action/Urgency",
      "subject": "Subject line",
      "preview_text": "Preview text",
      "body": "Full email body",
      "cta": "Call to action text",
      "atoms_used": ["atom snippets used"]
    }}
  ]
}}"""

    # Call LLM via unified client
    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=prompt,
        step="drafting",
        response_format="json",
        job_id=job_id,
        user_id=user_id,
    )

    # Parse response with robust JSON parser
    result = parse_llm_json(response_text, context="email sequence")

    emails = result.get("emails", [])
    sequence_name = result.get("sequence_name", "Email Nurture Sequence")

    # Add sequence metadata to each email
    for email in emails:
        email["sequence_name"] = sequence_name

    # Calculate cost
    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return emails, cost
