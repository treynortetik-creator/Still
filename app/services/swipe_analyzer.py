"""Swipe File Analyzer - Extract patterns from user's collected content examples."""
import json
import logging
from typing import Dict, List, Tuple, Optional

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall
from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.utils.json_parser import parse_llm_json

logger = logging.getLogger(__name__)
settings = get_settings()


async def analyze_swipe_collection(
    user_id: int,
    min_swipes: int = 3
) -> Tuple[Dict, float]:
    """
    Analyze a user's swipe file collection to extract style patterns.

    Args:
        user_id: The user's ID
        min_swipes: Minimum swipes required for analysis

    Returns:
        (analysis_result, cost) tuple
    """
    async with get_db() as db:
        # Get all swipes for user
        rows = await fetchall(
            db,
            """
            SELECT content, source_type, tags, notes
            FROM swipe_files
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (user_id,)
        )

        if len(rows) < min_swipes:
            raise ValueError(f"Need at least {min_swipes} swipes to analyze (have {len(rows)})")

        # Prepare content for analysis
        swipes_text = []
        for i, row in enumerate(rows, 1):
            source_type = row["source_type"] or "general"
            tags = json.loads(row["tags"]) if row["tags"] else []
            notes = row["notes"] or ""

            swipes_text.append(f"""
--- Swipe #{i} ({source_type}) ---
{row["content"]}
Tags: {', '.join(tags) if tags else 'none'}
User notes: {notes if notes else 'none'}
""")

        all_swipes = "\n".join(swipes_text)

    # Build analysis prompt
    prompt = f"""You are an expert content strategist analyzing a collection of content examples that a user has saved as "swipe files" - content they admire and want to learn from.

SWIPE FILE COLLECTION ({len(rows)} examples):
{all_swipes}

TASK: Analyze these swipe files to extract patterns that define the user's preferred content style. This is their "Style DNA".

Analyze and identify:

1. HOOK STYLES: What types of opening hooks appear most often? (questions, statistics, bold statements, stories, etc.)

2. CTA PATTERNS: How do these pieces typically end? What calls-to-action or engagement prompts are used?

3. TONE PATTERNS: What tone characteristics are consistent? (casual, professional, bold, empathetic, humorous, etc.)

4. STRUCTURE PATTERNS: How is content typically structured? (short paragraphs, lists, single-line zingers, long-form narratives, etc.)

5. VOCABULARY PREFERENCES: Any notable word choices, phrases, or linguistic patterns?

6. ENGAGEMENT TACTICS: What techniques are used to maintain reader interest?

7. UNIQUE ELEMENTS: Any distinctive style elements that stand out?

OUTPUT FORMAT (valid JSON):
{{
    "patterns": {{
        "hook_styles": ["list of 3-5 common hook styles with examples"],
        "cta_patterns": ["list of 3-5 common CTA patterns"],
        "tone_patterns": ["list of 3-5 tone characteristics"],
        "structure_patterns": ["list of 3-5 structural patterns"],
        "vocabulary_preferences": ["list of notable phrases or word patterns"],
        "engagement_tactics": ["list of engagement techniques used"],
        "unique_elements": ["list of distinctive style elements"]
    }},
    "summary": "A 2-3 sentence summary of the user's preferred content style",
    "recommendations": ["3-5 actionable recommendations for content creation based on these patterns"]
}}"""

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=prompt,
        step="editing",
        response_format="json",
        user_id=user_id,
    )

    # Parse response with robust JSON parser
    try:
        result = parse_llm_json(response_text, context="swipe analysis")
    except ValueError as e:
        logger.warning(f"Failed to parse swipe analysis: {e}")
        result = {
            "patterns": {},
            "summary": "Analysis could not be completed",
            "recommendations": []
        }

    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    # Save analysis to database
    async with get_db() as db:
        # Check if analysis exists
        existing = await fetchone(
            db,
            "SELECT id FROM swipe_analysis WHERE user_id = ? AND analysis_type = 'style_dna'",
            (user_id,)
        )

        if existing:
            await execute(
                db,
                """
                UPDATE swipe_analysis
                SET patterns = ?, summary = ?, swipe_count = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(result["patterns"]), result.get("summary"), len(rows), existing["id"])
            )
        else:
            await execute(
                db,
                """
                INSERT INTO swipe_analysis (user_id, analysis_type, patterns, summary, swipe_count)
                VALUES (?, 'style_dna', ?, ?, ?)
                """,
                (user_id, json.dumps(result["patterns"]), result.get("summary"), len(rows))
            )

        # Update user's cost
        await execute(
            db,
            "UPDATE users SET total_cost_incurred = total_cost_incurred + ? WHERE id = ?",
            (cost, user_id)
        )
        if not settings.use_postgres:
            await db.commit()

    return result, cost


async def get_style_dna(user_id: int) -> Optional[Dict]:
    """Get the user's saved Style DNA analysis."""
    async with get_db() as db:
        row = await fetchone(
            db,
            """
            SELECT patterns, summary, swipe_count, updated_at
            FROM swipe_analysis
            WHERE user_id = ? AND analysis_type = 'style_dna'
            """,
            (user_id,)
        )

        if not row:
            return None

        return {
            "patterns": json.loads(row["patterns"]) if row["patterns"] else {},
            "summary": row["summary"],
            "swipe_count": row["swipe_count"],
            "updated_at": row["updated_at"],
        }


async def get_style_context_for_drafting(user_id: int) -> str:
    """
    Get a condensed style context from Style DNA for use in drafting prompts.

    Returns a string that can be injected into content generation prompts.
    """
    style_dna = await get_style_dna(user_id)

    if not style_dna or not style_dna.get("patterns"):
        return ""

    patterns = style_dna["patterns"]

    # Build context string
    context_parts = []

    if patterns.get("hook_styles"):
        hooks = patterns["hook_styles"][:3]
        context_parts.append(f"PREFERRED HOOK STYLES: {'; '.join(hooks)}")

    if patterns.get("tone_patterns"):
        tones = patterns["tone_patterns"][:3]
        context_parts.append(f"TONE: {'; '.join(tones)}")

    if patterns.get("structure_patterns"):
        structures = patterns["structure_patterns"][:2]
        context_parts.append(f"STRUCTURE: {'; '.join(structures)}")

    if patterns.get("cta_patterns"):
        ctas = patterns["cta_patterns"][:2]
        context_parts.append(f"CTA STYLE: {'; '.join(ctas)}")

    if not context_parts:
        return ""

    return "\n\n=== USER'S STYLE PREFERENCES (from their swipe file analysis) ===\n" + "\n".join(context_parts) + "\n"


async def analyze_single_swipe(
    content: str,
    user_id: int,
) -> Tuple[Dict, float]:
    """
    Analyze a single piece of content for quick insights.

    Returns analysis of what makes this content effective.
    """
    prompt = f"""Analyze this content example and explain what makes it effective:

CONTENT:
{content}

OUTPUT FORMAT (valid JSON):
{{
    "hook_type": "Type of opening hook used",
    "tone": "Primary tone/voice",
    "structure": "How the content is structured",
    "cta_type": "Type of call-to-action (if any)",
    "key_techniques": ["List of 3-5 effective techniques used"],
    "why_it_works": "1-2 sentences explaining why this content is effective"
}}"""

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=prompt,
        step="editing",
        response_format="json",
        user_id=user_id,
    )

    try:
        result = parse_llm_json(response_text, context="swipe file analysis")
    except ValueError as e:
        logger.warning(f"Failed to parse swipe file analysis: {e}")
        result = {"why_it_works": "Could not analyze this content"}

    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    return result, cost
