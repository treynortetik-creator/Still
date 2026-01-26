"""Smart Content Remix - Surface new content ideas from existing library."""
import json
import logging
from typing import Dict, List, Tuple
from collections import defaultdict

from app.config import get_settings
from app.database import get_db
from app.db_utils import execute, fetchone, fetchall
from app.services.ai_client import call_llm_text, calculate_openrouter_cost
from app.utils.json_parser import parse_llm_json

settings = get_settings()
logger = logging.getLogger(__name__)


async def analyze_library_for_remix(user_id: int) -> Tuple[Dict, float]:
    """
    Analyze user's still library to suggest content remix opportunities.

    Returns suggestions for:
    - Topic clusters (stills that group together)
    - Comparison opportunities (contrasting ideas)
    - Contrarian takes (flip common perspectives)
    - Story expansions (stills that could become longer content)
    - Roundup posts (multiple stills on similar themes)

    Args:
        user_id: The user's ID

    Returns:
        (suggestions, cost) tuple
    """
    async with get_db() as db:
        # Get user's stills
        rows = await fetchall(
            db,
            """
            SELECT id, still_type, content, tags, source_file
            FROM stills
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (user_id,)
        )

        if len(rows) < 5:
            return {
                "suggestions": [],
                "message": "Add more stills to get remix suggestions (need at least 5)",
                "still_count": len(rows),
            }, 0.0

        # Prepare stills for analysis
        stills_text = []
        for i, row in enumerate(rows, 1):
            tags = json.loads(row["tags"]) if row["tags"] else []
            stills_text.append(f"""
[Still #{i}] Type: {row["still_type"]}
Content: {row["content"]}
Tags: {', '.join(tags) if tags else 'none'}
""")

        all_stills = "\n".join(stills_text)

    # Build analysis prompt
    prompt = f"""You are a content strategist analyzing a library of content stills (reusable content pieces). Your goal is to suggest creative ways to remix and combine these stills into new content.

STILL LIBRARY ({len(rows)} stills):
{all_stills}

TASK: Analyze these stills and suggest content remix opportunities. Look for:

1. TOPIC CLUSTERS: Groups of stills that share a theme and could become a comprehensive post
2. COMPARISON OPPORTUNITIES: Pairs of stills with contrasting viewpoints that could create a comparison/debate post
3. CONTRARIAN TAKES: Stills with common wisdom that could be flipped into contrarian perspectives
4. STORY EXPANSIONS: Stills with compelling stories/examples that deserve deeper exploration
5. ROUNDUP POSTS: Collections of stills (3+) on similar topics perfect for a "5 things I learned" style post

For each suggestion, be specific about which stills to use and how to combine them.

OUTPUT FORMAT (valid JSON):
{{
    "topic_clusters": [
        {{
            "theme": "theme name",
            "still_ids": [1, 3, 7],
            "post_idea": "Suggested post title/concept",
            "why_it_works": "Brief explanation"
        }}
    ],
    "comparison_opportunities": [
        {{
            "topic": "comparison topic",
            "still_a": 2,
            "still_b": 5,
            "angle": "How to frame the comparison",
            "post_idea": "Suggested post title/concept"
        }}
    ],
    "contrarian_takes": [
        {{
            "original_still": 4,
            "contrarian_angle": "The flip perspective",
            "post_idea": "Suggested post title/concept"
        }}
    ],
    "story_expansions": [
        {{
            "still_id": 6,
            "expansion_idea": "How to expand this into longer content",
            "target_format": "blog/linkedin series/email sequence"
        }}
    ],
    "roundup_posts": [
        {{
            "theme": "roundup theme",
            "still_ids": [1, 2, 3, 4, 5],
            "post_title": "Suggested roundup title like '5 lessons about X'",
            "format": "linkedin/blog"
        }}
    ],
    "quick_wins": [
        "List of 3-5 simple post ideas from individual stills"
    ]
}}

Focus on quality over quantity. Only include suggestions that would genuinely make good content."""

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=prompt,
        step="editing",
        response_format="json",
        user_id=user_id,
    )

    # Parse response with robust JSON parser
    try:
        result = parse_llm_json(response_text, context="remix analysis")
    except ValueError as e:
        logger.warning(f"Failed to parse remix analysis: {e}")
        result = {
            "topic_clusters": [],
            "comparison_opportunities": [],
            "contrarian_takes": [],
            "story_expansions": [],
            "roundup_posts": [],
            "quick_wins": []
        }

    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    # Update user's cost
    async with get_db() as db:
        await execute(
            db,
            "UPDATE users SET total_cost_incurred = total_cost_incurred + ? WHERE id = ?",
            (cost, user_id)
        )
        if not settings.use_postgres:
            await db.commit()

    result["still_count"] = len(rows)
    return result, cost


async def get_stills_by_topic(user_id: int, topic: str) -> List[Dict]:
    """
    Search stills by topic/keyword.

    Args:
        user_id: The user's ID
        topic: Search term

    Returns:
        List of matching stills
    """
    async with get_db() as db:
        # Simple text search
        rows = await fetchall(
            db,
            """
            SELECT id, still_type, content, tags, source_file
            FROM stills
            WHERE user_id = ? AND (
                content LIKE ? OR
                tags LIKE ?
            )
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id, f"%{topic}%", f"%{topic}%")
        )

        return [
            {
                "id": row["id"],
                "still_type": row["still_type"],
                "content": row["content"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "source_file": row["source_file"],
            }
            for row in rows
        ]


async def get_library_stats(user_id: int) -> Dict:
    """Get statistics about user's still library."""
    async with get_db() as db:
        # Total count
        total_row = await fetchone(
            db,
            "SELECT COUNT(*) as count FROM stills WHERE user_id = ?",
            (user_id,)
        )
        total = total_row["count"]

        # By type
        type_rows = await fetchall(
            db,
            """
            SELECT still_type, COUNT(*) as count
            FROM stills
            WHERE user_id = ?
            GROUP BY still_type
            """,
            (user_id,)
        )
        by_type = {row["still_type"]: row["count"] for row in type_rows}

        # Get all tags
        tag_rows = await fetchall(
            db,
            "SELECT tags FROM stills WHERE user_id = ? AND tags IS NOT NULL",
            (user_id,)
        )
        tag_counts = defaultdict(int)
        for row in tag_rows:
            tags = json.loads(row["tags"]) if row["tags"] else []
            for tag in tags:
                tag_counts[tag] += 1

        # Top tags
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:15]

        return {
            "total_stills": total,
            "by_type": by_type,
            "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
        }


async def generate_remix_content(
    user_id: int,
    still_ids: List[str],
    content_type: str = "linkedin",
    angle: str = None,
) -> Tuple[str, float]:
    """
    Generate a remixed piece of content from selected stills.

    Args:
        user_id: The user's ID
        still_ids: List of still IDs to combine
        content_type: Target content type (linkedin, blog, email)
        angle: Optional angle/approach for the content

    Returns:
        (generated_content, cost) tuple
    """
    async with get_db() as db:
        # Get the specified stills
        placeholders = ",".join(["?" for _ in still_ids])
        rows = await fetchall(
            db,
            f"""
            SELECT content, still_type, tags
            FROM stills
            WHERE id IN ({placeholders}) AND user_id = ?
            """,
            (*still_ids, user_id)
        )

        if not rows:
            raise ValueError("No stills found with those IDs")

        stills_text = []
        for row in rows:
            stills_text.append(f"[{row['still_type']}]: {row['content']}")

        combined_stills = "\n\n".join(stills_text)

    content_type_instructions = {
        "linkedin": "Create a LinkedIn post (1200-1500 characters). Start with a strong hook. Use short paragraphs. End with engagement question or CTA.",
        "blog": "Create a blog post section (500-800 words). Include a compelling subheading. Structure with clear flow.",
        "email": "Create an email body (200-400 words). Conversational tone. Clear single CTA.",
    }

    prompt = f"""You are a content creator combining multiple content stills into a cohesive piece.

SOURCE STILLS:
{combined_stills}

CONTENT TYPE: {content_type}
{content_type_instructions.get(content_type, '')}

{f'ANGLE/APPROACH: {angle}' if angle else ''}

TASK: Combine these stills into a single, cohesive piece of content. The stills should flow naturally together, not feel like a patchwork.

RULES:
1. Maintain the core insights from each still
2. Add transitions and connections between ideas
3. Create a compelling narrative arc
4. Match the format requirements for {content_type}
5. Make it feel like one unified piece, not separate parts

Return ONLY the content, no explanations."""

    response_text, input_tokens, output_tokens, model = await call_llm_text(
        prompt=prompt,
        step="drafting",
        user_id=user_id,
    )

    cost = calculate_openrouter_cost(model, input_tokens, output_tokens)

    # Update user's cost
    async with get_db() as db:
        await execute(
            db,
            "UPDATE users SET total_cost_incurred = total_cost_incurred + ? WHERE id = ?",
            (cost, user_id)
        )
        if not settings.use_postgres:
            await db.commit()

    return response_text.strip(), cost
