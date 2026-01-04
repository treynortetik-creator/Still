"""Prompt template management service."""
import json
import aiofiles
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchval

settings = get_settings()


async def init_prompts_from_files():
    """
    Initialize prompt templates in database from files in /data/prompts/.

    Called on application startup to ensure all prompts are available.
    """
    prompts_dir = settings.prompts_dir

    # Default prompts with their configurations
    default_prompts = {
        "source_of_truth": {
            "model": "gemini-2.5-flash",
            "max_tokens": 8000,
            "variables": ["cleaned_transcript", "today_date"],
        },
        "distillation": {
            "model": "gemini-2.5-flash",
            "max_tokens": 8000,
            "variables": [
                "target_persona_title", "persona_pain_points", "persona_priorities",
                "cleaned_transcript"
            ],
        },
        "distillation_pass2": {
            "model": "gemini-2.5-flash",
            "max_tokens": 8000,
            "variables": [
                "target_persona_title", "persona_pain_points", "persona_priorities",
                "cleaned_transcript", "first_pass_stills", "first_pass_count"
            ],
        },
        "linkedin_draft": {
            "model": "claude-opus-4-5-20251101",
            "max_tokens": 4000,
            "variables": [
                "selected_atoms_for_linkedin", "persona_title",
                "persona_priorities", "persona_pain_points"
            ],
        },
        "blog_draft": {
            "model": "claude-opus-4-5-20251101",
            "max_tokens": 8000,
            "variables": [
                "problem_atoms", "insight_atoms", "solution_atoms",
                "data_atoms", "story_atoms", "persona_title"
            ],
        },
        "email_draft": {
            "model": "claude-opus-4-5-20251101",
            "max_tokens": 4000,
            "variables": [
                "selected_atoms", "persona_title", "persona_priorities",
                "persona_pain_points"
            ],
        },
        "audience_edit": {
            "model": "gemini-2.5-flash",
            "max_tokens": 8000,
            "variables": [
                "persona_title", "persona_language_level",
                "persona_priorities", "draft_from_step1"
            ],
        },
        "factcheck": {
            "model": "gemini-2.5-flash",
            "max_tokens": 8000,
            "variables": ["original_transcript", "edited_draft_from_step2"],
        },
        "summarization": {
            "model": "gemini-2.5-flash",
            "max_tokens": 500,
            "variables": ["transcript"],
        },
        "still_matching": {
            "model": "gemini-2.5-flash",
            "max_tokens": 2000,
            "variables": [
                "old_still_content", "old_still_type",
                "new_still_candidates", "source_context"
            ],
        },
    }

    async with get_db() as db:
        for template_name, config in default_prompts.items():
            # Check if already exists
            existing = await fetchval(
                db,
                "SELECT id FROM prompt_templates WHERE template_name = ?",
                (template_name,)
            )
            if existing:
                continue

            # Try to load from file
            prompt_file = prompts_dir / f"{template_name}.txt"
            if prompt_file.exists():
                async with aiofiles.open(prompt_file, "r") as f:
                    prompt_content = await f.read()
            else:
                prompt_content = f"# {template_name} prompt template\n# Edit this template in the admin UI or /data/prompts/{template_name}.txt"

            # Insert into database
            await execute(
                db,
                """
                INSERT INTO prompt_templates
                (template_name, model, max_tokens, prompt_content, variables)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    template_name,
                    config["model"],
                    config["max_tokens"],
                    prompt_content,
                    json.dumps(config["variables"]),
                )
            )

        # Commit for SQLite (PostgreSQL auto-commits)
        if not settings.use_postgres:
            await db.commit()


async def get_prompt(template_name: str) -> Optional[dict]:
    """
    Get a prompt template by name.

    Returns the prompt content and configuration.
    """
    async with get_db() as db:
        row = await fetchone(
            db,
            """
            SELECT template_name, model, max_tokens, prompt_content, variables
            FROM prompt_templates
            WHERE template_name = ?
            """,
            (template_name,)
        )

        if not row:
            return None

        return {
            "template_name": row["template_name"],
            "model": row["model"],
            "max_tokens": row["max_tokens"],
            "prompt_content": row["prompt_content"],
            "variables": json.loads(row["variables"]) if row["variables"] else [],
        }


def render_prompt(template: str, variables: dict) -> str:
    """
    Render a prompt template with variables.

    Uses simple string formatting with {variable_name} placeholders.
    """
    try:
        return template.format(**variables)
    except KeyError as e:
        raise ValueError(f"Missing variable in prompt template: {e}")


async def get_rendered_prompt(template_name: str, variables: dict) -> tuple[str, dict]:
    """
    Get a fully rendered prompt ready for API call.

    Returns (rendered_prompt, config) tuple.
    """
    prompt_data = await get_prompt(template_name)
    if not prompt_data:
        raise ValueError(f"Prompt template not found: {template_name}")

    rendered = render_prompt(prompt_data["prompt_content"], variables)

    return rendered, {
        "model": prompt_data["model"],
        "max_tokens": prompt_data["max_tokens"],
    }
