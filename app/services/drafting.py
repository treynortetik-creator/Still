"""Content drafting service - Step 1 of the pipeline."""
import json
import os
from typing import Tuple
import anthropic

from app.config import get_settings, calculate_cost
from app.services.prompt_manager import get_rendered_prompt
from app.services.persona_manager import get_persona
from app.services.atomization import select_atoms_for_content_type, group_atoms_by_type
from app.utils.retry import retry_async, claude_circuit_breaker

settings = get_settings()


def get_anthropic_client():
    """Get Anthropic client."""
    api_key = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not configured")
    return anthropic.Anthropic(api_key=api_key)


async def draft_linkedin_posts(
    atoms: list[dict],
    persona_id: str,
    count: int = 3,
) -> Tuple[list[dict], float]:
    """
    Generate LinkedIn post drafts using Claude.

    Returns (drafts_list, cost) tuple.
    """
    persona = await get_persona(persona_id)
    if not persona:
        raise ValueError(f"Persona not found: {persona_id}")

    # Select best atoms for LinkedIn
    selected_atoms = select_atoms_for_content_type(atoms, "linkedin", persona_id, count=count * 2)

    # Format atoms for prompt
    atoms_text = "\n".join([
        f"- [{a['atom_type'].upper()}] {a['content']}"
        for a in selected_atoms
    ])

    variables = {
        "selected_atoms_for_linkedin": atoms_text,
        "persona_title": persona["title"],
        "persona_priorities": ", ".join(persona["priorities"]),
        "persona_pain_points": ", ".join(persona["pain_points"]),
    }

    prompt, config = await get_rendered_prompt("linkedin_draft", variables)

    # Add JSON output instruction
    full_prompt = prompt + f"""

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

    client = get_anthropic_client()

    async def do_draft():
        return client.messages.create(
            model=config["model"],
            max_tokens=config["max_tokens"],
            messages=[{"role": "user", "content": full_prompt}],
        )

    # Use retry logic for API call
    message = await retry_async(
        do_draft,
        max_retries=3,
        base_delay=2.0,
        context="draft_linkedin_posts",
    )

    response_text = message.content[0].text

    # Parse response
    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(response_text[start:end])
        else:
            raise ValueError("Failed to parse LinkedIn drafts as JSON")

    drafts = result.get("posts", [])

    # Calculate cost
    cost = calculate_cost(
        config["model"],
        message.usage.input_tokens,
        message.usage.output_tokens
    )

    return drafts, cost


async def draft_blog_post(
    atoms: list[dict],
    persona_id: str,
) -> Tuple[dict, float]:
    """
    Generate a blog post draft using Claude.

    Returns (draft, cost) tuple.
    """
    persona = await get_persona(persona_id)
    if not persona:
        raise ValueError(f"Persona not found: {persona_id}")

    # Group atoms by type
    grouped = group_atoms_by_type(atoms)

    # Format atoms for each category
    def format_atoms(atom_list):
        if not atom_list:
            return "None available"
        return "\n".join([f"- {a['content']}" for a in atom_list[:5]])

    variables = {
        "problem_atoms": format_atoms(grouped["problem"]),
        "insight_atoms": format_atoms(grouped["insight"]),
        "solution_atoms": format_atoms(grouped["solution"]),
        "data_atoms": format_atoms(grouped["data"]),
        "story_atoms": format_atoms(grouped["story"]),
        "persona_title": persona["title"],
    }

    prompt, config = await get_rendered_prompt("blog_draft", variables)

    # Add JSON output instruction
    full_prompt = prompt + """

OUTPUT FORMAT (valid JSON):
{
  "title": "Blog post title",
  "content": "Full blog post content with markdown formatting (## for H2 headings)",
  "atoms_used": ["atom content snippets used"],
  "word_count": 0,
  "sections": ["Section 1 title", "Section 2 title", "Section 3 title"]
}"""

    client = get_anthropic_client()

    async def do_draft():
        return client.messages.create(
            model=config["model"],
            max_tokens=config["max_tokens"],
            messages=[{"role": "user", "content": full_prompt}],
        )

    # Use retry logic for API call
    message = await retry_async(
        do_draft,
        max_retries=3,
        base_delay=2.0,
        context="draft_blog_post",
    )

    response_text = message.content[0].text

    # Parse response
    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(response_text[start:end])
        else:
            raise ValueError("Failed to parse blog draft as JSON")

    # Calculate cost
    cost = calculate_cost(
        config["model"],
        message.usage.input_tokens,
        message.usage.output_tokens
    )

    return result, cost


async def draft_email(
    atoms: list[dict],
    persona_id: str,
) -> Tuple[dict, float]:
    """
    Generate an email draft using Claude.

    Returns (draft, cost) tuple.
    """
    persona = await get_persona(persona_id)
    if not persona:
        raise ValueError(f"Persona not found: {persona_id}")

    # Select atoms for email
    selected_atoms = select_atoms_for_content_type(atoms, "email", persona_id, count=4)

    atoms_text = "\n".join([
        f"- [{a['atom_type'].upper()}] {a['content']}"
        for a in selected_atoms
    ])

    variables = {
        "selected_atoms": atoms_text,
        "persona_title": persona["title"],
        "persona_priorities": ", ".join(persona["priorities"]),
        "persona_pain_points": ", ".join(persona["pain_points"]),
    }

    prompt, config = await get_rendered_prompt("email_draft", variables)

    # Add output instruction
    full_prompt = prompt + """

OUTPUT FORMAT (valid JSON):
{
  "subject": "Email subject line",
  "preview_text": "Email preview text (first line)",
  "body": "Full email body",
  "cta": "Call to action",
  "atoms_used": ["atom content snippets used"]
}"""

    client = get_anthropic_client()

    async def do_draft():
        return client.messages.create(
            model=config["model"],
            max_tokens=config["max_tokens"],
            messages=[{"role": "user", "content": full_prompt}],
        )

    # Use retry logic for API call
    message = await retry_async(
        do_draft,
        max_retries=3,
        base_delay=2.0,
        context="draft_email",
    )

    response_text = message.content[0].text

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(response_text[start:end])
        else:
            raise ValueError("Failed to parse email draft as JSON")

    cost = calculate_cost(
        config["model"],
        message.usage.input_tokens,
        message.usage.output_tokens
    )

    return result, cost
