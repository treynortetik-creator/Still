"""Brand Voice Analyzer - Learn brand voice from user's writing samples."""
import json
import logging
from typing import Dict, List, Tuple, Optional

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall
from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.utils.json_parser import parse_llm_json

settings = get_settings()

logger = logging.getLogger(__name__)


async def analyze_brand_voice(user_id: int, profile_id: int = None) -> Tuple[Dict, float]:
    """
    Analyze user's writing samples to extract brand voice patterns.

    Args:
        user_id: The user's ID
        profile_id: Optional specific profile to analyze (uses first/default if None)

    Returns:
        (voice_profile, cost) tuple
    """
    async with get_db() as db:
        # Get or create profile
        if profile_id:
            profile_row = await fetchone(
                db,
                "SELECT id FROM brand_voice_profiles WHERE id = ? AND user_id = ?",
                (profile_id, user_id)
            )
        else:
            profile_row = await fetchone(
                db,
                "SELECT id FROM brand_voice_profiles WHERE user_id = ? ORDER BY created_at LIMIT 1",
                (user_id,)
            )

        if not profile_row:
            # Create default profile
            if settings.use_postgres:
                row = await db.fetchrow(
                    "INSERT INTO brand_voice_profiles (user_id) VALUES ($1) RETURNING id",
                    user_id
                )
                profile_id = row["id"]
            else:
                cursor = await db.execute(
                    "INSERT INTO brand_voice_profiles (user_id) VALUES (?)",
                    (user_id,)
                )
                await db.commit()
                profile_id = cursor.lastrowid
        else:
            profile_id = profile_row["id"]

        # Get samples for this profile
        rows = await fetchall(
            db,
            """
            SELECT content, content_type
            FROM brand_voice_samples
            WHERE profile_id = ?
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (profile_id,)
        )

        if len(rows) < 3:
            raise ValueError(f"Need at least 3 samples to analyze (have {len(rows)})")

        # Prepare samples for analysis
        samples_text = []
        for i, row in enumerate(rows, 1):
            samples_text.append(f"""
--- Sample #{i} ({row["content_type"]}) ---
{row["content"]}
""")

        all_samples = "\n".join(samples_text)

    # Build analysis prompt
    prompt = f"""You are an expert brand voice analyst. Analyze these writing samples from the same author to extract their unique voice and style patterns.

WRITING SAMPLES ({len(rows)} pieces):
{all_samples}

TASK: Analyze these samples to create a comprehensive brand voice profile. Extract patterns that are consistent across samples.

Analyze:

1. VOCABULARY PATTERNS: Common words, phrases, and terminology choices
2. SENTENCE STRUCTURE: Average length, complexity, rhythm patterns
3. TONE MARKERS: Emotional qualities, personality traits evident in writing
4. PHRASES TO USE: Signature expressions, go-to phrases
5. PHRASES TO AVOID: Words or patterns they never use
6. FORMATTING PREFERENCES: Use of lists, paragraphs, headers, etc.
7. UNIQUE ELEMENTS: Distinctive characteristics that make this voice recognizable

OUTPUT FORMAT (valid JSON):
{{
    "vocabulary_patterns": {{
        "common_words": ["list of frequently used words"],
        "technical_level": "casual/moderate/technical",
        "industry_terms": ["any industry-specific terminology"]
    }},
    "sentence_structure": {{
        "average_length": "short/medium/long",
        "complexity": "simple/moderate/complex",
        "rhythm": "description of sentence rhythm patterns"
    }},
    "tone_markers": ["list of 5-7 tone/personality descriptors"],
    "phrases_to_use": ["list of 5-10 signature phrases or expressions"],
    "phrases_to_avoid": ["list of words/phrases this author never uses"],
    "formatting_preferences": ["list of formatting tendencies"],
    "overall_summary": "2-3 sentence summary of this brand voice"
}}"""

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=prompt,
        step="editing",
        response_format="json",
        user_id=user_id,
    )

    # Parse response with robust JSON parser
    try:
        result = parse_llm_json(response_text, context="brand voice analysis")
    except ValueError as e:
        logger.warning(f"Failed to parse brand voice analysis: {e}")
        result = {
            "overall_summary": "Analysis could not be completed",
            "tone_markers": [],
            "phrases_to_use": [],
            "phrases_to_avoid": []
        }

    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    # Save to database
    async with get_db() as db:
        if settings.use_postgres:
            await db.execute(
                """
                UPDATE brand_voice_profiles SET
                    vocabulary_patterns = $1,
                    sentence_structure = $2,
                    tone_markers = $3,
                    phrases_to_use = $4,
                    phrases_to_avoid = $5,
                    overall_summary = $6,
                    sample_count = $7,
                    updated_at = NOW()
                WHERE id = $8
                """,
                json.dumps(result.get("vocabulary_patterns")),
                json.dumps(result.get("sentence_structure")),
                json.dumps(result.get("tone_markers")),
                json.dumps(result.get("phrases_to_use")),
                json.dumps(result.get("phrases_to_avoid")),
                result.get("overall_summary"),
                len(rows),
                profile_id,
            )
            # Update user's cost
            await db.execute(
                "UPDATE users SET total_cost_incurred = total_cost_incurred + $1 WHERE id = $2",
                cost, user_id
            )
        else:
            await execute(
                db,
                """
                UPDATE brand_voice_profiles SET
                    vocabulary_patterns = ?,
                    sentence_structure = ?,
                    tone_markers = ?,
                    phrases_to_use = ?,
                    phrases_to_avoid = ?,
                    overall_summary = ?,
                    sample_count = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(result.get("vocabulary_patterns")),
                    json.dumps(result.get("sentence_structure")),
                    json.dumps(result.get("tone_markers")),
                    json.dumps(result.get("phrases_to_use")),
                    json.dumps(result.get("phrases_to_avoid")),
                    result.get("overall_summary"),
                    len(rows),
                    profile_id,
                )
            )
            # Update user's cost
            await execute(
                db,
                "UPDATE users SET total_cost_incurred = total_cost_incurred + ? WHERE id = ?",
                (cost, user_id)
            )
            await db.commit()

    return result, cost


async def get_brand_voice_profile(user_id: int) -> Optional[Dict]:
    """Get the user's brand voice profile."""
    async with get_db() as db:
        row = await fetchone(
            db,
            """
            SELECT *
            FROM brand_voice_profiles
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (user_id,)
        )

        if not row or not row["overall_summary"]:
            return None

        return {
            "id": row["id"],
            "profile_name": row["profile_name"],
            "vocabulary_patterns": json.loads(row["vocabulary_patterns"]) if row["vocabulary_patterns"] else None,
            "sentence_structure": json.loads(row["sentence_structure"]) if row["sentence_structure"] else None,
            "tone_markers": json.loads(row["tone_markers"]) if row["tone_markers"] else [],
            "phrases_to_use": json.loads(row["phrases_to_use"]) if row["phrases_to_use"] else [],
            "phrases_to_avoid": json.loads(row["phrases_to_avoid"]) if row["phrases_to_avoid"] else [],
            "overall_summary": row["overall_summary"],
            "sample_count": row["sample_count"],
            "updated_at": row["updated_at"],
        }


async def get_voice_samples(user_id: int) -> List[Dict]:
    """Get the user's voice samples."""
    async with get_db() as db:
        # Get or create profile first
        profile_row = await fetchone(
            db,
            "SELECT id FROM brand_voice_profiles WHERE user_id = ? ORDER BY created_at LIMIT 1",
            (user_id,)
        )

        if not profile_row:
            return []

        rows = await fetchall(
            db,
            """
            SELECT id, content, content_type, created_at
            FROM brand_voice_samples
            WHERE profile_id = ?
            ORDER BY created_at DESC
            """,
            (profile_row["id"],)
        )

        return [
            {
                "id": row["id"],
                "content": row["content"],
                "content_type": row["content_type"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


async def add_voice_sample(user_id: int, content: str, content_type: str = "general") -> int:
    """Add a writing sample for voice analysis."""
    async with get_db() as db:
        # Get or create profile
        profile_row = await fetchone(
            db,
            "SELECT id FROM brand_voice_profiles WHERE user_id = ? ORDER BY created_at LIMIT 1",
            (user_id,)
        )

        if not profile_row:
            if settings.use_postgres:
                row = await db.fetchrow(
                    "INSERT INTO brand_voice_profiles (user_id) VALUES ($1) RETURNING id",
                    user_id
                )
                profile_id = row["id"]
            else:
                cursor = await db.execute(
                    "INSERT INTO brand_voice_profiles (user_id) VALUES (?)",
                    (user_id,)
                )
                await db.commit()
                profile_id = cursor.lastrowid
        else:
            profile_id = profile_row["id"]

        # Add sample
        if settings.use_postgres:
            row = await db.fetchrow(
                """
                INSERT INTO brand_voice_samples (user_id, profile_id, content, content_type)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_id, profile_id, content.strip(), content_type
            )
            return row["id"]
        else:
            cursor = await db.execute(
                """
                INSERT INTO brand_voice_samples (user_id, profile_id, content, content_type)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, profile_id, content.strip(), content_type)
            )
            await db.commit()
            return cursor.lastrowid


async def delete_voice_sample(user_id: int, sample_id: int) -> bool:
    """Delete a voice sample."""
    async with get_db() as db:
        if settings.use_postgres:
            result = await db.execute(
                "DELETE FROM brand_voice_samples WHERE id = $1 AND user_id = $2",
                sample_id, user_id
            )
            # asyncpg returns 'DELETE N' where N is the count
            return result and result != "DELETE 0"
        else:
            cursor = await db.execute(
                "DELETE FROM brand_voice_samples WHERE id = ? AND user_id = ?",
                (sample_id, user_id)
            )
            await db.commit()
            return cursor.rowcount > 0


async def get_voice_context_for_drafting(user_id: int) -> str:
    """
    Get a condensed voice context for use in drafting prompts.

    Returns a string to inject into content generation prompts.
    """
    profile = await get_brand_voice_profile(user_id)

    if not profile:
        return ""

    context_parts = ["\n=== USER'S BRAND VOICE (match this style) ==="]

    if profile.get("overall_summary"):
        context_parts.append(f"VOICE SUMMARY: {profile['overall_summary']}")

    if profile.get("tone_markers"):
        tones = profile["tone_markers"][:5]
        context_parts.append(f"TONE: {', '.join(tones)}")

    if profile.get("phrases_to_use"):
        phrases = profile["phrases_to_use"][:5]
        context_parts.append(f"USE PHRASES LIKE: {'; '.join(phrases)}")

    if profile.get("phrases_to_avoid"):
        avoid = profile["phrases_to_avoid"][:5]
        context_parts.append(f"AVOID: {'; '.join(avoid)}")

    vocab = profile.get("vocabulary_patterns", {})
    if vocab.get("technical_level"):
        context_parts.append(f"VOCABULARY LEVEL: {vocab['technical_level']}")

    context_parts.append("")

    return "\n".join(context_parts)


async def get_brand_voice_config_context(user_id: int, content_type: str = None) -> str:
    """
    Get brand voice configuration to inject into drafting prompts.

    Args:
        user_id: User ID
        content_type: "linkedin", "blog", or "email" for platform-specific tone

    Returns:
        Formatted context string for prompt injection
    """
    async with get_db() as db:
        row = await fetchone(
            db,
            """
            SELECT company_name, industry, tone_linkedin, tone_blog,
                   tone_email, core_principles, phrases_to_use,
                   phrases_to_avoid, vocabulary_level
            FROM brand_voice_config
            WHERE user_id = ?
            """,
            (user_id,)
        )

        if not row:
            return ""

        # Check if any meaningful data exists
        has_data = any([
            row["company_name"],
            row["industry"],
            row["core_principles"],
            row["phrases_to_use"],
            row["phrases_to_avoid"],
            row["tone_linkedin"],
            row["tone_blog"],
            row["tone_email"],
        ])

        if not has_data:
            return ""

        context_parts = ["\n=== BRAND VOICE GUIDELINES (apply to all content) ==="]

        if row["company_name"]:
            context_parts.append(f"COMPANY: {row['company_name']}")

        if row["industry"]:
            context_parts.append(f"INDUSTRY: {row['industry']}")

        if row["vocabulary_level"]:
            context_parts.append(f"VOCABULARY LEVEL: {row['vocabulary_level'].title()}")

        # Core principles
        if row["core_principles"]:
            principles = json.loads(row["core_principles"])
            if principles:
                context_parts.append("\nCORE PRINCIPLES:")
                for principle in principles:
                    context_parts.append(f"- {principle}")

        # Phrases to use
        if row["phrases_to_use"]:
            phrases = json.loads(row["phrases_to_use"])
            if phrases:
                context_parts.append(f"\nUSE THESE PHRASES: {'; '.join(phrases)}")

        # Phrases to avoid
        if row["phrases_to_avoid"]:
            avoid = json.loads(row["phrases_to_avoid"])
            if avoid:
                context_parts.append(f"AVOID THESE PHRASES: {'; '.join(avoid)}")

        # Platform-specific tone
        tone_map = {
            "linkedin": row["tone_linkedin"],
            "blog": row["tone_blog"],
            "email": row["tone_email"],
        }

        if content_type and content_type in tone_map and tone_map[content_type]:
            platform_name = content_type.title()
            context_parts.append(f"\nPLATFORM-SPECIFIC TONE ({platform_name}):")
            context_parts.append(tone_map[content_type])

        context_parts.append("")

        return "\n".join(context_parts)
